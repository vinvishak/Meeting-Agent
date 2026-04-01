"""
Natural language query route (T044).

  POST /api/v1/query — plain-language question → plain-language answer
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.query_handler import handle_query
from src.storage.database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    context: dict | None = None


class QueryResponse(BaseModel):
    answer: str
    supporting_data: dict
    data_freshness: str | None = None


# ---------------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------------


@router.post("/query", response_model=QueryResponse)
async def natural_language_query(
    body: QueryRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> QueryResponse:
    authorized_keys: list[str] = getattr(request.state, "project_keys", [])

    try:
        result = await handle_query(
            question=body.question,
            session=session,
            context=body.context,
            authorized_project_keys=authorized_keys or None,
        )
    except ValueError as exc:
        # Distinguishes "cannot answer" (422) from bad input (400)
        msg = str(exc)
        if "not configured" in msg.lower() or "cannot be answered" in msg.lower():
            raise HTTPException(status_code=422, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {exc}") from exc

    return QueryResponse(
        answer=result["answer"],
        supporting_data=result.get("supporting_data", {}),
        data_freshness=result.get("data_freshness"),
    )
