"""
Copilot MCP server.

Exposes three MCP tools over SSE transport:
  - list_meetings
  - get_transcript
  - get_meeting_summary

Also exposes GET /health for operator liveness checks.

Authentication: if MCP_TOKEN is set, inbound requests must supply a matching
Authorization: Bearer header or receive HTTP 401.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from src.copilot_mcp.auth import GraphTokenManager
from src.copilot_mcp.config import CopilotMCPSettings, get_settings
from src.copilot_mcp.graph_client import (
    MeetingRecord,
    TranscriptSegment,
    get_meeting_summary,
    get_transcript,
    list_meetings,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


async def _health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Bearer token middleware
# ---------------------------------------------------------------------------


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests with wrong or missing Authorization: Bearer token."""

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        # Health check is always public
        if request.url.path == "/health":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[len("Bearer "):] != self._token:
            return Response(
                content=json.dumps({"error": "unauthorized"}),
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Tool helpers — convert internal types to JSON-serialisable dicts
# ---------------------------------------------------------------------------


def _meeting_to_wire(rec: MeetingRecord) -> dict:
    return {
        "id": rec.id,
        "title": rec.title,
        "startedAt": rec.started_at.isoformat(),
        "endedAt": rec.ended_at.isoformat() if rec.ended_at else None,
        "participants": rec.participants,
    }


def _segments_to_raw_transcript(segments: list[TranscriptSegment]) -> str:
    return "".join(f"{seg.speaker}: {seg.text}\n" for seg in segments)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def build_app(settings: CopilotMCPSettings):
    """Build and return the ASGI app. Accepts settings for testability."""
    token_manager = GraphTokenManager(settings)

    mcp = FastMCP(
        name="copilot-mcp",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )

    # Register /health as a custom route
    mcp.custom_route("/health", methods=["GET"], name="health")

    @mcp.tool()
    async def list_meetings_tool(maxResults: int = 50) -> list[dict]:  # noqa: N803
        """Return recent meeting metadata for all tenant meetings."""
        token = await token_manager.get_token()
        records = await list_meetings(
            token,
            max_results=maxResults,
            lookback_days=settings.transcript_lookback_days,
        )
        return [_meeting_to_wire(r) for r in records]

    @mcp.tool()
    async def get_transcript_tool(meetingId: str) -> dict | None:  # noqa: N803
        """Return speaker-attributed transcript for a meeting, or null if unavailable."""
        if not meetingId:
            return {"error": "missing_param", "param": "meetingId"}
        token = await token_manager.get_token()
        record, segments = await get_transcript(token, meetingId)
        if record is None:
            return None
        wire = _meeting_to_wire(record)
        wire["rawTranscript"] = _segments_to_raw_transcript(segments) if segments else None
        return wire

    @mcp.tool()
    async def get_meeting_summary_tool(meetingId: str) -> dict | None:  # noqa: N803
        """Return Copilot-generated summary and action items, or null if unavailable."""
        if not meetingId:
            return {"error": "missing_param", "param": "meetingId"}
        token = await token_manager.get_token()
        result = await get_meeting_summary(token, meetingId)
        if result is None:
            return None
        return {
            "summary": result.summary,
            "actionItems": result.action_items,
        }

    # Build the Starlette ASGI app from FastMCP
    starlette_app = mcp.sse_app()

    # Add /health route directly to the Starlette app
    starlette_app.routes.insert(0, Route("/health", endpoint=_health, methods=["GET"]))

    # Wrap with bearer auth middleware if token is configured
    if settings.mcp_token:
        starlette_app.add_middleware(_BearerAuthMiddleware, token=settings.mcp_token)

    return starlette_app


def get_app() -> object:
    """Return the default ASGI app using environment-configured settings.

    Called by __main__.py and uvicorn. Not invoked at import time so tests
    can import this module without requiring Azure credentials in the environment.
    """
    return build_app(get_settings())
