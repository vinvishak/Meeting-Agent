"""
Sprint forecaster and bottleneck detector.

  forecast_current_sprint() — risk assessment for the active sprint
  find_bottlenecks()        — tickets stuck beyond team average per stage
"""

import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging_config import get_logger
from src.storage.models import NormalizedStatus, Sprint, SprintState, Ticket, TicketSnapshot
from src.velocity.calculator import SprintMetrics, _aware, _days_between

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class SprintForecast:
    sprint_id: str
    name: str
    points_completed: float
    points_remaining: float
    days_remaining: int
    forecast: str          # "on_track" | "at_risk" | "off_track"
    forecast_reason: str


@dataclass
class BottleneckTicket:
    jira_id: str
    title: str
    stuck_in_status: str
    days_in_status: float
    team_avg_days_in_status: float
    overage_days: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Current sprint forecast
# ---------------------------------------------------------------------------


async def forecast_current_sprint(
    session: AsyncSession,
    board_id: str,
    historical_metrics: list[SprintMetrics],
) -> SprintForecast | None:
    """
    Forecast completion risk for the currently active sprint on a board.

    Returns None if no active sprint is found.
    """
    result = await session.execute(
        select(Sprint).where(
            Sprint.board_id == board_id,
            Sprint.state == SprintState.active.value,
        )
    )
    active_sprint = result.scalar_one_or_none()
    if active_sprint is None:
        return None

    now = _utcnow()
    start = _aware(active_sprint.start_date) if active_sprint.start_date else now
    end = _aware(active_sprint.end_date) if active_sprint.end_date else now + timedelta(days=14)

    total_days = max((end - start).days, 1)
    elapsed_days = max((now - start).days, 0)
    days_remaining = max((end - now).days, 0)
    pct_elapsed = elapsed_days / total_days

    # Story points in current sprint
    tickets_result = await session.execute(
        select(Ticket).where(Ticket.sprint_id == active_sprint.id)
    )
    tickets = list(tickets_result.scalars().all())

    done = [t for t in tickets if t.normalized_status == NormalizedStatus.done.value]
    has_points = any(t.story_points for t in tickets)
    total_points = sum(t.story_points or 1.0 for t in tickets)
    completed_points = sum(t.story_points or 1.0 for t in done)
    remaining_points = max(total_points - completed_points, 0.0)
    pct_completed = completed_points / total_points if total_points > 0 else 0.0

    # Historical average velocity
    historical_velocities = [m.velocity for m in historical_metrics]
    avg_velocity = statistics.mean(historical_velocities) if historical_velocities else total_points

    # Risk assessment
    # at_risk: < 40% complete with > 60% time elapsed
    if pct_elapsed >= 0.60 and pct_completed < 0.40:
        forecast = "off_track"
        reason = (
            f"{pct_elapsed * 100:.0f}% of sprint duration elapsed; "
            f"only {pct_completed * 100:.0f}% of {'points' if has_points else 'tickets'} completed."
        )
    elif pct_elapsed >= 0.40 and pct_completed < 0.30:
        forecast = "at_risk"
        reason = (
            f"{pct_elapsed * 100:.0f}% of sprint duration elapsed; "
            f"only {pct_completed * 100:.0f}% of {'points' if has_points else 'tickets'} completed. "
            f"Pace is below historical average of {avg_velocity:.1f}."
        )
    else:
        forecast = "on_track"
        reason = (
            f"{pct_completed * 100:.0f}% of {'points' if has_points else 'tickets'} completed "
            f"with {days_remaining} days remaining."
        )

    return SprintForecast(
        sprint_id=active_sprint.id,
        name=active_sprint.name,
        points_completed=round(completed_points, 1),
        points_remaining=round(remaining_points, 1),
        days_remaining=days_remaining,
        forecast=forecast,
        forecast_reason=reason,
    )


# ---------------------------------------------------------------------------
# Bottleneck detection
# ---------------------------------------------------------------------------


async def find_bottlenecks(
    session: AsyncSession,
    board_id: str,
) -> list[BottleneckTicket]:
    """
    Find tickets that have been in their current status longer than the
    team's historical average for that status.
    """
    # All tickets on this board (via sprint)
    result = await session.execute(
        select(Ticket)
        .join(Sprint, Ticket.sprint_id == Sprint.id)
        .where(Sprint.board_id == board_id)
        .where(Ticket.normalized_status.not_in([NormalizedStatus.done.value]))
    )
    tickets = list(result.scalars().all())

    if not tickets:
        return []

    now = _utcnow()

    # Compute per-status average days across recent snapshots (team baseline)
    snaps_result = await session.execute(
        select(TicketSnapshot)
        .join(Ticket, TicketSnapshot.ticket_id == Ticket.id)
        .join(Sprint, Ticket.sprint_id == Sprint.id)
        .where(Sprint.board_id == board_id)
    )
    all_snaps = list(snaps_result.scalars().all())

    # Group consecutive same-status snapshots to compute time in status
    # Simplified: use time between snapshot transitions
    status_durations: dict[str, list[float]] = {}
    ticket_snaps: dict[str, list[TicketSnapshot]] = {}
    for snap in all_snaps:
        ticket_snaps.setdefault(snap.ticket_id, []).append(snap)

    for _tid, snaps in ticket_snaps.items():
        snaps.sort(key=lambda s: s.snapshot_at)
        for i, snap in enumerate(snaps):
            if i == 0:
                continue
            prev = snaps[i - 1]
            if prev.normalized_status == snap.normalized_status:
                continue
            duration = _days_between(_aware(prev.snapshot_at), _aware(snap.snapshot_at))
            status_durations.setdefault(prev.normalized_status, []).append(duration)

    avg_by_status: dict[str, float] = {
        status: statistics.mean(durations)
        for status, durations in status_durations.items()
        if durations
    }

    bottlenecks: list[BottleneckTicket] = []
    for ticket in tickets:
        current_status = ticket.normalized_status
        team_avg = avg_by_status.get(current_status)
        if team_avg is None:
            continue

        # Estimate days in current status from last snapshot transition
        snaps = sorted(ticket_snaps.get(ticket.id, []), key=lambda s: s.snapshot_at, reverse=True)
        days_in_status = 0.0
        for snap in snaps:
            if snap.normalized_status != current_status:
                days_in_status = _days_between(_aware(snap.snapshot_at), now)
                break
        else:
            # No prior different-status snapshot — use ticket updated_at
            days_in_status = _days_between(_aware(ticket.updated_at), now)

        overage = days_in_status - team_avg
        if overage > 0:
            bottlenecks.append(
                BottleneckTicket(
                    jira_id=ticket.jira_id,
                    title=ticket.title,
                    stuck_in_status=current_status,
                    days_in_status=round(days_in_status, 1),
                    team_avg_days_in_status=round(team_avg, 1),
                    overage_days=round(overage, 1),
                )
            )

    bottlenecks.sort(key=lambda b: b.overage_days, reverse=True)
    return bottlenecks
