"""
Ticket routes — GET /api/v1/tickets and GET /api/v1/tickets/{jira_id}.

Both endpoints enforce auth middleware project scoping via
`request.state.project_keys` (empty list = all projects authorised).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.models import Ticket
from src.storage.repository import AuditRepository, TicketRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AssigneeOut(BaseModel):
    id: str
    display_name: str


class SprintOut(BaseModel):
    id: str
    name: str


class TicketSummary(BaseModel):
    jira_id: str
    title: str
    assignee: AssigneeOut | None = None
    sprint: SprintOut | None = None
    jira_status: str
    normalized_status: str
    inferred_status: str
    inferred_status_reason: str
    priority: str | None = None
    story_points: float | None = None
    updated_at: datetime


class TicketsResponse(BaseModel):
    tickets: list[TicketSummary]
    total: int
    data_freshness: datetime | None = None


class InferredStatusSignals(BaseModel):
    jira_status_weight: int = 0
    recent_transcript_mention_weight: int = 0
    recent_activity_weight: int = 0
    recent_transition_weight: int = 0


class TicketDetail(BaseModel):
    jira_id: str
    title: str
    description: str | None = None
    assignee: AssigneeOut | None = None
    sprint: SprintOut | None = None
    jira_status: str
    normalized_status: str
    inferred_status: str
    inferred_status_reason: str
    inferred_status_signals: InferredStatusSignals
    story_points: float | None = None
    labels: list[str] = []
    linked_issues: list[str] = []
    created_at: datetime
    updated_at: datetime
    due_date: str | None = None
    data_freshness: datetime | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _authorized_project_keys(request: Request) -> list[str]:
    """Return the list of authorised Jira project keys from auth middleware state."""
    return getattr(request.state, "project_keys", [])


def _project_prefixes_for_ticket(jira_id: str, authorized_keys: list[str]) -> bool:
    """
    Return True if the ticket's Jira project key is in the authorized set.
    An empty authorized_keys list means all projects are permitted.
    """
    if not authorized_keys:
        return True
    prefix = jira_id.split("-")[0] if "-" in jira_id else jira_id
    return prefix.upper() in {k.upper() for k in authorized_keys}


def _build_assignee(ticket: Ticket) -> AssigneeOut | None:
    if ticket.assignee:
        return AssigneeOut(id=ticket.assignee.id, display_name=ticket.assignee.display_name)
    return None


def _build_sprint(ticket: Ticket) -> SprintOut | None:
    if ticket.sprint:
        return SprintOut(id=ticket.sprint.id, name=ticket.sprint.name)
    return None


# ---------------------------------------------------------------------------
# GET /tickets
# ---------------------------------------------------------------------------


@router.get("/tickets", response_model=TicketsResponse)
async def list_tickets(
    request: Request,
    team: str | None = Query(None, description="Filter by project key / team"),
    sprint_id: str | None = Query(None),
    assignee_id: str | None = Query(None),
    project: str | None = Query(None, description="Filter by Jira project key"),
    priority: str | None = Query(None),
    inferred_status: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> TicketsResponse:
    authorized_keys = _authorized_project_keys(request)

    # Combine "team" and "project" — both are treated as project key filters
    project_filter = project or team

    tickets = await TicketRepository.list_with_filters(
        session,
        assignee_id=assignee_id,
        sprint_id=sprint_id,
        inferred_status=inferred_status,
        priority=priority,
        date_from=date_from,
        date_to=date_to,
        limit=limit + offset,  # fetch a bit more then slice; count done below
        offset=0,
    )

    # Apply auth scoping and optional project filter in Python (avoids
    # complex join in the repository layer for MVP)
    filtered: list[Ticket] = []
    for t in tickets:
        if not _project_prefixes_for_ticket(t.jira_id, authorized_keys):
            continue
        if project_filter:
            prefix = t.jira_id.split("-")[0].upper() if "-" in t.jira_id else t.jira_id.upper()
            if prefix != project_filter.upper():
                continue
        filtered.append(t)

    total = len(filtered)
    page = filtered[offset: offset + limit]

    # Data freshness = most recent sync_completed audit entry
    last_sync = await AuditRepository.get_last_sync_event(session)
    data_freshness = last_sync.created_at if last_sync else None

    ticket_out = [
        TicketSummary(
            jira_id=t.jira_id,
            title=t.title,
            assignee=_build_assignee(t),
            sprint=_build_sprint(t),
            jira_status=t.jira_status,
            normalized_status=t.normalized_status,
            inferred_status=t.inferred_status,
            inferred_status_reason=t.inferred_status_reason,
            priority=t.priority,
            story_points=t.story_points,
            updated_at=t.updated_at,
        )
        for t in page
    ]

    return TicketsResponse(tickets=ticket_out, total=total, data_freshness=data_freshness)


# ---------------------------------------------------------------------------
# GET /tickets/{jira_id}
# ---------------------------------------------------------------------------


@router.get("/tickets/{jira_id}", response_model=TicketDetail)
async def get_ticket(
    jira_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    authorized_keys = _authorized_project_keys(request)

    ticket = await TicketRepository.get_by_jira_id(session, jira_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {jira_id!r} not found.")

    if not _project_prefixes_for_ticket(ticket.jira_id, authorized_keys):
        raise HTTPException(status_code=404, detail=f"Ticket {jira_id!r} not found.")

    # Retrieve latest status_inferred audit entry for the signal breakdown
    audit_entries = await AuditRepository.list_with_filters(
        session,
        ticket_jira_id=jira_id,
        event_type="status_inferred",
        limit=1,
    )
    signals = InferredStatusSignals()
    if audit_entries:
        si = audit_entries[0].signal_inputs or {}
        signals = InferredStatusSignals(
            jira_status_weight=si.get("jira_status_weight", 0),
            recent_transcript_mention_weight=si.get("recent_transcript_mention_weight", 0),
            recent_activity_weight=si.get("recent_activity_weight", 0),
            recent_transition_weight=si.get("recent_transition_weight", 0),
        )

    last_sync = await AuditRepository.get_last_sync_event(session)

    return TicketDetail(
        jira_id=ticket.jira_id,
        title=ticket.title,
        description=ticket.description,
        assignee=_build_assignee(ticket),
        sprint=_build_sprint(ticket),
        jira_status=ticket.jira_status,
        normalized_status=ticket.normalized_status,
        inferred_status=ticket.inferred_status,
        inferred_status_reason=ticket.inferred_status_reason,
        inferred_status_signals=signals,
        story_points=ticket.story_points,
        labels=ticket.labels or [],
        linked_issues=ticket.linked_issue_ids or [],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        due_date=ticket.due_date.isoformat() if ticket.due_date else None,
        data_freshness=last_sync.created_at if last_sync else None,
    )
