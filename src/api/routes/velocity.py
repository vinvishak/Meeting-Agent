"""
Velocity routes.

  GET /api/v1/velocity     — sprint history + trend + forecast (T035)
  GET /api/v1/bottlenecks  — tickets stuck beyond team average (T036)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.repository import AuditRepository
from src.velocity.calculator import compute_sprint_metrics
from src.velocity.forecaster import find_bottlenecks, forecast_current_sprint

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SprintSummary(BaseModel):
    sprint_id: str
    name: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    committed_points: float | None = None
    completed_points: float
    velocity: float
    cycle_time_avg_days: float | None = None
    lead_time_avg_days: float | None = None
    throughput_tickets: int


class CurrentSprintForecast(BaseModel):
    sprint_id: str
    name: str
    points_completed: float
    points_remaining: float
    days_remaining: int
    forecast: str
    forecast_reason: str


class VelocityResponse(BaseModel):
    board_id: str
    sprints: list[SprintSummary]
    trend: str
    average_velocity: float
    current_sprint_forecast: CurrentSprintForecast | None = None
    data_freshness: datetime | None = None


class BottleneckTicket(BaseModel):
    jira_id: str
    title: str
    stuck_in_status: str
    days_in_status: float
    team_avg_days_in_status: float
    overage_days: float


class BottlenecksResponse(BaseModel):
    board_id: str
    bottlenecks: list[BottleneckTicket]
    data_freshness: datetime | None = None


# ---------------------------------------------------------------------------
# GET /velocity
# ---------------------------------------------------------------------------


@router.get("/velocity", response_model=VelocityResponse)
async def get_velocity(
    board_id: str = Query(..., description="Jira board identifier"),
    sprint_count: int = Query(6, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
) -> VelocityResponse:
    report = await compute_sprint_metrics(session, board_id, sprint_count)

    forecast = await forecast_current_sprint(session, board_id, report.sprints)

    last_sync = await AuditRepository.get_last_sync_event(session)

    sprints_out = [
        SprintSummary(
            sprint_id=m.sprint_id,
            name=m.name,
            start_date=m.start_date,
            end_date=m.end_date,
            committed_points=m.committed_points,
            completed_points=m.completed_points,
            velocity=m.velocity,
            cycle_time_avg_days=m.cycle_time_avg_days,
            lead_time_avg_days=m.lead_time_avg_days,
            throughput_tickets=m.throughput_tickets,
        )
        for m in report.sprints
    ]

    forecast_out: CurrentSprintForecast | None = None
    if forecast:
        forecast_out = CurrentSprintForecast(
            sprint_id=forecast.sprint_id,
            name=forecast.name,
            points_completed=forecast.points_completed,
            points_remaining=forecast.points_remaining,
            days_remaining=forecast.days_remaining,
            forecast=forecast.forecast,
            forecast_reason=forecast.forecast_reason,
        )

    return VelocityResponse(
        board_id=board_id,
        sprints=sprints_out,
        trend=report.trend,
        average_velocity=report.average_velocity,
        current_sprint_forecast=forecast_out,
        data_freshness=last_sync.created_at if last_sync else None,
    )


# ---------------------------------------------------------------------------
# GET /bottlenecks
# ---------------------------------------------------------------------------


@router.get("/bottlenecks", response_model=BottlenecksResponse)
async def get_bottlenecks(
    board_id: str = Query(..., description="Jira board identifier"),
    session: AsyncSession = Depends(get_db),
) -> BottlenecksResponse:
    bottlenecks = await find_bottlenecks(session, board_id)

    last_sync = await AuditRepository.get_last_sync_event(session)

    return BottlenecksResponse(
        board_id=board_id,
        bottlenecks=[
            BottleneckTicket(
                jira_id=b.jira_id,
                title=b.title,
                stuck_in_status=b.stuck_in_status,
                days_in_status=b.days_in_status,
                team_avg_days_in_status=b.team_avg_days_in_status,
                overage_days=b.overage_days,
            )
            for b in bottlenecks
        ],
        data_freshness=last_sync.created_at if last_sync else None,
    )
