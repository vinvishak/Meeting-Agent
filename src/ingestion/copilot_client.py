"""
Copilot MCP client adapter.

Connects to the GitHub Copilot MCP Server via SSE transport and wraps each
MCP tool call in a typed Pydantic interface with exponential-backoff retry.
Deduplication of already-ingested meetings is handled by the caller via
the `copilot_meeting_id` unique constraint on the Transcript table.

Usage:
    async with CopilotMCPClient() as client:
        meetings = await client.list_meetings()
        transcript = await client.get_transcript("meeting-abc-123")
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Typed Pydantic response models
# ---------------------------------------------------------------------------


class CopilotMeeting(BaseModel):
    copilot_meeting_id: str
    title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[str] = Field(default_factory=list)


class CopilotTranscript(BaseModel):
    copilot_meeting_id: str
    title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[str] = Field(default_factory=list)
    raw_transcript: str
    copilot_summary: str | None = None
    action_items: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.utcnow()


def _parse_participants(raw: Any) -> list[str]:
    if isinstance(raw, list):
        result: list[str] = []
        for p in raw:
            if isinstance(p, dict):
                result.append(p.get("displayName") or p.get("name") or str(p))
            elif isinstance(p, str):
                result.append(p)
        return result
    return []


def _parse_action_items(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in raw]
    if isinstance(raw, str):
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return []


def _parse_meeting(raw: dict) -> CopilotMeeting:
    return CopilotMeeting(
        copilot_meeting_id=str(raw.get("id", raw.get("meetingId", ""))),
        title=raw.get("title") or raw.get("subject"),
        started_at=_parse_datetime(raw.get("startedAt") or raw.get("start") or raw.get("started_at")),
        ended_at=_parse_datetime(raw.get("endedAt") or raw.get("end") or raw.get("ended_at"))
        if raw.get("endedAt") or raw.get("end") or raw.get("ended_at")
        else None,
        participants=_parse_participants(raw.get("participants", [])),
    )


def _parse_transcript(raw: dict) -> CopilotTranscript:
    # The raw transcript may be under "transcript", "content", or the dict itself
    transcript_text = (
        raw.get("transcript")
        or raw.get("content")
        or raw.get("rawTranscript")
        or ""
    )
    if isinstance(transcript_text, list):
        # Sometimes transcript is a list of {speaker, text} segments
        lines: list[str] = []
        for seg in transcript_text:
            if isinstance(seg, dict):
                speaker = seg.get("speaker") or seg.get("displayName", "Unknown")
                text = seg.get("text") or seg.get("content", "")
                lines.append(f"{speaker}: {text}")
            else:
                lines.append(str(seg))
        transcript_text = "\n".join(lines)

    return CopilotTranscript(
        copilot_meeting_id=str(raw.get("id") or raw.get("meetingId") or raw.get("copilot_meeting_id", "")),
        title=raw.get("title") or raw.get("subject"),
        started_at=_parse_datetime(raw.get("startedAt") or raw.get("start") or raw.get("started_at")),
        ended_at=_parse_datetime(raw.get("endedAt") or raw.get("end") or raw.get("ended_at"))
        if raw.get("endedAt") or raw.get("end") or raw.get("ended_at")
        else None,
        participants=_parse_participants(raw.get("participants", [])),
        raw_transcript=str(transcript_text),
        copilot_summary=raw.get("summary") or raw.get("copilotSummary"),
        action_items=_parse_action_items(raw.get("actionItems") or raw.get("action_items", [])),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class CopilotMCPClient:
    """Async context manager that holds an active MCP session for the duration."""

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.copilot_mcp_url.rstrip("/") + "/sse"
        self._headers = (
            {"Authorization": f"Bearer {settings.copilot_mcp_token}"}
            if settings.copilot_mcp_token
            else {}
        )
        self._session: ClientSession | None = None
        self._sse_ctx: Any = None
        self._client_ctx: Any = None

    async def __aenter__(self) -> "CopilotMCPClient":
        self._sse_ctx = sse_client(url=self._url, headers=self._headers)
        read_stream, write_stream = await self._sse_ctx.__aenter__()
        self._client_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._client_ctx.__aenter__()
        await self._session.initialize()
        logger.debug("CopilotMCPClient connected to %s", self._url)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client_ctx:
            await self._client_ctx.__aexit__(exc_type, exc_val, exc_tb)
        if self._sse_ctx:
            await self._sse_ctx.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None

    async def _call(self, tool_name: str, arguments: dict) -> Any:
        if self._session is None:
            raise RuntimeError("CopilotMCPClient not entered — use 'async with'")
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                result = await self._session.call_tool(tool_name, arguments=arguments)
                if not result.content:
                    return {}
                raw = result.content[0].text  # type: ignore[union-attr]
                return json.loads(raw) if isinstance(raw, str) else raw
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_SECONDS**attempt
                    logger.warning(
                        "MCP tool %r failed (attempt %d/%d): %s — retrying in %.1fs",
                        tool_name,
                        attempt + 1,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    jitter = random.uniform(0, wait * 0.3)
                    await asyncio.sleep(wait + jitter)
        raise RuntimeError(
            f"MCP tool {tool_name!r} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public tool wrappers
    # ------------------------------------------------------------------

    async def list_meetings(self, max_results: int = 50) -> list[CopilotMeeting]:
        """Fetch recent meeting metadata."""
        data = await self._call("list_meetings", {"maxResults": max_results})
        raw_meetings = data if isinstance(data, list) else data.get("meetings", data.get("value", []))
        meetings: list[CopilotMeeting] = []
        for raw in raw_meetings:
            try:
                meetings.append(_parse_meeting(raw))
            except Exception as exc:
                logger.warning("Failed to parse meeting %r: %s", raw.get("id"), exc)
        return meetings

    async def get_transcript(self, meeting_id: str) -> CopilotTranscript | None:
        """Fetch the full transcript for a meeting."""
        try:
            data = await self._call("get_transcript", {"meetingId": meeting_id})
            return _parse_transcript(data)
        except Exception as exc:
            logger.warning("Failed to get transcript for meeting %r: %s", meeting_id, exc)
            return None

    async def get_meeting_summary(self, meeting_id: str) -> str | None:
        """Fetch the Copilot-generated summary for a meeting."""
        try:
            data = await self._call("get_meeting_summary", {"meetingId": meeting_id})
            if isinstance(data, str):
                return data
            return data.get("summary") or data.get("text") or data.get("content")
        except Exception as exc:
            logger.warning("Failed to get summary for meeting %r: %s", meeting_id, exc)
            return None
