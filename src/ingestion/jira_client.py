"""
Jira MCP client adapter.

Connects to the Jira MCP Server via SSE transport and wraps each MCP tool
call in a typed Pydantic interface with exponential-backoff retry.

Usage:
    async with JiraMCPClient() as client:
        sprints = await client.list_sprints("BOARD-1")
        issues  = await client.list_issues("PROJ")
        comments = await client.get_comments("PROJ-123")
"""

import asyncio
import json
import random
from datetime import date, datetime
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0  # wait = base ** attempt  (2s, 4s, 8s)


# ---------------------------------------------------------------------------
# Typed Pydantic response models
# ---------------------------------------------------------------------------


class JiraIssue(BaseModel):
    jira_id: str  # e.g. "PROJ-123"
    summary: str
    description: str | None = None
    jira_status: str
    assignee_email: str | None = None
    assignee_display_name: str | None = None
    assignee_username: str | None = None
    priority: str | None = None
    story_points: float | None = None
    labels: list[str] = Field(default_factory=list)
    linked_issue_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    due_date: date | None = None
    is_blocked: bool = False
    sprint_jira_id: str | None = None
    board_id: str | None = None


class JiraSprint(BaseModel):
    jira_sprint_id: str
    name: str
    state: str  # "active" | "future" | "closed"
    board_id: str
    start_date: date | None = None
    end_date: date | None = None


class JiraComment(BaseModel):
    id: str
    issue_jira_id: str
    author_display_name: str
    author_email: str | None = None
    body: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle both "Z" and "+00:00" UTC suffixes
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Cannot parse datetime from {value!r}")


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _parse_issue(raw: dict) -> JiraIssue:
    """Map a raw MCP tool-result dict to a typed JiraIssue."""
    fields = raw.get("fields", raw)  # Some MCP servers nest under "fields"
    assignee = fields.get("assignee") or {}
    labels_raw = fields.get("labels", [])
    labels = [str(lbl.get("name", lbl)) if isinstance(lbl, dict) else str(lbl) for lbl in labels_raw]

    linked_raw = fields.get("issuelinks", []) or fields.get("linked_issues", [])
    linked_ids: list[str] = []
    for link in linked_raw:
        if isinstance(link, dict):
            for key in ("inwardIssue", "outwardIssue", "linked_issue_id"):
                sub = link.get(key)
                if isinstance(sub, dict):
                    linked_ids.append(sub.get("key", sub.get("id", "")))
                elif isinstance(sub, str):
                    linked_ids.append(sub)
        elif isinstance(link, str):
            linked_ids.append(link)

    status_raw = fields.get("status", {})
    status_name = (
        status_raw.get("name", status_raw) if isinstance(status_raw, dict) else str(status_raw)
    )

    priority_raw = fields.get("priority", {})
    priority = (
        priority_raw.get("name", None) if isinstance(priority_raw, dict) else str(priority_raw)
    )

    sprint_info = fields.get("sprint") or {}
    sprint_jira_id = (
        str(sprint_info.get("id", "")) if isinstance(sprint_info, dict) else None
    ) or None

    is_blocked = bool(fields.get("flagged", False)) or "blocked" in str(status_name).lower()

    return JiraIssue(
        jira_id=raw.get("key", raw.get("id", "")),
        summary=str(fields.get("summary", "")),
        description=fields.get("description"),
        jira_status=str(status_name),
        assignee_email=assignee.get("emailAddress") if isinstance(assignee, dict) else None,
        assignee_display_name=assignee.get("displayName") if isinstance(assignee, dict) else None,
        assignee_username=assignee.get("name") or assignee.get("accountId") if isinstance(assignee, dict) else None,
        priority=priority,
        story_points=fields.get("story_points") or fields.get("customfield_10016") or fields.get("storyPoints"),
        labels=labels,
        linked_issue_ids=[i for i in linked_ids if i],
        created_at=_parse_datetime(fields.get("created", fields.get("created_at", datetime.utcnow().isoformat()))),
        updated_at=_parse_datetime(fields.get("updated", fields.get("updated_at", datetime.utcnow().isoformat()))),
        due_date=_parse_date(fields.get("duedate") or fields.get("due_date")),
        is_blocked=is_blocked,
        sprint_jira_id=sprint_jira_id,
        board_id=fields.get("board_id"),
    )


def _parse_sprint(raw: dict) -> JiraSprint:
    return JiraSprint(
        jira_sprint_id=str(raw.get("id", raw.get("jira_sprint_id", ""))),
        name=str(raw.get("name", "")),
        state=str(raw.get("state", "future")).lower(),
        board_id=str(raw.get("originBoardId", raw.get("board_id", ""))),
        start_date=_parse_date(raw.get("startDate") or raw.get("start_date")),
        end_date=_parse_date(raw.get("endDate") or raw.get("end_date")),
    )


