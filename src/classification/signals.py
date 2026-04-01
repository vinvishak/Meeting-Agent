"""
Signal extraction for multi-signal ticket status classification.

Each ticket is evaluated against four weighted signals (per research.md §4):

  Signal                              Weight
  ─────────────────────────────────── ──────
  Jira status = in_progress           3
  Transcript mention within 2 days    2
  Jira activity within 5 days         1   (comment or status transition)
  Status transition within 5 days     1   (separate from comment activity)
  Blocker flag set                    override → Blocked

The classifier (signals.py) builds a SignalSet; classifier.py applies the
6-rule decision logic.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, computed_field

from src.storage.models import NormalizedStatus, Ticket, TranscriptMention

# ------------------------------------------------------------------
# Constants (weights from research.md §4)
# ------------------------------------------------------------------

_W_JIRA_STATUS_IN_PROGRESS = 3
_W_TRANSCRIPT_MENTION = 2
_W_JIRA_ACTIVITY = 1  # Jira updated_at within 5 days (covers comments)
_W_STATUS_TRANSITION = 1  # explicit status change within 5 days

_MENTION_WINDOW_DAYS = 2
_ACTIVITY_WINDOW_DAYS = 5


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ------------------------------------------------------------------
# SignalSet model
# ------------------------------------------------------------------


class SignalSet(BaseModel):
    """Structured container for all classification signals for one ticket."""

    jira_status_weight: int = 0
    recent_transcript_mention_weight: int = 0
    recent_activity_weight: int = 0     # Jira updated_at within 5 days
    recent_transition_weight: int = 0   # status changed within 5 days
    has_blocker: bool = False
    last_activity_at: datetime | None = None

    @computed_field  # type: ignore[misc]
    @property
    def total_score(self) -> int:
        return (
            self.jira_status_weight
            + self.recent_transcript_mention_weight
            + self.recent_activity_weight
            + self.recent_transition_weight
        )


# ------------------------------------------------------------------
# Extraction
# ------------------------------------------------------------------


def extract_signals(
    ticket: Ticket,
    normalized_status: str,
    recent_mentions: list[TranscriptMention],
    previous_jira_status: str | None,
    previous_status_changed_at: datetime | None,
    stale_threshold_days: int,
) -> SignalSet:
    """
    Build a SignalSet for *ticket* from all available signals.

    Args:
        ticket: The current Ticket ORM record (updated_at reflects last Jira activity).
        normalized_status: Current normalized status string (NormalizedStatus value).
        recent_mentions: TranscriptMentions for this ticket created within the last
            `_MENTION_WINDOW_DAYS` days (caller filters).
        previous_jira_status: The jira_status from the most recent TicketSnapshot
            (None if no prior snapshot exists).
        previous_status_changed_at: snapshot_at of the most recent snapshot whose
            jira_status differs from the current ticket.jira_status. None if no
            status transition occurred.
        stale_threshold_days: Number of days with no activity before → stale.
    """
    now = _utcnow()
    updated_at = _aware(ticket.updated_at)

    # ---- Blocker override ----------------------------------------
    has_blocker = (
        normalized_status == NormalizedStatus.blocked.value
        or any(
            "blocked" in (m.mention_intent or "").lower() or "blocker" in (m.excerpt or "").lower()
            for m in recent_mentions
        )
    )

    # ---- Signal: Jira status = in_progress -----------------------
    jira_status_weight = (
        _W_JIRA_STATUS_IN_PROGRESS
        if normalized_status in (NormalizedStatus.in_progress.value, NormalizedStatus.review.value)
        else 0
    )

    # ---- Signal: transcript mention within 2 days ----------------
    mention_cutoff = now - timedelta(days=_MENTION_WINDOW_DAYS)
    recent_transcript_mention_weight = (
        _W_TRANSCRIPT_MENTION
        if any(_aware(m.created_at) >= mention_cutoff for m in recent_mentions)
        else 0
    )

    # ---- Signal: Jira activity (updated_at) within 5 days --------
    activity_cutoff = now - timedelta(days=_ACTIVITY_WINDOW_DAYS)
    recent_activity_weight = _W_JIRA_ACTIVITY if updated_at >= activity_cutoff else 0

    # ---- Signal: explicit status transition within 5 days --------
    recent_transition_weight = 0
    if previous_status_changed_at is not None:
        trans_at = _aware(previous_status_changed_at)
        if trans_at >= activity_cutoff:
            recent_transition_weight = _W_STATUS_TRANSITION

    # ---- Last-activity marker (for stale detection) --------------
    last_activity_at: datetime | None = updated_at
    if recent_mentions:
        latest_mention = max(_aware(m.created_at) for m in recent_mentions)
        if latest_mention > last_activity_at:
            last_activity_at = latest_mention

    return SignalSet(
        jira_status_weight=jira_status_weight,
        recent_transcript_mention_weight=recent_transcript_mention_weight,
        recent_activity_weight=recent_activity_weight,
        recent_transition_weight=recent_transition_weight,
        has_blocker=has_blocker,
        last_activity_at=last_activity_at,
    )
