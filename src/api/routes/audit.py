"""
Audit route (T045).

  GET /api/v1/audit — admin-only access to the immutable event log.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.repository import AuditRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TicketRef(BaseModel):
    jira_id: str
    title: str


class AuditEntryOut(BaseModel):
    id: str
    event_type: str
    ticket: TicketRef | None = None
    reasoning: str
    signal_inputs: dict
    created_at: datetime


class AuditResponse(BaseModel):
    entries: list[AuditEntryOut]
    total: int


# ---------------------------------------------------------------------------
# GET /audit
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=AuditResponse)
async def list_audit_entries(
    request: Request,
    ticket_jira_id: str | None = Query(None),
    event_type: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> AuditResponse:
    # Admin-only: require a session token that grants admin rights.
    # The MVP auth middleware attaches is_admin to request.state when the
    # token matches a known admin identity.  Absent that field, deny access.
    is_admin: bool = getattr(request.state, "is_admin", False)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Audit log access requires admin privileges.")

    entries = await AuditRepository.list_with_filters(
        session,
        ticket_jira_id=ticket_jira_id,
        event_type=event_type,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit + offset,
        offset=0,
    )
    total = await AuditRepository.count_with_filters(
        session,
        ticket_jira_id=ticket_jira_id,
        event_type=event_type,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    page = entries[offset: offset + limit]

    return AuditResponse(
        entries=[
            AuditEntryOut(
                id=e.id,
                event_type=e.event_type,
                ticket=TicketRef(jira_id=e.ticket.jira_id, title=e.ticket.title) if e.ticket else None,
                reasoning=e.reasoning,
                signal_inputs=e.signal_inputs or {},
                created_at=e.created_at,
            )
            for e in page
        ],
        total=total,
    )
