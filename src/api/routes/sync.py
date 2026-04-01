"""
Sync status route — GET /api/v1/sync/status.

Returns the timestamp and outcome of the most recent sync cycle so that
operators can quickly verify data freshness from the quickstart troubleshooting
guide (quickstart.md §5).
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.repository import AuditRepository

router = APIRouter()


class SyncStatusResponse(BaseModel):
    state: str  # "idle" | "failed" | "unknown"
    last_sync_at: datetime | None = None
    last_sync_event_type: str | None = None
    last_sync_reasoning: str | None = None


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(session: AsyncSession = Depends(get_db)) -> SyncStatusResponse:
    """
    Return the outcome of the most recent sync cycle.

    The sync worker writes an AuditEntry with event_type=sync_completed or
    sync_failed after each cycle — this endpoint reads the most recent one.
    """
    last_event = await AuditRepository.get_last_sync_event(session)

    if last_event is None:
        return SyncStatusResponse(state="unknown")

    state = "idle" if last_event.event_type == "sync_completed" else "failed"
    return SyncStatusResponse(
        state=state,
        last_sync_at=last_event.created_at,
        last_sync_event_type=last_event.event_type,
        last_sync_reasoning=last_event.reasoning,
    )
