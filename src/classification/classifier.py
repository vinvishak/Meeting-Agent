"""
Multi-signal ticket status classifier.

Applies the 6-rule decision logic from research.md §4 to a SignalSet and
returns an (InferredStatus, reason_string) pair that is suitable for storing
in Ticket.inferred_status / Ticket.inferred_status_reason.

Decision order (rules evaluated top-to-bottom, first match wins):
  1. Any blocker signal          → blocked
  2. Jira done + no contrary evidence → completed_not_updated  (if ticket
     was done but transcript says otherwise) OR officially done
  3. Total score ≥ 4             → officially_in_progress
  4. Total score 2–3             → likely_in_progress
  5. score < 2 AND last activity > stale_threshold_days → stale
  6. Else                        → likely_in_progress  (low-confidence)
"""

from datetime import UTC, datetime, timedelta

from src.classification.signals import SignalSet
from src.storage.models import InferredStatus, NormalizedStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _signal_summary(signals: SignalSet) -> str:
    parts: list[str] = []
    if signals.jira_status_weight:
        parts.append(f"Jira status is in progress (weight {signals.jira_status_weight})")
    if signals.recent_transcript_mention_weight:
        parts.append(f"mentioned in transcript recently (weight {signals.recent_transcript_mention_weight})")
    if signals.recent_activity_weight:
        parts.append(f"Jira activity within 5 days (weight {signals.recent_activity_weight})")
    if signals.recent_transition_weight:
        parts.append(f"status transition within 5 days (weight {signals.recent_transition_weight})")
    return "; ".join(parts) if parts else "no active signals"


def classify(
    normalized_status: str,
    signals: SignalSet,
    stale_threshold_days: int,
    has_contrary_transcript: bool = False,
) -> tuple[str, str]:
    """
    Classify a ticket using the 6-rule logic from research.md §4.

    Args:
        normalized_status: Current NormalizedStatus value for the ticket.
        signals: SignalSet produced by signals.extract_signals().
        stale_threshold_days: Days of inactivity before a ticket is stale.
        has_contrary_transcript: True when Jira says 'done' but a recent
            transcript mention with completion intent contradicts this.

    Returns:
        (inferred_status_value, reason_string)
    """
    now = _utcnow()

    # ------------------------------------------------------------------ #
    # Rule 1: Blocker override
    # ------------------------------------------------------------------ #
    if signals.has_blocker:
        return (
            InferredStatus.blocked.value,
            f"Blocked signal detected ({_signal_summary(signals)}).",
        )

    # ------------------------------------------------------------------ #
    # Rule 2: Official Jira status = done
    # ------------------------------------------------------------------ #
    if normalized_status == NormalizedStatus.done.value:
        if has_contrary_transcript:
            return (
                InferredStatus.completed_not_updated.value,
                "Jira shows Done but a recent meeting transcript suggests the ticket may still be active. "
                "Manual verification recommended.",
            )
        return (
            InferredStatus.officially_in_progress.value
            if signals.total_score >= 4
            else InferredStatus.completed_not_updated.value,
            "Jira status is Done.",
        )

    # ------------------------------------------------------------------ #
    # Rule 3: High-confidence in progress (score ≥ 4)
    # ------------------------------------------------------------------ #
    if signals.total_score >= 4:
        return (
            InferredStatus.officially_in_progress.value,
            f"Strong multi-signal evidence of active work (score={signals.total_score}): "
            f"{_signal_summary(signals)}.",
        )

    # ------------------------------------------------------------------ #
    # Rule 4: Moderate confidence (score 2–3)
    # ------------------------------------------------------------------ #
    if signals.total_score >= 2:
        return (
            InferredStatus.likely_in_progress.value,
            f"Moderate evidence of active work (score={signals.total_score}): "
            f"{_signal_summary(signals)}.",
        )

    # ------------------------------------------------------------------ #
    # Rule 5: Stale — low score AND no recent activity
    # ------------------------------------------------------------------ #
    stale_cutoff = now - timedelta(days=stale_threshold_days)
    last_active: datetime | None = signals.last_activity_at
    if last_active is None or _aware(last_active) < stale_cutoff:
        days_inactive = (
            (now - _aware(last_active)).days if last_active else stale_threshold_days
        )
        return (
            InferredStatus.stale.value,
            f"No activity detected for {days_inactive} day(s) "
            f"(threshold: {stale_threshold_days} days). {_signal_summary(signals)}.",
        )

    # ------------------------------------------------------------------ #
    # Rule 6: Low-confidence fallback
    # ------------------------------------------------------------------ #
    return (
        InferredStatus.likely_in_progress.value,
        f"Low-confidence: insufficient signals (score={signals.total_score}). "
        f"{_signal_summary(signals)}.",
    )