def _parse_comment(raw: dict, issue_jira_id: str) -> JiraComment:
    author = raw.get("author", {}) or {}
    return JiraComment(
        id=str(raw.get("id", "")),
        issue_jira_id=issue_jira_id,
        author_display_name=author.get("displayName", author.get("display_name", "unknown"))
        if isinstance(author, dict)
        else str(author),
        author_email=author.get("emailAddress") if isinstance(author, dict) else None,
        body=str(raw.get("body", "")),
        created_at=_parse_datetime(raw.get("created", raw.get("created_at", datetime.utcnow().isoformat()))),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class JiraMCPClient:
    """Async context manager that holds an active MCP session for the duration."""

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.jira_mcp_url.rstrip("/") + "/sse"
        self._headers = {"Authorization": f"Bearer {settings.jira_mcp_token}"} if settings.jira_mcp_token else {}
        self._session: ClientSession | None = None
        self._sse_ctx: Any = None
        self._client_ctx: Any = None

    async def __aenter__(self) -> "JiraMCPClient":
        self._sse_ctx = sse_client(url=self._url, headers=self._headers)
        read_stream, write_stream = await self._sse_ctx.__aenter__()
        self._client_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._client_ctx.__aenter__()
        await self._session.initialize()
        logger.debug("JiraMCPClient connected to %s", self._url)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client_ctx:
            await self._client_ctx.__aexit__(exc_type, exc_val, exc_tb)
        if self._sse_ctx:
            await self._sse_ctx.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None

    # ------------------------------------------------------------------
    # Internal retry helper
    # ------------------------------------------------------------------

    async def _call(self, tool_name: str, arguments: dict) -> Any:
        if self._session is None:
            raise RuntimeError("JiraMCPClient not entered — use 'async with'")
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
                    wait = _RETRY_BASE_SECONDS ** attempt
                    logger.warning(
                        "MCP tool %r failed (attempt %d/%d): %s — retrying in %.1fs",
                        tool_name, attempt + 1, _MAX_RETRIES, exc, wait,
                    )
                    jitter = random.uniform(0, wait * 0.3)
                    await asyncio.sleep(wait + jitter)
        raise RuntimeError(
            f"MCP tool {tool_name!r} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public tool wrappers
    # ------------------------------------------------------------------

    async def list_issues(self, project_key: str, max_results: int = 500) -> list[JiraIssue]:
        """Fetch all issues for a project key."""
        data = await self._call("list_issues", {"project": project_key, "maxResults": max_results})
        raw_issues = data if isinstance(data, list) else data.get("issues", [])
        issues: list[JiraIssue] = []
        for raw in raw_issues:
            try:
                issues.append(_parse_issue(raw))
            except Exception as exc:
                logger.warning("Failed to parse Jira issue %r: %s", raw.get("key"), exc)
        return issues

    async def get_issue(self, jira_id: str) -> JiraIssue | None:
        """Fetch a single issue by key."""
        try:
            data = await self._call("get_issue", {"issueIdOrKey": jira_id})
            return _parse_issue(data)
        except Exception as exc:
            logger.warning("Failed to get issue %r: %s", jira_id, exc)
            return None

    async def list_sprints(self, board_id: str) -> list[JiraSprint]:
        """Fetch all sprints for a board."""
        data = await self._call("list_sprints", {"boardId": board_id})
        raw_sprints = data if isinstance(data, list) else data.get("values", data.get("sprints", []))
        sprints: list[JiraSprint] = []
        for raw in raw_sprints:
            try:
                s = _parse_sprint(raw)
                if not s.board_id:
                    s = s.model_copy(update={"board_id": board_id})
                sprints.append(s)
            except Exception as exc:
                logger.warning("Failed to parse sprint %r: %s", raw.get("id"), exc)
        return sprints

    async def get_comments(self, jira_id: str, max_results: int = 50) -> list[JiraComment]:
        """Fetch comments for an issue."""
        data = await self._call("get_comments", {"issueIdOrKey": jira_id, "maxResults": max_results})
        raw_comments = data if isinstance(data, list) else data.get("comments", [])
        comments: list[JiraComment] = []
        for raw in raw_comments:
            try:
                comments.append(_parse_comment(raw, jira_id))
            except Exception as exc:
                logger.warning("Failed to parse comment on %r: %s", jira_id, exc)
        return comments

    async def update_issue(self, jira_id: str, fields: dict) -> bool:
        """Apply a field update to an issue. Returns True on success."""
        try:
            await self._call("update_issue", {"issueIdOrKey": jira_id, "fields": fields})
            return True
        except Exception as exc:
            logger.error("Failed to update issue %r: %s", jira_id, exc)
            return False
