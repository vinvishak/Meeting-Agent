"""
Update suggester.

Converts MentionCandidate records (from transcript_analyzer) into
UpdateSuggestion ORM records:

  1. Derives update_type and proposed_value from mention_intent
  2. Assigns confidence_tier from combined match + intent confidence
  3. Detects conflicting statements across speakers on the same ticket
  4. Auto-applies high-confidence non-conflicted suggestions when
     AUTO_APPLY_ENABLED=true (T032)

All writes happen inside the caller's AsyncSession; the caller is
responsible for committing.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.transcript_analyzer import MentionCandidate
from src.config import get_settings
from src.logging_config import get_logger
from src.storage.models import (
    ApprovalState,
    AuditEventType,
    ConfidenceTier,
    MentionIntent,
    TranscriptMention,
    UpdateType,
)
from src.storage.repository import AuditRepository, MentionRepository, SuggestionRepository

if TYPE_CHECKING:
    from src.ingestion.jira_client import JiraMCPClient

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HIGH_THRESHOLD = 0.90
_MEDIUM_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_confidence(match_confidence: float, intent_confidence: float) -> float:
    """Combined confidence: match quality weighted more than intent classification."""
    return round(0.6 * match_confidence + 0.4 * intent_confidence, 4)


def _derive_tier(confidence: float) -> str:
    if confidence >= _HIGH_THRESHOLD:
        return ConfidenceTier.high.value
    if confidence >= _MEDIUM_THRESHOLD:
        return ConfidenceTier.medium.value
    return ConfidenceTier.low.value


def _derive_update_type_and_value(
    candidate: MentionCandidate,
) -> tuple[str, dict] | None:
    """
    Map mention_intent to (update_type, proposed_value).

    Returns None for intents that don't naturally map to an actionable Jira update.
    """
    intent = candidate.mention_intent
    excerpt = candidate.excerpt

    if intent == MentionIntent.completion.value:
        return (UpdateType.status_transition.value, {"new_status": "done"})

    if intent == MentionIntent.blocker.value:
        return (UpdateType.set_blocked.value, {"blocked": True, "reason": excerpt[:300]})

    if intent == MentionIntent.progress_update.value:
        return (UpdateType.add_comment.value, {"comment": f"[Meeting note] {excerpt[:500]}"})

    if intent == MentionIntent.ownership_change.value:
        # Best-effort: include speaker as proposed assignee
        return (UpdateType.update_assignee.value, {"assignee_display_name": candidate.speaker_name})

    if intent == MentionIntent.eta_change.value:
        return (UpdateType.add_comment.value, {"comment": f"[ETA update from meeting] {excerpt[:500]}"})

    if intent == MentionIntent.dependency.value:
        return (UpdateType.add_comment.value, {"comment": f"[Dependency noted in meeting] {excerpt[:500]}"})

    if intent == MentionIntent.future_intent.value:
        return (UpdateType.add_comment.value, {"comment": f"[Future intent from meeting] {excerpt[:500]}"})

    # ambiguous → add_comment with low confidence note
    if intent == MentionIntent.ambiguous.value:
        return (UpdateType.add_comment.value, {"comment": f"[Possible update from meeting — verify intent] {excerpt[:500]}"})

    return None


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _detect_conflicts(
    candidates: list[MentionCandidate],
    ticket_id: str,
) -> tuple[bool, str | None]:
    """
    Detect if multiple speakers make contradictory statements about the same ticket.

    A conflict is when two different speakers with intent=completion and
    intent=blocker (or completion and progress_update hinting at not done)
    appear for the same ticket.
    """
    relevant = [c for c in candidates if c.ticket_id == ticket_id]
    if len(relevant) < 2:
        return False, None

    speakers_by_intent: dict[str, list[str]] = {}
    for c in relevant:
        speakers_by_intent.setdefault(c.mention_intent, []).append(c.speaker_name)

    # Conflict: someone says done AND someone says blocked
    if MentionIntent.completion.value in speakers_by_intent and MentionIntent.blocker.value in speakers_by_intent:
        details = (
            f"Conflicting statements: "
            f"{', '.join(speakers_by_intent[MentionIntent.completion.value])} indicated completion, "
            f"while {', '.join(speakers_by_intent[MentionIntent.blocker.value])} indicated a blocker."
        )
        return True, details

    # Conflict: two different speakers both say completion (could be a double-update)
    if len(speakers_by_intent.get(MentionIntent.completion.value, [])) > 1:
        speakers = speakers_by_intent[MentionIntent.completion.value]
        details = f"Multiple speakers indicated completion: {', '.join(speakers)}. Manual verification recommended."
        return True, details

    return False, None


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


async def create_suggestions_from_mentions(
    candidates: list[MentionCandidate],
    session: AsyncSession,
    transcript_id: str,
    jira_client: "JiraMCPClient | None" = None,
) -> list[str]:
    """
    Persist TranscriptMention and UpdateSuggestion records from analyzed candidates.

    Returns a list of created UpdateSuggestion IDs.
    """
    settings = get_settings()
    auto_apply = settings.auto_apply_enabled
    suggestion_ids: list[str] = []

    for candidate in candidates:
        # 1. Persist the TranscriptMention
        try:
            mention = await MentionRepository.create(
                session,
                transcript_id=transcript_id,
                ticket_id=candidate.ticket_id or None,
                speaker_name=candidate.speaker_name,
                speaker_engineer_id=candidate.speaker_engineer_id,
                excerpt=candidate.excerpt,
                excerpt_timestamp_seconds=candidate.excerpt_timestamp_seconds,
                match_type=candidate.match_type,
                match_confidence=candidate.match_confidence,
                mention_intent=candidate.mention_intent,
            )
        except Exception as exc:
            logger.warning("Failed to persist mention for %r: %s", candidate.jira_id, exc)
            continue

        # 2. Skip unresolved mentions — no suggestion to create
        if not candidate.ticket_id:
            continue

        # 3. Derive update type and proposed value
        update_info = _derive_update_type_and_value(candidate)
        if update_info is None:
            continue

        update_type, proposed_value = update_info

        # 4. Compute combined confidence and tier
        confidence = _derive_confidence(candidate.match_confidence, candidate.intent_confidence)
        tier = _derive_tier(confidence)

        # 5. Conflict detection
        conflict_flag, conflict_details = _detect_conflicts(candidates, candidate.ticket_id)

        # 6. Create suggestion
        try:
            suggestion = await SuggestionRepository.create(
                session,
                transcript_mention_id=mention.id,
                ticket_id=candidate.ticket_id,
                update_type=update_type,
                proposed_value=proposed_value,
                confidence_score=confidence,
                confidence_tier=tier,
                approval_state=ApprovalState.pending.value,
                conflict_flag=conflict_flag,
                conflict_details=conflict_details,
            )
        except Exception as exc:
            logger.warning("Failed to create suggestion for %r: %s", candidate.jira_id, exc)
            continue

        suggestion_ids.append(suggestion.id)

        # 7. Write audit entry for suggestion creation
        await AuditRepository.create(
            session,
            event_type=AuditEventType.suggestion_created.value,
            ticket_id=candidate.ticket_id,
            update_suggestion_id=suggestion.id,
            transcript_mention_id=mention.id,
            reasoning=(
                f"Suggestion created from transcript mention. "
                f"Intent: {candidate.mention_intent}, confidence: {confidence:.2f}, tier: {tier}."
            ),
            signal_inputs={
                "match_type": candidate.match_type,
                "match_confidence": candidate.match_confidence,
                "intent": candidate.mention_intent,
                "intent_confidence": candidate.intent_confidence,
                "confidence_score": confidence,
                "confidence_tier": tier,
                "conflict_flag": conflict_flag,
                "excerpt": candidate.excerpt[:200],
            },
        )

        # 8. Auto-apply (T032): high confidence + no conflict + AUTO_APPLY_ENABLED
        if (
            auto_apply
            and tier == ConfidenceTier.high.value
            and not conflict_flag
            and jira_client is not None
            and candidate.jira_id
        ):
            await _auto_apply(suggestion, mention, candidate, jira_client, session)

    return suggestion_ids


async def _auto_apply(
    suggestion: "UpdateSuggestion",  # type: ignore[name-defined]  # noqa: F821
    mention: TranscriptMention,
    candidate: MentionCandidate,
    jira_client: "JiraMCPClient",
    session: AsyncSession,
) -> None:
    """Apply a high-confidence suggestion directly to Jira."""
    try:
        fields = _build_jira_fields(suggestion.update_type, suggestion.proposed_value)
        success = await jira_client.update_issue(candidate.jira_id, fields)
        if not success:
            logger.warning("Auto-apply failed for suggestion %s on %s", suggestion.id, candidate.jira_id)
            return

        now = datetime.now(UTC)
        await SuggestionRepository.update_state(
            session,
            suggestion.id,
            ApprovalState.auto_applied.value,
            applied_at=now,
        )

        await AuditRepository.create(
            session,
            event_type=AuditEventType.suggestion_auto_applied.value,
            ticket_id=candidate.ticket_id,
            update_suggestion_id=suggestion.id,
            transcript_mention_id=mention.id,
            reasoning=(
                f"Auto-applied: {suggestion.update_type} to {candidate.jira_id}. "
                f"Confidence: {suggestion.confidence_score:.2f}. "
                f"Excerpt: {candidate.excerpt[:200]}"
            ),
            signal_inputs={
                "confidence_score": suggestion.confidence_score,
                "match_type": candidate.match_type,
                "update_type": suggestion.update_type,
                "proposed_value": suggestion.proposed_value,
                "excerpt": candidate.excerpt[:200],
            },
        )
        logger.info("Auto-applied suggestion %s to %s", suggestion.id, candidate.jira_id)
    except Exception as exc:
        logger.error("Auto-apply raised exception for %s: %s", candidate.jira_id, exc, exc_info=True)


def _build_jira_fields(update_type: str, proposed_value: dict) -> dict:
    """Convert proposed_value to Jira API field format."""
    if update_type == UpdateType.status_transition.value:
        new_status = proposed_value.get("new_status", "")
        return {"transition": {"name": new_status}}
    if update_type == UpdateType.add_comment.value:
        return {"comment": proposed_value.get("comment", "")}
    if update_type == UpdateType.update_assignee.value:
        return {"assignee": {"displayName": proposed_value.get("assignee_display_name", "")}}
    if update_type == UpdateType.set_blocked.value:
        return {"flagged": proposed_value.get("blocked", False)}
    if update_type == UpdateType.update_due_date.value:
        return {"duedate": proposed_value.get("due_date", "")}
    return proposed_value
