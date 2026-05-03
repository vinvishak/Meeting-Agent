"""
Core sync worker.

Orchestrates one full sync cycle:
  1. Fetch Jira sprints + tickets via JiraClient
  2. Normalise engineer identities
  3. Resolve StatusMapping for each ticket's raw Jira status
  4. Extract classification signals and run the classifier
  5. Persist Ticket, TicketSnapshot, and AuditEntry(status_inferred) records
  6. Ingest new Copilot transcripts → entity match → analyze → create suggestions
  7. Write a final AuditEntry(sync_completed | sync_failed)

Standalone CLI (runs one cycle and exits):
    python -m src.workers.sync_worker --run-once
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from src.classification.classifier import classify
from src.classification.signals import extract_signals
from src.config import get_settings
from src.ingestion.jira_client import JiraClient
from src.ingestion.normalizer import JiraIdentity, normalize_engineers
from src.logging_config import configure_logging, get_logger
from src.storage.database import AsyncSessionLocal
from src.storage.models import (
    AuditEventType,
    NormalizedStatus,
)
from src.storage.repository import (
    AuditRepository,
    SnapshotRepository,
    SprintRepository,
    StatusMappingRepository,
    TicketRepository,
)

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def run_sync_cycle() -> None:
    """
    Perform one complete Jira sync cycle.

    Raises on unrecoverable errors; the scheduler catches and logs them.
    """
    settings = get_settings()
    project_keys = [k.strip() for k in settings.jira_project_keys.split(",") if k.strip()]
    if not project_keys:
        logger.warning("JIRA_PROJECT_KEYS is not configured — skipping sync cycle")
        return

    started_at = _utcnow()
    logger.info("Sync cycle started at %s for projects: %s", started_at.isoformat(), project_keys)

    error: Exception | None = None

    try:
        async with JiraClient() as jira:
            for project_key in project_keys:
                await _sync_project(jira, project_key, settings)

        # Ingest Copilot transcripts after Jira sync completes
        await _ingest_transcripts()

        # Recalculate velocity metrics for all synced boards (T037)
        await _recalculate_velocity(project_keys)
    except Exception as exc:
        error = exc
        logger.error("Sync cycle failed: %s", exc, exc_info=True)

    # GitHub sync runs independently — failure must not abort Jira sync results
    try:
        await _sync_github()
    except Exception as exc:
        logger.warning("GitHub sync failed (non-fatal): %s", exc, exc_info=True)

    elapsed = (_utcnow() - started_at).total_seconds()
    async with AsyncSessionLocal() as session:
        if error is None:
            await AuditRepository.create(
                session,
                event_type=AuditEventType.sync_completed.value,
                reasoning=f"Sync completed in {elapsed:.1f}s. Projects: {project_keys}.",
                signal_inputs={"elapsed_seconds": elapsed, "projects": project_keys},
            )
            logger.info("Sync cycle completed in %.1fs", elapsed)
        else:
            await AuditRepository.create(
                session,
                event_type=AuditEventType.sync_failed.value,
                reasoning=f"Sync failed after {elapsed:.1f}s: {error}",
                signal_inputs={"elapsed_seconds": elapsed, "projects": project_keys, "error": str(error)},
            )
        await session.commit()

    if error is not None:
        raise error


async def _sync_project(jira: JiraClient, project_key: str, settings: object) -> None:
    """Sync all sprints and tickets for one Jira project key."""
    stale_days: int = getattr(settings, "stale_threshold_days", 10)

    # ------------------------------------------------------------------
    # 1. Fetch sprints
    # ------------------------------------------------------------------
    board_id = await jira.get_board_id(project_key)
    sprints = await jira.list_sprints(board_id) if board_id else []
    sprint_id_map: dict[str, str] = {}  # jira_sprint_id → internal DB id

    async with AsyncSessionLocal() as session:
        for s in sprints:
            sprint = await SprintRepository.upsert(
                session,
                jira_sprint_id=s.jira_sprint_id,
                name=s.name,
                board_id=s.board_id,
                state=s.state,
                start_date=s.start_date,
                end_date=s.end_date,
            )
            sprint_id_map[s.jira_sprint_id] = sprint.id
        await session.commit()

    logger.debug("Upserted %d sprint(s) for project %s", len(sprints), project_key)

    # ------------------------------------------------------------------
    # 2. Fetch issues
    # ------------------------------------------------------------------
    issues = await jira.list_issues(project_key)
    if not issues:
        logger.info("No issues returned for project %s", project_key)
        return

    # ------------------------------------------------------------------
    # 3. Normalise engineer identities
    # ------------------------------------------------------------------
    identities = [
        JiraIdentity(
            username=issue.assignee_username or f"__unknown__{issue.jira_id}",
            display_name=issue.assignee_display_name or "Unknown",
            email=issue.assignee_email,
        )
        for issue in issues
        if issue.assignee_username or issue.assignee_display_name
    ]
    # Deduplicate by username
    seen: set[str] = set()
    unique_identities: list[JiraIdentity] = []
    for ident in identities:
        if ident.username not in seen:
            seen.add(ident.username)
            unique_identities.append(ident)

    async with AsyncSessionLocal() as session:
        username_to_engineer_id = await normalize_engineers(session, unique_identities)
        await session.commit()

    # ------------------------------------------------------------------
    # 4. Resolve status mappings (cached per board)
    # ------------------------------------------------------------------
    async with AsyncSessionLocal() as session:
        status_cache: dict[str, str] = {}  # raw_status → normalized_status
        mappings = await StatusMappingRepository.list_by_board(session, project_key)
        for m in mappings:
            status_cache[m.jira_status_name.lower()] = m.normalized_status

    def _normalize_status(raw: str) -> str:
        """Best-effort normalization when no explicit mapping exists."""
        cached = status_cache.get(raw.lower())
        if cached:
            return cached
        lower = raw.lower()
        if "done" in lower or "closed" in lower or "resolved" in lower or "complete" in lower:
            return NormalizedStatus.done.value
        if "progress" in lower or "active" in lower or "develop" in lower:
            return NormalizedStatus.in_progress.value
        if "review" in lower or "testing" in lower or "qa" in lower:
            return NormalizedStatus.review.value
        if "block" in lower:
            return NormalizedStatus.blocked.value
        return NormalizedStatus.open.value

    # ------------------------------------------------------------------
    # 5. Upsert tickets, classify, snapshot
    # ------------------------------------------------------------------
    now = _utcnow()
    mention_cutoff = now - timedelta(days=2)

    async with AsyncSessionLocal() as session:
        for issue in issues:
            normalized_status = _normalize_status(issue.jira_status)
            sprint_id = sprint_id_map.get(issue.sprint_jira_id or "") if issue.sprint_jira_id else None
            assignee_id = username_to_engineer_id.get(issue.assignee_username or "")

            # Upsert the ticket
            ticket = await TicketRepository.upsert(
                session,
                jira_id=issue.jira_id,
                title=issue.summary,
                description=issue.description,
                assignee_id=assignee_id,
                sprint_id=sprint_id,
                jira_status=issue.jira_status,
                normalized_status=normalized_status,
                priority=issue.priority,
                story_points=issue.story_points,
                labels=issue.labels,
                linked_issue_ids=issue.linked_issue_ids,
                created_at=_aware(issue.created_at),
                updated_at=_aware(issue.updated_at),
                due_date=issue.due_date,
            )
            await session.flush()

            # Detect recent status transition from last snapshot
            snapshots = await SnapshotRepository.list_by_ticket(session, ticket.id, limit=1)
            previous_jira_status = snapshots[0].jira_status if snapshots else None
            previous_changed_at = (
                _aware(snapshots[0].snapshot_at)
                if snapshots and snapshots[0].jira_status != issue.jira_status
                else None
            )

            # Fetch recent transcript mentions (within 2 days) from DB
            from src.storage.repository import MentionRepository  # local import avoids circularity

            recent_mentions = await MentionRepository.list_recent_by_ticket(
                session, ticket.id, mention_cutoff
            )

            # Extract signals and classify
            signals = extract_signals(
                ticket=ticket,
                normalized_status=normalized_status,
                recent_mentions=recent_mentions,
                previous_jira_status=previous_jira_status,
                previous_status_changed_at=previous_changed_at,
                stale_threshold_days=stale_days,
            )
            inferred_status, reason = classify(
                normalized_status=normalized_status,
                signals=signals,
                stale_threshold_days=stale_days,
            )

            # Update inferred status on the ticket
            await TicketRepository.update_inferred_status(session, ticket.id, inferred_status, reason)

            # Create immutable snapshot
            await SnapshotRepository.create(
                session,
                ticket_id=ticket.id,
                jira_status=issue.jira_status,
                normalized_status=normalized_status,
                assignee_id=assignee_id,
                sprint_id=sprint_id,
                story_points=issue.story_points,
                inferred_status=inferred_status,
            )

            # Write audit entry
            await AuditRepository.create(
                session,
                event_type=AuditEventType.status_inferred.value,
                ticket_id=ticket.id,
                reasoning=reason,
                signal_inputs={
                    "jira_status_weight": signals.jira_status_weight,
                    "recent_transcript_mention_weight": signals.recent_transcript_mention_weight,
                    "recent_activity_weight": signals.recent_activity_weight,
                    "recent_transition_weight": signals.recent_transition_weight,
                    "has_blocker": signals.has_blocker,
                    "total_score": signals.total_score,
                    "inferred_status": inferred_status,
                },
            )

        await session.commit()

    logger.info("Processed %d issue(s) for project %s", len(issues), project_key)


# ---------------------------------------------------------------------------
# T028 — Copilot transcript ingestion
# ---------------------------------------------------------------------------


async def _ingest_transcripts() -> None:
    """
    Fetch new Copilot meetings, persist transcripts, run analysis pipeline,
    and generate UpdateSuggestion records.

    Silently skips if COPILOT_MCP_URL/token are not configured.
    """
    from anthropic import AsyncAnthropic

    from src.analysis.transcript_analyzer import analyze_transcript
    from src.analysis.update_suggester import create_suggestions_from_mentions
    from src.ingestion.copilot_client import CopilotMCPClient
    from src.storage.repository import TicketRepository, TranscriptRepository

    settings = get_settings()
    if not settings.copilot_mcp_url or not settings.copilot_mcp_token:
        logger.debug("Copilot MCP not configured — skipping transcript ingestion")
        return

    anthropic_client: AsyncAnthropic | None = None
    if settings.anthropic_api_key:
        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        async with CopilotMCPClient() as copilot:
            meetings = await copilot.list_meetings()
    except Exception as exc:
        logger.warning("Copilot transcript fetch failed: %s", exc)
        return

    ingested = 0
    for meeting in meetings:
        try:
            # Deduplication: skip already-ingested meetings
            async with AsyncSessionLocal() as session:
                existing = await TranscriptRepository.get_by_meeting_id(session, meeting.copilot_meeting_id)

            if existing:
                continue

            # Fetch full transcript
            async with CopilotMCPClient() as copilot:
                raw = await copilot.get_transcript(meeting.copilot_meeting_id)

            if raw is None:
                continue

            # Persist Transcript record
            async with AsyncSessionLocal() as session:
                transcript = await TranscriptRepository.upsert(
                    session,
                    copilot_meeting_id=meeting.copilot_meeting_id,
                    title=raw.title,
                    started_at=_aware(raw.started_at),
                    ended_at=_aware(raw.ended_at) if raw.ended_at else None,
                    participants=raw.participants,
                    raw_transcript=raw.raw_transcript,
                    copilot_summary=raw.copilot_summary,
                    action_items=raw.action_items,
                )
                await session.commit()

            # Run analysis pipeline
            async with AsyncSessionLocal() as session:
                active_tickets = await TicketRepository.list_active(session)
                candidates = await analyze_transcript(
                    transcript, active_tickets, session, anthropic_client
                )
                if candidates:
                    await create_suggestions_from_mentions(
                        candidates,
                        session,
                        transcript_id=transcript.id,
                    )
                await TranscriptRepository.mark_processed(session, transcript.id)
                await session.commit()

            ingested += 1
            logger.info("Ingested transcript for meeting %s", meeting.copilot_meeting_id)
        except Exception as exc:
            logger.warning("Failed to ingest meeting %s: %s", meeting.copilot_meeting_id, exc)

    logger.info("Transcript ingestion complete: %d new meeting(s) processed", ingested)


# ---------------------------------------------------------------------------
# T037 — Velocity recalculation
# ---------------------------------------------------------------------------


async def _recalculate_velocity(project_keys: list[str]) -> None:
    """
    Recompute sprint metrics for all boards after each sync cycle and persist
    updated Sprint.velocity and Sprint.completed_points.
    """
    from sqlalchemy import select

    from src.storage.models import Sprint
    from src.velocity.calculator import compute_sprint_metrics

    async with AsyncSessionLocal() as session:
        board_ids_result = await session.execute(select(Sprint.board_id).distinct())
        board_ids = [row[0] for row in board_ids_result]

    for board_id in board_ids:
        try:
            async with AsyncSessionLocal() as session:
                report = await compute_sprint_metrics(session, board_id, sprint_count=10)
                # Update Sprint.velocity for each closed sprint in the report
                for metrics in report.sprints:
                    sprint_result = await session.execute(
                        select(Sprint).where(Sprint.id == metrics.sprint_id)
                    )
                    sprint = sprint_result.scalar_one_or_none()
                    if sprint:
                        sprint.velocity = metrics.velocity
                        sprint.completed_points = metrics.completed_points
                await session.commit()
            logger.debug("Velocity recalculated for board %s", board_id)
        except Exception as exc:
            logger.warning("Velocity recalculation failed for board %s: %s", board_id, exc)


# ---------------------------------------------------------------------------
# GitHub sync
# ---------------------------------------------------------------------------


async def _sync_github() -> None:
    """
    Fetch commits and PRs from GitHub for all configured repos.

    Silently skips if GITHUB_PAT or GITHUB_ORG is not configured.
    Extracts Jira ticket keys from commit messages and PR text, stores links.
    """
    from src.ingestion.github_client import GitHubClient, extract_jira_keys
    from src.storage.repository import GitHubRepository

    settings = get_settings()
    if not settings.github_pat or not settings.github_org:
        logger.debug("GitHub PAT or org not configured — skipping GitHub sync")
        return

    logger.info("GitHub sync started for org: %s", settings.github_org)
    total_commits = 0
    total_prs = 0
    total_links = 0

    async with GitHubClient() as gh:
        # Determine which repos to sync
        if settings.github_repos.strip():
            repo_names = [r.strip() for r in settings.github_repos.split(",") if r.strip()]
            from src.ingestion.github_client import GitHubRepoInfo
            repos = [
                GitHubRepoInfo(
                    full_name=f"{settings.github_org}/{name}",
                    org=settings.github_org,
                    name=name,
                    default_branch="main",
                )
                for name in repo_names
            ]
        else:
            repos = await gh.list_repos()

        for repo_info in repos:
            try:
                async with AsyncSessionLocal() as session:
                    db_repo = await GitHubRepository.upsert_repo(
                        session,
                        org=repo_info.org,
                        name=repo_info.name,
                        full_name=repo_info.full_name,
                        default_branch=repo_info.default_branch,
                    )
                    await session.commit()
                    since = _aware(db_repo.last_synced_at) if db_repo.last_synced_at else None
                    repo_id = db_repo.id

                # Fetch and store commits
                commits = await gh.list_commits(repo_info.full_name, since=since)
                async with AsyncSessionLocal() as session:
                    for c in commits:
                        commit = await GitHubRepository.upsert_commit(
                            session,
                            repo_id=repo_id,
                            sha=c.sha,
                            message=c.message,
                            author_login=c.author_login,
                            author_name=c.author_name,
                            author_email=c.author_email,
                            committed_at=_aware(c.committed_at),
                            branch=c.branch,
                            url=c.url,
                        )
                        for key in extract_jira_keys(c.message):
                            await GitHubRepository.upsert_jira_link(
                                session,
                                source_type="commit",
                                jira_key=key,
                                commit_sha=commit.sha,
                            )
                            total_links += 1
                    await session.commit()
                total_commits += len(commits)

                # Fetch and store PRs
                prs = await gh.list_prs(repo_info.full_name, since=since)
                async with AsyncSessionLocal() as session:
                    for p in prs:
                        pr = await GitHubRepository.upsert_pr(
                            session,
                            repo_id=repo_id,
                            pr_number=p.pr_number,
                            title=p.title,
                            body=p.body,
                            state=p.state,
                            author_login=p.author_login,
                            head_branch=p.head_branch,
                            base_branch=p.base_branch,
                            opened_at=_aware(p.opened_at),
                            closed_at=_aware(p.closed_at) if p.closed_at else None,
                            merged_at=_aware(p.merged_at) if p.merged_at else None,
                            url=p.url,
                        )
                        pr_text = f"{p.title} {p.body[:2000] if p.body else ''}"
                        for key in extract_jira_keys(pr_text):
                            await GitHubRepository.upsert_jira_link(
                                session,
                                source_type="pr",
                                jira_key=key,
                                pr_id=pr.id,
                            )
                            total_links += 1
                    await session.commit()
                total_prs += len(prs)

                # Mark repo as synced
                async with AsyncSessionLocal() as session:
                    await GitHubRepository.update_repo_synced_at(session, repo_id, _utcnow())
                    await session.commit()

                logger.debug(
                    "GitHub: synced %s — %d commits, %d PRs",
                    repo_info.full_name, len(commits), len(prs),
                )
            except Exception as exc:
                logger.warning("GitHub: failed to sync repo %s: %s", repo_info.full_name, exc)

    # Resolve any forward references (links created before Jira ticket existed)
    async with AsyncSessionLocal() as session:
        resolved = await GitHubRepository.resolve_forward_jira_links(session)
        await session.commit()
    if resolved:
        logger.info("GitHub: resolved %d forward Jira link(s)", resolved)

    logger.info(
        "GitHub sync complete: %d repos, %d commits, %d PRs, %d Jira links",
        len(repos), total_commits, total_prs, total_links,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    configure_logging("INFO")
    parser = argparse.ArgumentParser(description="Jira sync worker.")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single sync cycle and exit (dev/debugging mode).",
    )
    args = parser.parse_args()
    if args.run_once:
        asyncio.run(run_sync_cycle())
        return 0
    print("Use --run-once for a single cycle, or run via the scheduler.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
