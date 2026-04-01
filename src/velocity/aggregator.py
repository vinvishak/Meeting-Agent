"""
Sprint health and initiative aggregators (T038 + T039).

  aggregate_sprint_health()   — per-team health, blockers, forecast, completion
  aggregate_initiatives()     — initiative-level rollups from ticket labels
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging_config import get_logger
from src.storage.models import NormalizedStatus, Sprint, SprintState, Ticket
from src.velocity.calculator import compute_sprint_metrics
from src.velocity.forecaster import forecast_current_sprint

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class TeamHealth:
    board_id: str
    team_name: str
    sprint_name: str
    health: str          # "on_track" | "at_risk" | "off_track"
    active_blockers: int
    forecast: str
    completion_pct: float


@dataclass
class InitiativeRollup:
    name: str
    completion_pct: float
    blocked_tickets: int
    at_risk: bool
    estimated_completion_date: str | None  # ISO date string


# ---------------------------------------------------------------------------
# Sprint health aggregator (T038)
# ---------------------------------------------------------------------------


async def aggregate_sprint_health(
    session: AsyncSession,
    authorized_board_ids: list[str] | None = None,
) -> list[TeamHealth]:
    """
    Compute health for every board visible to the requesting user.

    If authorized_board_ids is None or empty, all boards are included.
    """
    # Discover boards from Sprint table
    result = await session.execute(select(Sprint.board_id).distinct())
    all_board_ids = [row[0] for row in result]

    board_ids = [b for b in all_board_ids if b in set(authorized_board_ids)] if authorized_board_ids else all_board_ids

    health_list: list[TeamHealth] = []

    for board_id in board_ids:
        # Load active sprint
        sprint_result = await session.execute(
            select(Sprint).where(
                Sprint.board_id == board_id,
                Sprint.state == SprintState.active.value,
            )
        )
        active_sprint = sprint_result.scalar_one_or_none()
        if active_sprint is None:
            continue

        # Count active blockers
        blockers_result = await session.execute(
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.sprint_id == active_sprint.id,
                Ticket.inferred_status == "blocked",
            )
        )
        active_blockers = blockers_result.scalar_one() or 0

        # Completion percentage
        all_tickets_result = await session.execute(
            select(Ticket).where(Ticket.sprint_id == active_sprint.id)
        )
        all_tickets = list(all_tickets_result.scalars().all())
        total = len(all_tickets)
        done = sum(1 for t in all_tickets if t.normalized_status == NormalizedStatus.done.value)
        completion_pct = round((done / total * 100) if total > 0 else 0.0, 1)

        # Get forecast
        report = await compute_sprint_metrics(session, board_id, sprint_count=6)
        forecast = await forecast_current_sprint(session, board_id, report.sprints)
        forecast_str = forecast.forecast if forecast else "unknown"

        # Health = worst of blockers, forecast, and completion
        if active_blockers > 0 or forecast_str == "off_track":
            health = "off_track"
        elif forecast_str == "at_risk" or completion_pct < 30:
            health = "at_risk"
        else:
            health = "on_track"

        health_list.append(
            TeamHealth(
                board_id=board_id,
                team_name=board_id,  # Board ID is used as team name (no separate team entity)
                sprint_name=active_sprint.name,
                health=health,
                active_blockers=active_blockers,
                forecast=forecast_str,
                completion_pct=completion_pct,
            )
        )

    return health_list


# ---------------------------------------------------------------------------
# Initiative aggregator (T039)
# ---------------------------------------------------------------------------


async def aggregate_initiatives(session: AsyncSession) -> list[InitiativeRollup]:
    """
    Group tickets by initiative label and compute rollup metrics.

    Initiative labels are ticket labels that don't match common non-initiative
    patterns (i.e., any label that appears on 2+ tickets is treated as an initiative).
    """
    # Load all non-done tickets with their labels
    result = await session.execute(select(Ticket))
    all_tickets = list(result.scalars().all())

    if not all_tickets:
        return []

    # Collect all labels with their frequency
    label_counts: dict[str, int] = {}
    for ticket in all_tickets:
        for label in (ticket.labels or []):
            label_counts[label] = label_counts.get(label, 0) + 1

    # Consider any label that appears on 2+ tickets as a potential initiative
    initiative_labels = [label for label, count in label_counts.items() if count >= 2]

    if not initiative_labels:
        return []

    rollups: list[InitiativeRollup] = []

    for label in sorted(initiative_labels):
        tickets_in_initiative = [t for t in all_tickets if label in (t.labels or [])]
        total = len(tickets_in_initiative)
        if total == 0:
            continue

        done = sum(1 for t in tickets_in_initiative if t.normalized_status == NormalizedStatus.done.value)
        blocked = sum(1 for t in tickets_in_initiative if t.inferred_status == "blocked")
        completion_pct = round(done / total * 100, 1)
        at_risk = blocked > 0 or completion_pct < 50

        # Rough completion date estimate: extrapolate from current velocity
        # Use the most recent updated_at across in-progress tickets
        in_progress = [
            t for t in tickets_in_initiative
            if t.normalized_status in (NormalizedStatus.in_progress.value, NormalizedStatus.review.value)
        ]
        estimated_completion: str | None = None
        remaining = total - done
        if remaining > 0 and in_progress:
            # Very rough estimate: remaining tickets / (done / elapsed days since oldest created)
            oldest_created = min(t.created_at for t in tickets_in_initiative)
            now = datetime.now(UTC)
            elapsed_days = max((now - _aware(oldest_created)).days, 1)
            daily_rate = done / elapsed_days if done > 0 else 0.1
            days_to_completion = remaining / daily_rate
            estimated_completion = (now + timedelta(days=days_to_completion)).date().isoformat()

        rollups.append(
            InitiativeRollup(
                name=label,
                completion_pct=completion_pct,
                blocked_tickets=blocked,
                at_risk=at_risk,
                estimated_completion_date=estimated_completion,
            )
        )

    return rollups


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
