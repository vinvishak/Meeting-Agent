"""
Read-only Claude tool schemas and implementations for natural language queries (T042).

Six tools exposed to Claude via tool-use:
  get_active_tickets       — filtered list of current tickets
  get_blocked_tickets      — tickets in blocked inferred status
  get_velocity             — velocity metrics for a team/sprint range
  get_sprint_risk          — tickets at risk in the current sprint
  get_overloaded_engineers — engineers with above-average ticket load
  get_transcript_jira_gaps — tickets mentioned in meetings but not updated
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import InferredStatus, NormalizedStatus, Sprint, Ticket, TranscriptMention

# ---------------------------------------------------------------------------
# Tool schemas for Claude tool-use
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_active_tickets",
        "description": "Returns a list of active (non-done, non-stale) tickets, optionally filtered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Optional Jira board ID filter"},
                "assignee_display_name": {"type": "string", "description": "Optional engineer name filter"},
                "inferred_status": {
                    "type": "string",
                    "enum": ["officially_in_progress", "likely_in_progress", "blocked", "stale", "completed_not_updated"],
                    "description": "Optional inferred status filter",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_blocked_tickets",
        "description": "Returns all tickets currently inferred as blocked, with reasons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Optional Jira board ID filter"},
            },
            "required": [],
        },
    },
    {
        "name": "get_velocity",
        "description": "Returns velocity metrics (story points per sprint, trend) for a team.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Jira board identifier"},
                "sprint_count": {"type": "integer", "description": "Number of past sprints (default 6)"},
            },
            "required": ["board_id"],
        },
    },
    {
        "name": "get_sprint_risk",
        "description": "Returns tickets in the current active sprint that are at risk of not completing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Jira board identifier"},
            },
            "required": ["board_id"],
        },
    },
    {
        "name": "get_overloaded_engineers",
        "description": "Returns engineers who have significantly more active tickets than the team average.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Optional Jira board ID filter"},
            },
            "required": [],
        },
    },
    {
        "name": "get_transcript_jira_gaps",
        "description": "Returns tickets discussed in recent meeting transcripts but not updated in Jira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {"type": "integer", "description": "How many days back to look for transcripts (default 7)"},
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def get_active_tickets(
    session: AsyncSession,
    board_id: str | None = None,
    assignee_display_name: str | None = None,
    inferred_status: str | None = None,
    authorized_jira_ids: list[str] | None = None,
) -> list[dict]:
    stmt = select(Ticket).where(
        Ticket.inferred_status.not_in([InferredStatus.stale.value])
    )
    if inferred_status:
        stmt = stmt.where(Ticket.inferred_status == inferred_status)
    if board_id:
        stmt = stmt.join(Sprint, Ticket.sprint_id == Sprint.id).where(Sprint.board_id == board_id)
    result = await session.execute(stmt.limit(100))
    tickets = list(result.scalars().all())

    if assignee_display_name:
        tickets = [t for t in tickets if t.assignee and assignee_display_name.lower() in t.assignee.display_name.lower()]

    return [
        {
            "jira_id": t.jira_id,
            "title": t.title,
            "inferred_status": t.inferred_status,
            "jira_status": t.jira_status,
            "assignee": t.assignee.display_name if t.assignee else None,
            "story_points": t.story_points,
            "priority": t.priority,
        }
        for t in tickets
    ]


async def get_blocked_tickets(
    session: AsyncSession,
    board_id: str | None = None,
) -> list[dict]:
    stmt = select(Ticket).where(Ticket.inferred_status == InferredStatus.blocked.value)
    if board_id:
        stmt = stmt.join(Sprint, Ticket.sprint_id == Sprint.id).where(Sprint.board_id == board_id)
    result = await session.execute(stmt)
    tickets = list(result.scalars().all())
    return [
        {
            "jira_id": t.jira_id,
            "title": t.title,
            "assignee": t.assignee.display_name if t.assignee else None,
            "reason": t.inferred_status_reason,
        }
        for t in tickets
    ]


async def get_velocity(
    session: AsyncSession,
    board_id: str,
    sprint_count: int = 6,
) -> dict:
    from src.velocity.calculator import compute_sprint_metrics

    report = await compute_sprint_metrics(session, board_id, sprint_count)
    return {
        "board_id": board_id,
        "average_velocity": report.average_velocity,
        "trend": report.trend,
        "sprint_count": len(report.sprints),
        "sprints": [
            {"name": m.name, "velocity": m.velocity, "throughput_tickets": m.throughput_tickets}
            for m in report.sprints
        ],
    }


async def get_sprint_risk(session: AsyncSession, board_id: str) -> dict:
    from src.velocity.calculator import compute_sprint_metrics
    from src.velocity.forecaster import forecast_current_sprint

    report = await compute_sprint_metrics(session, board_id)
    forecast = await forecast_current_sprint(session, board_id, report.sprints)
    if forecast is None:
        return {"board_id": board_id, "active_sprint": None}

    # Get tickets not yet done in active sprint
    sprint_result = await session.execute(
        select(Sprint).where(Sprint.board_id == board_id, Sprint.state == "active")
    )
    sprint = sprint_result.scalar_one_or_none()
    at_risk_tickets: list[dict] = []
    if sprint:
        tickets_result = await session.execute(
            select(Ticket).where(
                Ticket.sprint_id == sprint.id,
                Ticket.normalized_status != NormalizedStatus.done.value,
            )
        )
        at_risk_tickets = [
            {"jira_id": t.jira_id, "title": t.title, "inferred_status": t.inferred_status, "story_points": t.story_points}
            for t in tickets_result.scalars().all()
        ]

    return {
        "board_id": board_id,
        "active_sprint": forecast.name,
        "forecast": forecast.forecast,
        "forecast_reason": forecast.forecast_reason,
        "days_remaining": forecast.days_remaining,
        "at_risk_tickets": at_risk_tickets,
    }


async def get_overloaded_engineers(
    session: AsyncSession,
    board_id: str | None = None,
) -> list[dict]:
    stmt = select(Ticket).where(
        Ticket.inferred_status.not_in([InferredStatus.stale.value, "completed_not_updated"])
    )
    if board_id:
        stmt = stmt.join(Sprint, Ticket.sprint_id == Sprint.id).where(Sprint.board_id == board_id)
    result = await session.execute(stmt)
    tickets = list(result.scalars().all())

    engineer_load: dict[str, dict[str, Any]] = {}
    for t in tickets:
        if not t.assignee_id:
            continue
        if t.assignee_id not in engineer_load:
            engineer_load[t.assignee_id] = {
                "display_name": t.assignee.display_name if t.assignee else "Unknown",
                "active_tickets": 0,
                "story_points": 0.0,
                "blocked_tickets": 0,
            }
        engineer_load[t.assignee_id]["active_tickets"] += 1
        engineer_load[t.assignee_id]["story_points"] += t.story_points or 0.0
        if t.inferred_status == InferredStatus.blocked.value:
            engineer_load[t.assignee_id]["blocked_tickets"] += 1

    if not engineer_load:
        return []

    import statistics
    avg_tickets = statistics.mean(d["active_tickets"] for d in engineer_load.values())
    avg_points = statistics.mean(d["story_points"] for d in engineer_load.values())

    overloaded = [
        {**data, "engineer_id": eid}
        for eid, data in engineer_load.items()
        if data["active_tickets"] > avg_tickets * 1.5 or data["story_points"] > avg_points * 1.5
    ]
    overloaded.sort(key=lambda x: x["story_points"], reverse=True)
    return overloaded


async def get_transcript_jira_gaps(
    session: AsyncSession,
    days_back: int = 7,
    authorized_jira_ids: list[str] | None = None,
) -> list[dict]:
    """Return tickets mentioned in recent transcripts but not updated since the meeting."""
    cutoff = datetime.now(UTC) - timedelta(days=days_back)

    result = await session.execute(
        select(TranscriptMention)
        .join(Ticket, TranscriptMention.ticket_id == Ticket.id)
        .where(
            TranscriptMention.created_at >= cutoff,
            TranscriptMention.ticket_id.is_not(None),
        )
    )
    mentions = list(result.scalars().all())

    gaps: list[dict] = []
    seen_tickets: set[str] = set()

    for mention in mentions:
        if not mention.ticket or mention.ticket_id in seen_tickets:
            continue
        ticket = mention.ticket

        def _aware(dt: datetime) -> datetime:
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt

        mention_time = _aware(mention.created_at)
        ticket_updated = _aware(ticket.updated_at)

        # Gap: ticket was mentioned AFTER its last Jira update
        if mention_time > ticket_updated:
            seen_tickets.add(mention.ticket_id)
            gaps.append({
                "jira_id": ticket.jira_id,
                "title": ticket.title,
                "last_jira_update": ticket_updated.isoformat(),
                "last_mentioned_at": mention_time.isoformat(),
                "mentioned_by": mention.speaker_name,
                "excerpt": mention.excerpt[:200],
            })

    return gaps


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_DISPATCH: dict[str, Any] = {
    "get_active_tickets": get_active_tickets,
    "get_blocked_tickets": get_blocked_tickets,
    "get_velocity": get_velocity,
    "get_sprint_risk": get_sprint_risk,
    "get_overloaded_engineers": get_overloaded_engineers,
    "get_transcript_jira_gaps": get_transcript_jira_gaps,
}


async def dispatch_tool(
    tool_name: str,
    tool_input: dict,
    session: AsyncSession,
) -> Any:
    """Execute the named tool with the given input dict."""
    fn = _TOOL_DISPATCH.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await fn(session, **tool_input)
    except Exception as exc:
        return {"error": str(exc)}
