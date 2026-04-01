"""
Suggestion routes.

  GET  /api/v1/suggestions              — review queue
  POST /api/v1/suggestions/{id}/approve — apply to Jira and mark approved
  POST /api/v1/suggestions/{id}/reject  — mark rejected, no Jira change
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_db
from src.storage.models import ApprovalState, AuditEventType
from src.storage.repository import AuditRepository, SuggestionRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TicketRef(BaseModel):
    jira_id: str
    title: str


class TranscriptSource(BaseModel):
    transcript_id: str
    meeting_title: str | None = None
    started_at: datetime | None = None
    excerpt: str
    speaker: str
    excerpt_timestamp_seconds: int | None = None


class SuggestionOut(BaseModel):
    id: str
    ticket: TicketRef | None = None
    update_type: str
    proposed_value: dict
    confidence_score: float
    confidence_tier: str
    approval_state: str
    conflict_flag: bool
    conflict_details: str | None = None
    source: TranscriptSource | None = None
    created_at: datetime


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionOut]
    total: int


class ApproveRequest(BaseModel):
    note: str | None = None


class ApproveResponse(BaseModel):
    id: str
    approval_state: str
    applied_at: datetime | None = None


class RejectRequest(BaseModel):
    reason: str | None = None


class RejectResponse(BaseModel):
    id: str
    approval_state: str
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _authorized_project_keys(request: Request) -> list[str]:
    return getattr(request.state, "project_keys", [])


def _is_project_authorized(jira_id: str, authorized_keys: list[str]) -> bool:
    if not authorized_keys:
        return True
    prefix = jira_id.split("-")[0].upper() if "-" in jira_id else jira_id.upper()
    return prefix in {k.upper() for k in authorized_keys}


# ---------------------------------------------------------------------------
# GET /suggestions
# ---------------------------------------------------------------------------


@router.get("/suggestions", response_model=SuggestionsResponse)
async def list_suggestions(
    request: Request,
    approval_state: str | None = Query("pending"),
    confidence_tier: str | None = Query(None),
    ticket_jira_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> SuggestionsResponse:
    authorized_keys = _authorized_project_keys(request)

    suggestions = await SuggestionRepository.list_with_filters(
        session,
        approval_state=approval_state,
        confidence_tier=confidence_tier,
        ticket_jira_id=ticket_jira_id,
        limit=limit + offset,
        offset=0,
    )

    # Apply auth scoping
    filtered = [
        s for s in suggestions
        if not s.ticket or _is_project_authorized(s.ticket.jira_id, authorized_keys)
    ]
    total = len(filtered)
    page = filtered[offset: offset + limit]

    out: list[SuggestionOut] = []
    for s in page:
        ticket_ref: TicketRef | None = None
        if s.ticket:
            ticket_ref = TicketRef(jira_id=s.ticket.jira_id, title=s.ticket.title)

        source: TranscriptSource | None = None
        if s.transcript_mention:
            mention = s.transcript_mention
            transcript = mention.transcript if mention else None
            source = TranscriptSource(
                transcript_id=mention.transcript_id,
                meeting_title=transcript.title if transcript else None,
                started_at=transcript.started_at if transcript else None,
                excerpt=mention.excerpt,
                speaker=mention.speaker_name,
                excerpt_timestamp_seconds=mention.excerpt_timestamp_seconds,
            )

        out.append(
            SuggestionOut(
                id=s.id,
                ticket=ticket_ref,
                update_type=s.update_type,
                proposed_value=s.proposed_value,
                confidence_score=s.confidence_score,
                confidence_tier=s.confidence_tier,
                approval_state=s.approval_state,
                conflict_flag=s.conflict_flag,
                conflict_details=s.conflict_details,
                source=source,
                created_at=s.created_at,
            )
        )

    return SuggestionsResponse(suggestions=out, total=total)


# ---------------------------------------------------------------------------
# POST /suggestions/{id}/approve
# ---------------------------------------------------------------------------


@router.post("/suggestions/{suggestion_id}/approve", response_model=ApproveResponse)
async def approve_suggestion(
    suggestion_id: str,
    body: ApproveRequest | None = None,
    request: Request = None,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_db),
) -> ApproveResponse:
    suggestion = await SuggestionRepository.get_by_id(session, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    # 409 if conflicted
    if suggestion.conflict_flag:
        raise HTTPException(
            status_code=409,
            detail="Cannot approve a suggestion with unresolved conflicts. Resolve conflicts manually first.",
        )

    # 403 if not authorized for this project
    if suggestion.ticket and request is not None:
        authorized_keys = _authorized_project_keys(request)
        if not _is_project_authorized(suggestion.ticket.jira_id, authorized_keys):
            raise HTTPException(status_code=403, detail="Not authorized for this ticket's project.")

    # Apply to Jira
    if suggestion.ticket:
        from src.analysis.update_suggester import _build_jira_fields
        from src.ingestion.jira_client import JiraMCPClient

        fields = _build_jira_fields(suggestion.update_type, suggestion.proposed_value)
        try:
            async with JiraMCPClient() as jira:
                await jira.update_issue(suggestion.ticket.jira_id, fields)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Jira update failed: {exc}") from exc

    now = datetime.now(UTC)
    updated = await SuggestionRepository.update_state(
        session,
        suggestion_id,
        ApprovalState.approved.value,
        applied_at=now,
    )

    await AuditRepository.create(
        session,
        event_type=AuditEventType.suggestion_approved.value,
        ticket_id=suggestion.ticket_id,
        update_suggestion_id=suggestion.id,
        reasoning=(
            f"Suggestion approved. Update type: {suggestion.update_type}. "
            + (f"Note: {body.note}" if body and body.note else "")
        ),
        signal_inputs={
            "confidence_score": suggestion.confidence_score,
            "confidence_tier": suggestion.confidence_tier,
            "update_type": suggestion.update_type,
            "proposed_value": suggestion.proposed_value,
        },
    )
    await session.commit()

    return ApproveResponse(
        id=suggestion_id,
        approval_state=ApprovalState.approved.value,
        applied_at=updated.applied_at if updated else now,
    )


# ---------------------------------------------------------------------------
# POST /suggestions/{id}/reject  (T031)
# ---------------------------------------------------------------------------


@router.post("/suggestions/{suggestion_id}/reject", response_model=RejectResponse)
async def reject_suggestion(
    suggestion_id: str,
    body: RejectRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> RejectResponse:
    suggestion = await SuggestionRepository.get_by_id(session, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    rejection_reason = body.reason if body else None

    await SuggestionRepository.update_state(
        session,
        suggestion_id,
        ApprovalState.rejected.value,
        rejection_reason=rejection_reason,
        reviewed_at=datetime.now(UTC),
    )

    await AuditRepository.create(
        session,
        event_type=AuditEventType.suggestion_rejected.value,
        ticket_id=suggestion.ticket_id,
        update_suggestion_id=suggestion.id,
        reasoning=f"Suggestion rejected. Reason: {rejection_reason or 'not provided'}.",
        signal_inputs={
            "confidence_score": suggestion.confidence_score,
            "confidence_tier": suggestion.confidence_tier,
            "update_type": suggestion.update_type,
        },
    )
    await session.commit()

    return RejectResponse(
        id=suggestion_id,
        approval_state=ApprovalState.rejected.value,
        rejection_reason=rejection_reason,
    )
