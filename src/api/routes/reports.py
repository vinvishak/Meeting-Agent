"""
Reporting routes (T040 + T041).

  GET /api/v1/reports/sprint-health      — per-team health summary
  GET /api/v1/reports/executive-summary  — portfolio + initiative rollups
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.repository import AuditRepository
from src.velocity.aggregator import aggregate_initiatives, aggregate_sprint_health

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TeamHealthOut(BaseModel):
    board_id: str
    team_name: str
    sprint_name: str
    health: str
    active_blockers: int
    forecast: str
    completion_pct: float


class SprintHealthResponse(BaseModel):
    teams: list[TeamHealthOut]
    generated_at: datetime
    data_freshness: datetime | None = None


class InitiativeOut(BaseModel):
    name: str
    completion_pct: float
    blocked_tickets: int
    at_risk: bool
    estimated_completion_date: str | None = None


class ExecutiveSummaryResponse(BaseModel):
    summary_date: str
    teams: list[TeamHealthOut]
    initiatives: list[InitiativeOut]
    overall_velocity_trend: str
    data_freshness: datetime | None = None


# ---------------------------------------------------------------------------
# GET /reports/sprint-health  (T040)
# ---------------------------------------------------------------------------


@router.get("/reports/sprint-health", response_model=SprintHealthResponse)
async def sprint_health(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> SprintHealthResponse:
    authorized_keys: list[str] = getattr(request.state, "project_keys", [])
    health_list = await aggregate_sprint_health(session, authorized_keys or None)
    last_sync = await AuditRepository.get_last_sync_event(session)

    return SprintHealthResponse(
        teams=[
            TeamHealthOut(
                board_id=h.board_id,
                team_name=h.team_name,
                sprint_name=h.sprint_name,
                health=h.health,
                active_blockers=h.active_blockers,
                forecast=h.forecast,
                completion_pct=h.completion_pct,
            )
            for h in health_list
        ],
        generated_at=datetime.now(UTC),
        data_freshness=last_sync.created_at if last_sync else None,
    )


# ---------------------------------------------------------------------------
# GET /reports/executive-summary  (T041)
# ---------------------------------------------------------------------------


@router.get("/reports/executive-summary", response_model=ExecutiveSummaryResponse)
async def executive_summary(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> ExecutiveSummaryResponse:
    authorized_keys: list[str] = getattr(request.state, "project_keys", [])
    health_list = await aggregate_sprint_health(session, authorized_keys or None)
    initiatives = await aggregate_initiatives(session)
    last_sync = await AuditRepository.get_last_sync_event(session)

    # Overall velocity trend: majority vote across team trends
    from src.velocity.calculator import compute_sprint_metrics

    trends: list[str] = []
    for h in health_list:
        try:
            report = await compute_sprint_metrics(session, h.board_id, sprint_count=6)
            trends.append(report.trend)
        except Exception:
            pass

    trend_counts: dict[str, int] = {}
    for t in trends:
        trend_counts[t] = trend_counts.get(t, 0) + 1
    overall_trend = max(trend_counts, key=lambda k: trend_counts[k]) if trend_counts else "stable"

    return ExecutiveSummaryResponse(
        summary_date=datetime.now(UTC).date().isoformat(),
        teams=[
            TeamHealthOut(
                board_id=h.board_id,
                team_name=h.team_name,
                sprint_name=h.sprint_name,
                health=h.health,
                active_blockers=h.active_blockers,
                forecast=h.forecast,
                completion_pct=h.completion_pct,
            )
            for h in health_list
        ],
        initiatives=[
            InitiativeOut(
                name=i.name,
                completion_pct=i.completion_pct,
                blocked_tickets=i.blocked_tickets,
                at_risk=i.at_risk,
                estimated_completion_date=i.estimated_completion_date,
            )
            for i in initiatives
        ],
        overall_velocity_trend=overall_trend,
        data_freshness=last_sync.created_at if last_sync else None,
    )
