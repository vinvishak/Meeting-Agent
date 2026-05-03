"""
Data-access layer for all 9 entities.

All methods accept an AsyncSession and perform no business logic — only
structured reads and writes. Callers are responsible for committing or
rolling back transactions.

Pattern:
    async with AsyncSessionLocal() as session:
        ticket = await TicketRepository.get_by_jira_id(session, "PROJ-123")
        await session.commit()
"""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import (
    AuditEntry,
    Engineer,
    GitHubCommit,
    GitHubJiraLink,
    GitHubPullRequest,
    GitHubRepo,
    Sprint,
    StatusMapping,
    Ticket,
    TicketSnapshot,
    Transcript,
    TranscriptMention,
    UpdateSuggestion,
    _now,
)

# ---------------------------------------------------------------------------
# Engineer
# ---------------------------------------------------------------------------


class EngineerRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, engineer_id: str) -> Engineer | None:
        result = await session.execute(select(Engineer).where(Engineer.id == engineer_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Engineer | None:
        result = await session.execute(select(Engineer).where(Engineer.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_jira_username(session: AsyncSession, username: str) -> Engineer | None:
        result = await session.execute(
            select(Engineer).where(Engineer.jira_username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Engineer]:
        result = await session.execute(select(Engineer).order_by(Engineer.display_name))
        return list(result.scalars().all())

    @staticmethod
    async def create(session: AsyncSession, **kwargs: Any) -> Engineer:
        engineer = Engineer(**kwargs)
        session.add(engineer)
        await session.flush()
        return engineer

    @staticmethod
    async def update(session: AsyncSession, engineer_id: str, **kwargs: Any) -> Engineer | None:
        kwargs["updated_at"] = _now()
        await session.execute(
            update(Engineer).where(Engineer.id == engineer_id).values(**kwargs)
        )
        return await EngineerRepository.get_by_id(session, engineer_id)


# ---------------------------------------------------------------------------
# Sprint
# ---------------------------------------------------------------------------


class SprintRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, sprint_id: str) -> Sprint | None:
        result = await session.execute(select(Sprint).where(Sprint.id == sprint_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_jira_id(session: AsyncSession, jira_sprint_id: str) -> Sprint | None:
        result = await session.execute(
            select(Sprint).where(Sprint.jira_sprint_id == jira_sprint_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_board(session: AsyncSession, board_id: str) -> list[Sprint]:
        result = await session.execute(
            select(Sprint).where(Sprint.board_id == board_id).order_by(Sprint.start_date.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def upsert(session: AsyncSession, jira_sprint_id: str, **kwargs: Any) -> Sprint:
        sprint = await SprintRepository.get_by_jira_id(session, jira_sprint_id)
        if sprint is None:
            sprint = Sprint(jira_sprint_id=jira_sprint_id, **kwargs)
            session.add(sprint)
        else:
            for key, value in kwargs.items():
                setattr(sprint, key, value)
        await session.flush()
        return sprint


# ---------------------------------------------------------------------------
# StatusMapping
# ---------------------------------------------------------------------------


class StatusMappingRepository:
    @staticmethod
    async def get(session: AsyncSession, board_id: str, jira_status_name: str) -> StatusMapping | None:
        result = await session.execute(
            select(StatusMapping).where(
                StatusMapping.board_id == board_id,
                StatusMapping.jira_status_name == jira_status_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_board(session: AsyncSession, board_id: str) -> list[StatusMapping]:
        result = await session.execute(
            select(StatusMapping).where(StatusMapping.board_id == board_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def upsert(
        session: AsyncSession, board_id: str, jira_status_name: str, normalized_status: str
    ) -> StatusMapping:
        mapping = await StatusMappingRepository.get(session, board_id, jira_status_name)
        if mapping is None:
            mapping = StatusMapping(
                board_id=board_id,
                jira_status_name=jira_status_name,
                normalized_status=normalized_status,
            )
            session.add(mapping)
        else:
            mapping.normalized_status = normalized_status
        await session.flush()
        return mapping


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------


class TicketRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, ticket_id: str) -> Ticket | None:
        result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_jira_id(session: AsyncSession, jira_id: str) -> Ticket | None:
        result = await session.execute(select(Ticket).where(Ticket.jira_id == jira_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_with_filters(
        session: AsyncSession,
        *,
        assignee_id: str | None = None,
        sprint_id: str | None = None,
        inferred_status: str | None = None,
        priority: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        authorized_jira_ids: list[str] | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Ticket]:
        stmt = select(Ticket)
        if assignee_id:
            stmt = stmt.where(Ticket.assignee_id == assignee_id)
        if sprint_id:
            stmt = stmt.where(Ticket.sprint_id == sprint_id)
        if inferred_status:
            stmt = stmt.where(Ticket.inferred_status == inferred_status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if date_from:
            stmt = stmt.where(Ticket.updated_at >= date_from)
        if date_to:
            stmt = stmt.where(Ticket.updated_at <= date_to)
        if authorized_jira_ids is not None and len(authorized_jira_ids) > 0:
            stmt = stmt.where(Ticket.jira_id.in_(authorized_jira_ids))
        stmt = stmt.order_by(Ticket.updated_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count_with_filters(
        session: AsyncSession,
        *,
        assignee_id: str | None = None,
        sprint_id: str | None = None,
        inferred_status: str | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Ticket)
        if assignee_id:
            stmt = stmt.where(Ticket.assignee_id == assignee_id)
        if sprint_id:
            stmt = stmt.where(Ticket.sprint_id == sprint_id)
        if inferred_status:
            stmt = stmt.where(Ticket.inferred_status == inferred_status)
        result = await session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def upsert(session: AsyncSession, jira_id: str, **kwargs: Any) -> Ticket:
        ticket = await TicketRepository.get_by_jira_id(session, jira_id)
        if ticket is None:
            ticket = Ticket(jira_id=jira_id, **kwargs)
            session.add(ticket)
        else:
            for key, value in kwargs.items():
                setattr(ticket, key, value)
            ticket.last_synced_at = _now()
        await session.flush()
        return ticket

    @staticmethod
    async def update_inferred_status(
        session: AsyncSession,
        ticket_id: str,
        inferred_status: str,
        reason: str,
    ) -> None:
        await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(
                inferred_status=inferred_status,
                inferred_status_reason=reason,
                inferred_status_updated_at=_now(),
            )
        )

    @staticmethod
    async def list_active(session: AsyncSession) -> list[Ticket]:
        """Return all tickets not in done/stale state — used for entity matching."""
        result = await session.execute(
            select(Ticket).where(
                Ticket.inferred_status.not_in(["stale", "completed_not_updated"])
            )
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# TicketSnapshot
# ---------------------------------------------------------------------------


class SnapshotRepository:
    @staticmethod
    async def create(session: AsyncSession, **kwargs: Any) -> TicketSnapshot:
        snapshot = TicketSnapshot(**kwargs)
        session.add(snapshot)
        await session.flush()
        return snapshot

    @staticmethod
    async def list_by_ticket(
        session: AsyncSession, ticket_id: str, limit: int = 50
    ) -> list[TicketSnapshot]:
        result = await session.execute(
            select(TicketSnapshot)
            .where(TicketSnapshot.ticket_id == ticket_id)
            .order_by(TicketSnapshot.snapshot_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_older_than(session: AsyncSession, cutoff: datetime) -> int:
        """Purge snapshots older than cutoff for the 12-month retention policy."""
        result = await session.execute(
            delete(TicketSnapshot).where(TicketSnapshot.snapshot_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


class TranscriptRepository:
    @staticmethod
    async def get_by_meeting_id(
        session: AsyncSession, copilot_meeting_id: str
    ) -> Transcript | None:
        result = await session.execute(
            select(Transcript).where(Transcript.copilot_meeting_id == copilot_meeting_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        session: AsyncSession, copilot_meeting_id: str, **kwargs: Any
    ) -> Transcript:
        transcript = await TranscriptRepository.get_by_meeting_id(session, copilot_meeting_id)
        if transcript is None:
            transcript = Transcript(copilot_meeting_id=copilot_meeting_id, **kwargs)
            session.add(transcript)
        else:
            for key, value in kwargs.items():
                setattr(transcript, key, value)
            transcript.last_synced_at = _now()
        await session.flush()
        return transcript

    @staticmethod
    async def list_unprocessed(session: AsyncSession) -> list[Transcript]:
        result = await session.execute(
            select(Transcript)
            .where(Transcript.processed_at.is_(None))
            .order_by(Transcript.started_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_processed(session: AsyncSession, transcript_id: str) -> None:
        await session.execute(
            update(Transcript)
            .where(Transcript.id == transcript_id)
            .values(processed_at=_now())
        )

    @staticmethod
    async def delete_older_than(session: AsyncSession, cutoff: datetime) -> int:
        """Purge transcripts older than cutoff for the 12-month retention policy."""
        result = await session.execute(
            delete(Transcript).where(Transcript.last_synced_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TranscriptMention
# ---------------------------------------------------------------------------


class MentionRepository:
    @staticmethod
    async def create(session: AsyncSession, **kwargs: Any) -> TranscriptMention:
        mention = TranscriptMention(**kwargs)
        session.add(mention)
        await session.flush()
        return mention

    @staticmethod
    async def list_by_transcript(
        session: AsyncSession, transcript_id: str
    ) -> list[TranscriptMention]:
        result = await session.execute(
            select(TranscriptMention)
            .where(TranscriptMention.transcript_id == transcript_id)
            .order_by(TranscriptMention.excerpt_timestamp_seconds.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_unresolved(session: AsyncSession) -> list[TranscriptMention]:
        result = await session.execute(
            select(TranscriptMention).where(TranscriptMention.match_type == "unresolved")
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_recent_by_ticket(
        session: AsyncSession, ticket_id: str, since: datetime
    ) -> list[TranscriptMention]:
        result = await session.execute(
            select(TranscriptMention)
            .where(
                TranscriptMention.ticket_id == ticket_id,
                TranscriptMention.created_at >= since,
            )
            .order_by(TranscriptMention.created_at.desc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# UpdateSuggestion
# ---------------------------------------------------------------------------


class SuggestionRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, suggestion_id: str) -> UpdateSuggestion | None:
        result = await session.execute(
            select(UpdateSuggestion).where(UpdateSuggestion.id == suggestion_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, **kwargs: Any) -> UpdateSuggestion:
        suggestion = UpdateSuggestion(**kwargs)
        session.add(suggestion)
        await session.flush()
        return suggestion

    @staticmethod
    async def list_with_filters(
        session: AsyncSession,
        *,
        approval_state: str | None = "pending",
        confidence_tier: str | None = None,
        ticket_jira_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UpdateSuggestion]:
        stmt = select(UpdateSuggestion)
        if approval_state:
            stmt = stmt.where(UpdateSuggestion.approval_state == approval_state)
        if confidence_tier:
            stmt = stmt.where(UpdateSuggestion.confidence_tier == confidence_tier)
        if ticket_jira_id:
            stmt = stmt.join(Ticket, UpdateSuggestion.ticket_id == Ticket.id).where(
                Ticket.jira_id == ticket_jira_id
            )
        stmt = stmt.order_by(UpdateSuggestion.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_state(
        session: AsyncSession, suggestion_id: str, state: str, **kwargs: Any
    ) -> UpdateSuggestion | None:
        await session.execute(
            update(UpdateSuggestion)
            .where(UpdateSuggestion.id == suggestion_id)
            .values(approval_state=state, **kwargs)
        )
        return await SuggestionRepository.get_by_id(session, suggestion_id)


# ---------------------------------------------------------------------------
# AuditEntry
# ---------------------------------------------------------------------------


class AuditRepository:
    @staticmethod
    async def create(session: AsyncSession, **kwargs: Any) -> AuditEntry:
        entry = AuditEntry(**kwargs)
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def get_last_sync_event(session: AsyncSession) -> AuditEntry | None:
        result = await session.execute(
            select(AuditEntry)
            .where(AuditEntry.event_type.in_(["sync_completed", "sync_failed"]))
            .order_by(AuditEntry.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_with_filters(
        session: AsyncSession,
        *,
        ticket_jira_id: str | None = None,
        event_type: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEntry]:
        stmt = select(AuditEntry)
        if event_type:
            stmt = stmt.where(AuditEntry.event_type == event_type)
        if from_dt:
            stmt = stmt.where(AuditEntry.created_at >= from_dt)
        if to_dt:
            stmt = stmt.where(AuditEntry.created_at <= to_dt)
        if ticket_jira_id:
            stmt = stmt.join(Ticket, AuditEntry.ticket_id == Ticket.id).where(
                Ticket.jira_id == ticket_jira_id
            )
        stmt = stmt.order_by(AuditEntry.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count_with_filters(
        session: AsyncSession,
        *,
        ticket_jira_id: str | None = None,
        event_type: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(AuditEntry)
        if event_type:
            stmt = stmt.where(AuditEntry.event_type == event_type)
        if from_dt:
            stmt = stmt.where(AuditEntry.created_at >= from_dt)
        if to_dt:
            stmt = stmt.where(AuditEntry.created_at <= to_dt)
        if ticket_jira_id:
            stmt = stmt.join(Ticket, AuditEntry.ticket_id == Ticket.id).where(
                Ticket.jira_id == ticket_jira_id
            )
        result = await session.execute(stmt)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# GitHubRepository
# ---------------------------------------------------------------------------


class GitHubRepository:
    @staticmethod
    async def upsert_repo(
        session: AsyncSession,
        org: str,
        name: str,
        full_name: str,
        default_branch: str,
    ) -> GitHubRepo:
        result = await session.execute(
            select(GitHubRepo).where(GitHubRepo.full_name == full_name)
        )
        repo = result.scalar_one_or_none()
        if repo is None:
            repo = GitHubRepo(
                org=org,
                name=name,
                full_name=full_name,
                default_branch=default_branch,
                is_active=True,
            )
            session.add(repo)
        else:
            repo.default_branch = default_branch
            repo.is_active = True
        await session.flush()
        return repo

    @staticmethod
    async def update_repo_synced_at(
        session: AsyncSession, repo_id: str, synced_at: datetime
    ) -> None:
        await session.execute(
            update(GitHubRepo)
            .where(GitHubRepo.id == repo_id)
            .values(last_synced_at=synced_at)
        )

    @staticmethod
    async def upsert_commit(
        session: AsyncSession,
        repo_id: str,
        sha: str,
        message: str,
        author_login: str | None,
        author_name: str | None,
        author_email: str | None,
        committed_at: datetime,
        branch: str | None,
        url: str | None,
    ) -> GitHubCommit:
        result = await session.execute(
            select(GitHubCommit).where(GitHubCommit.sha == sha)
        )
        commit = result.scalar_one_or_none()
        if commit is None:
            commit = GitHubCommit(
                repo_id=repo_id,
                sha=sha,
                message=message,
                author_login=author_login,
                author_name=author_name,
                author_email=author_email,
                committed_at=committed_at,
                branch=branch,
                url=url,
            )
            session.add(commit)
            await session.flush()
        return commit

    @staticmethod
    async def upsert_pr(
        session: AsyncSession,
        repo_id: str,
        pr_number: int,
        title: str,
        body: str | None,
        state: str,
        author_login: str | None,
        head_branch: str | None,
        base_branch: str | None,
        opened_at: datetime,
        closed_at: datetime | None,
        merged_at: datetime | None,
        url: str | None,
    ) -> GitHubPullRequest:
        result = await session.execute(
            select(GitHubPullRequest).where(
                GitHubPullRequest.repo_id == repo_id,
                GitHubPullRequest.pr_number == pr_number,
            )
        )
        pr = result.scalar_one_or_none()
        if pr is None:
            pr = GitHubPullRequest(
                repo_id=repo_id,
                pr_number=pr_number,
                title=title,
                body=body,
                state=state,
                author_login=author_login,
                head_branch=head_branch,
                base_branch=base_branch,
                opened_at=opened_at,
                closed_at=closed_at,
                merged_at=merged_at,
                url=url,
                last_synced_at=_now(),
            )
            session.add(pr)
        else:
            pr.title = title
            pr.state = state
            pr.closed_at = closed_at
            pr.merged_at = merged_at
            pr.last_synced_at = _now()
        await session.flush()
        return pr

    @staticmethod
    async def upsert_jira_link(
        session: AsyncSession,
        source_type: str,
        jira_key: str,
        commit_sha: str | None = None,
        pr_id: str | None = None,
    ) -> GitHubJiraLink:
        stmt = select(GitHubJiraLink).where(
            GitHubJiraLink.source_type == source_type,
            GitHubJiraLink.jira_key == jira_key,
        )
        if commit_sha:
            stmt = stmt.where(GitHubJiraLink.commit_sha == commit_sha)
        if pr_id:
            stmt = stmt.where(GitHubJiraLink.pr_id == pr_id)

        result = await session.execute(stmt)
        link = result.scalar_one_or_none()
        if link is not None:
            return link

        ticket_result = await session.execute(
            select(Ticket).where(Ticket.jira_id == jira_key)
        )
        ticket = ticket_result.scalar_one_or_none()

        link = GitHubJiraLink(
            source_type=source_type,
            commit_sha=commit_sha,
            pr_id=pr_id,
            jira_key=jira_key,
            ticket_id=ticket.id if ticket else None,
        )
        session.add(link)
        await session.flush()
        return link

    @staticmethod
    async def resolve_forward_jira_links(session: AsyncSession) -> int:
        result = await session.execute(
            select(GitHubJiraLink).where(GitHubJiraLink.ticket_id.is_(None))
        )
        unresolved = list(result.scalars().all())
        resolved = 0
        for link in unresolved:
            ticket_result = await session.execute(
                select(Ticket).where(Ticket.jira_id == link.jira_key)
            )
            ticket = ticket_result.scalar_one_or_none()
            if ticket:
                link.ticket_id = ticket.id
                resolved += 1
        return resolved

    @staticmethod
    async def list_repos(session: AsyncSession) -> list[tuple[GitHubRepo, int, int]]:
        """Return list of (repo, commit_count, open_pr_count) tuples."""
        repos_result = await session.execute(
            select(GitHubRepo).where(GitHubRepo.is_active.is_(True)).order_by(GitHubRepo.full_name)
        )
        repos = list(repos_result.scalars().all())
        out = []
        for repo in repos:
            commit_count_result = await session.execute(
                select(func.count()).select_from(GitHubCommit).where(GitHubCommit.repo_id == repo.id)
            )
            commit_count = commit_count_result.scalar_one()
            open_pr_count_result = await session.execute(
                select(func.count())
                .select_from(GitHubPullRequest)
                .where(GitHubPullRequest.repo_id == repo.id, GitHubPullRequest.state == "open")
            )
            open_pr_count = open_pr_count_result.scalar_one()
            out.append((repo, commit_count, open_pr_count))
        return out

    @staticmethod
    async def list_commits(
        session: AsyncSession,
        repo_full_name: str | None = None,
        jira_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[GitHubCommit, list[str]]], int]:
        """Return (commits with jira_keys, total_count)."""
        stmt = select(GitHubCommit).join(GitHubRepo, GitHubCommit.repo_id == GitHubRepo.id)
        if repo_full_name:
            stmt = stmt.where(GitHubRepo.full_name == repo_full_name)
        if jira_key:
            stmt = stmt.where(
                GitHubCommit.sha.in_(
                    select(GitHubJiraLink.commit_sha).where(
                        GitHubJiraLink.source_type == "commit",
                        GitHubJiraLink.jira_key == jira_key,
                    )
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = stmt.order_by(GitHubCommit.committed_at.desc()).offset(offset).limit(limit)
        commits_result = await session.execute(stmt)
        commits = list(commits_result.scalars().all())

        out = []
        for commit in commits:
            keys_result = await session.execute(
                select(GitHubJiraLink.jira_key).where(
                    GitHubJiraLink.source_type == "commit",
                    GitHubJiraLink.commit_sha == commit.sha,
                )
            )
            keys = [row[0] for row in keys_result]
            out.append((commit, keys))
        return out, total

    @staticmethod
    async def list_prs(
        session: AsyncSession,
        repo_full_name: str | None = None,
        state: str | None = None,
        jira_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[GitHubPullRequest, list[str]]], int]:
        """Return (prs with jira_keys, total_count)."""
        stmt = select(GitHubPullRequest).join(
            GitHubRepo, GitHubPullRequest.repo_id == GitHubRepo.id
        )
        if repo_full_name:
            stmt = stmt.where(GitHubRepo.full_name == repo_full_name)
        if state:
            stmt = stmt.where(GitHubPullRequest.state == state)
        if jira_key:
            stmt = stmt.where(
                GitHubPullRequest.id.in_(
                    select(GitHubJiraLink.pr_id).where(
                        GitHubJiraLink.source_type == "pr",
                        GitHubJiraLink.jira_key == jira_key,
                    )
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = stmt.order_by(GitHubPullRequest.opened_at.desc()).offset(offset).limit(limit)
        prs_result = await session.execute(stmt)
        prs = list(prs_result.scalars().all())

        out = []
        for pr in prs:
            keys_result = await session.execute(
                select(GitHubJiraLink.jira_key).where(
                    GitHubJiraLink.source_type == "pr",
                    GitHubJiraLink.pr_id == pr.id,
                )
            )
            keys = [row[0] for row in keys_result]
            out.append((pr, keys))
        return out, total
