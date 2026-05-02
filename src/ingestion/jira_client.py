"""
Jira Cloud REST API client.

Connects directly to the Jira Cloud REST API v3 using HTTP Basic Auth
(email + API token). No MCP server required.

Usage:
    async with JiraClient() as client:
        sprints = await client.list_sprints("123")
        issues  = await client.list_issues("PROJ")
        comments = await client.get_comments("PROJ-123")
"""

import asyncio
import random
from datetime import date, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0  # wait = base ** attempt  (2s, 4s, 8s)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
    """Map a raw Jira REST API issue dict to a typed JiraIssue."""
    fields = raw.get("fields", raw)
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


class JiraClient:
    """Async context manager that holds an active httpx session for the duration."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.jira_base_url.rstrip("/")
        self._auth = httpx.BasicAuth(settings.jira_email, settings.jira_api_token)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "JiraClient":
        self._client = httpx.AsyncClient(
            auth=self._auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )
        logger.debug("JiraClient connected to %s", self._base_url)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Internal retry helper
    # ------------------------------------------------------------------

    async def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise RuntimeError("JiraClient not entered — use 'async with'")
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.status_code == 401:
                    raise RuntimeError(
                        f"Jira authentication failed (401). Check JIRA_EMAIL and JIRA_API_TOKEN. URL: {url}"
                    )
                if response.status_code in _RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return {}
                return response.json()
            except RuntimeError:
                raise  # 401 — do not retry
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_SECONDS ** (attempt + 1)
                    jitter = random.uniform(0, wait * 0.3)
                    logger.warning(
                        "Jira API %s %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        method, path, attempt + 1, _MAX_RETRIES, exc, wait + jitter,
                    )
                    await asyncio.sleep(wait + jitter)
        raise RuntimeError(
            f"Jira API {method} {path} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def list_issues(self, project_key: str, max_results: int = 500) -> list[JiraIssue]:
        """Fetch all issues for a project using JQL, with pagination."""
        issues: list[JiraIssue] = []
        start_at = 0
        page_size = 100
        while True:
            data = await self._call(
                "GET",
                "/rest/api/3/search/jql",
                params={
                    "jql": f"project={project_key} ORDER BY created ASC",
                    "startAt": start_at,
                    "maxResults": min(page_size, max_results - len(issues)),
                    "fields": "summary,description,status,assignee,priority,labels,"
                              "issuelinks,created,updated,duedate,flagged,sprint,"
                              "customfield_10016",
                },
            )
            raw_issues = data.get("issues", [])
            for raw in raw_issues:
                try:
                    issues.append(_parse_issue(raw))
                except Exception as exc:
                    logger.warning("Failed to parse Jira issue %r: %s", raw.get("key"), exc)
            start_at += len(raw_issues)
            total = data.get("total", 0)
            if start_at >= total or len(issues) >= max_results or not raw_issues:
                break
        return issues

    async def get_issue(self, jira_id: str) -> JiraIssue | None:
        """Fetch a single issue by key."""
        try:
            data = await self._call("GET", f"/rest/api/3/issue/{jira_id}")
            return _parse_issue(data)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.warning("Issue %r not accessible: HTTP %s", jira_id, exc.response.status_code)
                return None
            raise
        except Exception as exc:
            logger.warning("Failed to get issue %r: %s", jira_id, exc)
            return None

    async def get_board_id(self, project_key: str) -> str | None:
        """Look up the numeric board ID for a project key."""
        try:
            data = await self._call("GET", "/rest/agile/1.0/board", params={"projectKeyOrId": project_key})
            values = data.get("values", [])
            if values:
                return str(values[0]["id"])
            return None
        except Exception as exc:
            logger.warning("Failed to get board ID for project %r: %s", project_key, exc)
            return None

    async def list_sprints(self, board_id: str) -> list[JiraSprint]:
        """Fetch all sprints for a board."""
        try:
            data = await self._call("GET", f"/rest/agile/1.0/board/{board_id}/sprint")
            raw_sprints = data.get("values", [])
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
        except Exception as exc:
            logger.warning("Failed to list sprints for board %r: %s", board_id, exc)
            return []

    async def get_comments(self, jira_id: str, max_results: int = 50) -> list[JiraComment]:
        """Fetch comments for an issue."""
        try:
            data = await self._call(
                "GET",
                f"/rest/api/3/issue/{jira_id}/comment",
                params={"maxResults": max_results, "orderBy": "created"},
            )
            raw_comments = data.get("comments", [])
            comments: list[JiraComment] = []
            for raw in raw_comments:
                try:
                    comments.append(_parse_comment(raw, jira_id))
                except Exception as exc:
                    logger.warning("Failed to parse comment on %r: %s", jira_id, exc)
            return comments
        except Exception as exc:
            logger.warning("Failed to get comments for %r: %s", jira_id, exc)
            return []

    async def update_issue(self, jira_id: str, fields: dict) -> bool:
        """Apply field updates to a Jira issue. Returns True on success."""
        try:
            await self._call("PUT", f"/rest/api/3/issue/{jira_id}", json={"fields": fields})
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.error(
                    "Failed to update issue %r: HTTP %s (check permissions)",
                    jira_id, exc.response.status_code,
                )
                return False
            raise
        except Exception as exc:
            logger.error("Failed to update issue %r: %s", jira_id, exc)
            return False
