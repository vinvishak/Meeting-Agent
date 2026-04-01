"""
Sprint velocity calculator.

Computes per-sprint metrics from TicketSnapshot and Sprint data:
  - velocity        : completed story points (falls back to ticket count)
  - throughput      : number of completed tickets
  - cycle_time_avg  : avg days from first in-progress transition → done
  - lead_time_avg   : avg days from ticket.created_at → done
  - planned vs completed delta

Usage:
    metrics = await compute_sprint_metrics(session, board_id, sprint_count=6)
"""

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging_config import get_logger
from src.storage.models import NormalizedStatus, Sprint, Ticket, TicketSnapshot

logger = get_logger(__name__)

_HIGH_VARIANCE_THRESHOLD = 0.50  # coefficient of variation above which we flag variance


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class SprintMetrics:
    sprint_id: str
    jira_sprint_id: str
    name: str
    start_date: datetime | None
    end_date: datetime | None
    committed_points: float | None
    completed_points: float
    velocity: float  # = completed_points (or ticket count fallback)
    throughput_tickets: int
    cycle_time_avg_days: float | None
    lead_time_avg_days: float | None
    high_variance: bool = False


@dataclass
class VelocityReport:
    board_id: str
    sprints: list[SprintMetrics] = field(default_factory=list)
    average_velocity: float = 0.0
    trend: str = "stable"  # "improving" | "declining" | "stable"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _days_between(a: datetime, b: datetime) -> float:
    return abs((_aware(b) - _aware(a)).total_seconds()) / 86400.0


def _classify_trend(velocities: list[float]) -> str:
    """Classify velocity trend over the last N sprints."""
    if len(velocities) < 3:
        return "stable"
    first_half = velocities[: len(velocities) // 2]
    second_half = velocities[len(velocities) // 2 :]
    avg_first = statistics.mean(first_half)
    avg_second = statistics.mean(second_half)
    if avg_first == 0:
        return "stable"
    change = (avg_second - avg_first) / avg_first
    if change >= 0.10:
        return "improving"
    if change <= -0.10:
        return "declining"
    return "stable"


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


async def compute_sprint_metrics(
    session: AsyncSession,
    board_id: str,
    sprint_count: int = 6,
) -> VelocityReport:
    """
    Compute velocity metrics for the last `sprint_count` closed sprints on a board.
    """
    # Load closed sprints ordered by end date desc
    result = await session.execute(
        select(Sprint)
        .where(Sprint.board_id == board_id, Sprint.state == "closed")
        .order_by(Sprint.end_date.desc())
        .limit(sprint_count)
    )
    sprints = list(result.scalars().all())

    if not sprints:
        logger.debug("No closed sprints found for board %s", board_id)
        return VelocityReport(board_id=board_id)

    sprint_metrics: list[SprintMetrics] = []

    for sprint in sprints:
        # All tickets in this sprint
        tickets_result = await session.execute(
            select(Ticket).where(Ticket.sprint_id == sprint.id)
        )
        tickets = list(tickets_result.scalars().all())

        if not tickets:
            sprint_metrics.append(
                SprintMetrics(
                    sprint_id=sprint.id,
                    jira_sprint_id=sprint.jira_sprint_id,
                    name=sprint.name,
                    start_date=_aware(sprint.start_date) if sprint.start_date else None,
                    end_date=_aware(sprint.end_date) if sprint.end_date else None,
                    committed_points=sprint.committed_points,
                    completed_points=0.0,
                    velocity=0.0,
                    throughput_tickets=0,
                    cycle_time_avg_days=None,
                    lead_time_avg_days=None,
                )
            )
            continue

        done_tickets = [t for t in tickets if t.normalized_status == NormalizedStatus.done.value]
        completed_points = sum(t.story_points or 0.0 for t in done_tickets)
        has_story_points = any(t.story_points for t in tickets)
        velocity = completed_points if has_story_points else float(len(done_tickets))

        # Cycle time: for each done ticket, find first in_progress snapshot → done snapshot
        cycle_times: list[float] = []
        lead_times: list[float] = []

        for ticket in done_tickets:
            snaps_result = await session.execute(
                select(TicketSnapshot)
                .where(TicketSnapshot.ticket_id == ticket.id)
                .order_by(TicketSnapshot.snapshot_at.asc())
            )
            snaps = list(snaps_result.scalars().all())

            first_in_progress: datetime | None = None
            last_done: datetime | None = None
            for snap in snaps:
                if snap.normalized_status == NormalizedStatus.in_progress.value and first_in_progress is None:
                    first_in_progress = _aware(snap.snapshot_at)
                if snap.normalized_status == NormalizedStatus.done.value:
                    last_done = _aware(snap.snapshot_at)

            if first_in_progress and last_done:
                cycle_times.append(_days_between(first_in_progress, last_done))

            created_at = _aware(ticket.created_at)
            done_at = last_done or (_aware(sprint.end_date) if sprint.end_date else _utcnow())
            lead_times.append(_days_between(created_at, done_at))

        cycle_time_avg = statistics.mean(cycle_times) if cycle_times else None
        lead_time_avg = statistics.mean(lead_times) if lead_times else None

        sprint_metrics.append(
            SprintMetrics(
                sprint_id=sprint.id,
                jira_sprint_id=sprint.jira_sprint_id,
                name=sprint.name,
                start_date=_aware(sprint.start_date) if sprint.start_date else None,
                end_date=_aware(sprint.end_date) if sprint.end_date else None,
                committed_points=sprint.committed_points,
                completed_points=completed_points,
                velocity=velocity,
                throughput_tickets=len(done_tickets),
                cycle_time_avg_days=round(cycle_time_avg, 2) if cycle_time_avg is not None else None,
                lead_time_avg_days=round(lead_time_avg, 2) if lead_time_avg is not None else None,
            )
        )

    # Flag high-variance sprints
    velocities = [m.velocity for m in sprint_metrics]
    if len(velocities) >= 3:
        avg_v = statistics.mean(velocities)
        stdev_v = statistics.stdev(velocities)
        cv = stdev_v / avg_v if avg_v > 0 else 0
        if cv >= _HIGH_VARIANCE_THRESHOLD:
            # Flag all sprints in a high-variance sequence
            for m in sprint_metrics:
                m.high_variance = True

    average_velocity = statistics.mean(velocities) if velocities else 0.0
    trend = _classify_trend(list(reversed(velocities)))  # oldest → newest

    return VelocityReport(
        board_id=board_id,
        sprints=list(reversed(sprint_metrics)),  # oldest first
        average_velocity=round(average_velocity, 2),
        trend=trend,
    )
