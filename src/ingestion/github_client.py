"""
GitHub REST API client.

Connects to api.github.com using a Personal Access Token (PAT) via Bearer auth.
Supports listing repos, commits, and PRs with pagination and rate-limit handling.

Usage:
    async with GitHubClient() as client:
        repos = await client.list_repos()
        commits = await client.list_commits("org/repo", since=last_synced_at)
        prs = await client.list_prs("org/repo", since=last_synced_at)
"""

import asyncio
import random
import re
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_GITHUB_API_VERSION = "2022-11-28"

_JIRA_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


# ---------------------------------------------------------------------------
# Jira key extraction (used by sync worker)
# ---------------------------------------------------------------------------


def extract_jira_keys(text: str | None) -> list[str]:
    """Return deduplicated Jira ticket keys found in text (e.g. 'SCRUM-42')."""
    if not text:
        return []
    return list(dict.fromkeys(_JIRA_KEY_RE.findall(text)))


# ---------------------------------------------------------------------------
# Typed Pydantic response models
# ---------------------------------------------------------------------------


class GitHubRepoInfo(BaseModel):
    full_name: str
    org: str
    name: str
    default_branch: str = "main"


class GitHubCommitInfo(BaseModel):
    sha: str
    message: str
    author_login: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime
    branch: str | None = None
    url: str | None = None


class GitHubPRInfo(BaseModel):
    pr_number: int
    title: str
    body: str | None = None
    state: str  # "open" | "closed" | "merged"
    author_login: str | None = None
    head_branch: str | None = None
    base_branch: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    url: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _parse_dt_required(value: Any) -> datetime:
    result = _parse_dt(value)
    if result is None:
        raise ValueError(f"Required datetime missing: {value!r}")
    return result


def _parse_link_header(link_header: str | None) -> str | None:
    """Extract the 'next' URL from a GitHub Link response header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            url_part = part.split(";")[0].strip()
            return url_part.strip("<>")
    return None


def _parse_pr_state(raw: dict) -> str:
    if raw.get("merged_at"):
        return "merged"
    state = raw.get("state", "open")
    return state if state in ("open", "closed") else "open"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Async context manager for GitHub REST API requests with PAT auth."""

    def __init__(self) -> None:
        settings = get_settings()
        self._pat = settings.github_pat
        self._org = settings.github_org
        self._base_url = "https://api.github.com"
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._pat}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _GITHUB_API_VERSION,
            },
            timeout=30.0,
        )
        logger.debug("GitHubClient connected to %s", self._base_url)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Internal request helper with retry + rate-limit handling
    # ------------------------------------------------------------------

    async def _get(self, url: str, **params: Any) -> tuple[Any, dict]:
        """
        GET a URL (absolute) and return (json_body, response_headers).
        Handles rate limiting and retries.
        """
        if self._client is None:
            raise RuntimeError("GitHubClient not entered — use 'async with'")

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.get(url, params=params or None)

                # Rate limit: remaining == 0 means we must wait
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining is not None and int(remaining) == 0:
                    reset_ts = int(response.headers.get("X-RateLimit-Reset", "0"))
                    now_ts = int(datetime.utcnow().timestamp())
                    wait = max(reset_ts - now_ts + 1, 1)
                    logger.warning(
                        "GitHub rate limit reached — waiting %ds until reset", wait
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code == 401:
                    raise RuntimeError(
                        "GitHub authentication failed (401) — check GITHUB_PAT"
                    )
                if response.status_code == 404:
                    raise RuntimeError(f"GitHub resource not found (404): {url}")
                if response.status_code in _RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.json(), dict(response.headers)

            except RuntimeError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_SECONDS ** (attempt + 1)
                    jitter = random.uniform(0, wait * 0.3)
                    logger.warning(
                        "GitHub API GET %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        url, attempt + 1, _MAX_RETRIES, exc, wait + jitter,
                    )
                    await asyncio.sleep(wait + jitter)

        raise RuntimeError(
            f"GitHub API GET {url} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def list_repos(self) -> list[GitHubRepoInfo]:
        """
        List all repos for the configured org or user account, handling pagination.
        Tries /orgs/{name}/repos first; falls back to /users/{name}/repos if 404
        (personal accounts are not orgs).
        """
        # Determine the correct endpoint — org vs personal account
        try:
            start_url = f"{self._base_url}/orgs/{self._org}/repos"
            repos = await self._fetch_repos(start_url)
        except RuntimeError:
            logger.info(
                "GitHub: %r is not an org — retrying as user account", self._org
            )
            start_url = f"{self._base_url}/users/{self._org}/repos"
            repos = await self._fetch_repos(start_url)

        logger.info("GitHub: discovered %d repo(s) for %r", len(repos), self._org)
        return repos

    async def _fetch_repos(self, start_url: str) -> list[GitHubRepoInfo]:
        """Paginate through a repos listing URL and return parsed GitHubRepoInfo list."""
        repos: list[GitHubRepoInfo] = []
        url: str | None = start_url
        params: dict[str, Any] = {"type": "all", "per_page": 100}

        while url:
            data, headers = await self._get(url, **params)
            params = {}
            for raw in data:
                try:
                    owner = raw.get("owner", {}).get("login", self._org)
                    repos.append(
                        GitHubRepoInfo(
                            full_name=raw["full_name"],
                            org=owner,
                            name=raw["name"],
                            default_branch=raw.get("default_branch", "main"),
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to parse repo %r: %s", raw.get("full_name"), exc)
            url = _parse_link_header(headers.get("link"))

        return repos

    async def list_commits(
        self,
        full_name: str,
        since: datetime | None = None,
        branch: str | None = None,
    ) -> list[GitHubCommitInfo]:
        """List commits for a repo, newest first. Pass `since` for incremental sync."""
        commits: list[GitHubCommitInfo] = []
        url = f"{self._base_url}/repos/{full_name}/commits"
        params: dict[str, Any] = {"per_page": 100}
        if since:
            params["since"] = since.isoformat()
        if branch:
            params["sha"] = branch

        while url:
            data, headers = await self._get(url, **params)
            params = {}
            for raw in data:
                try:
                    commit = raw.get("commit", {})
                    author_data = commit.get("author", {}) or {}
                    github_author = raw.get("author") or {}
                    commits.append(
                        GitHubCommitInfo(
                            sha=raw["sha"],
                            message=commit.get("message", ""),
                            author_login=github_author.get("login"),
                            author_name=author_data.get("name"),
                            author_email=author_data.get("email"),
                            committed_at=_parse_dt_required(author_data.get("date")),
                            branch=branch,
                            url=raw.get("html_url"),
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to parse commit %r in %s: %s", raw.get("sha"), full_name, exc)
            url = _parse_link_header(headers.get("link"))

        logger.debug("GitHub: fetched %d commit(s) from %s", len(commits), full_name)
        return commits

    async def list_prs(
        self,
        full_name: str,
        since: datetime | None = None,
    ) -> list[GitHubPRInfo]:
        """
        List pull requests for a repo sorted by update time (newest first).
        Stops pagination early when updated_at < since for incremental sync.
        """
        prs: list[GitHubPRInfo] = []
        url = f"{self._base_url}/repos/{full_name}/pulls"
        params: dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
        }

        stop = False
        while url and not stop:
            data, headers = await self._get(url, **params)
            params = {}
            for raw in data:
                try:
                    updated_at = _parse_dt(raw.get("updated_at"))
                    if since and updated_at and updated_at < since:
                        stop = True
                        break
                    state = _parse_pr_state(raw)
                    head = raw.get("head", {}) or {}
                    base = raw.get("base", {}) or {}
                    user = raw.get("user") or {}
                    prs.append(
                        GitHubPRInfo(
                            pr_number=raw["number"],
                            title=raw.get("title", ""),
                            body=raw.get("body"),
                            state=state,
                            author_login=user.get("login"),
                            head_branch=head.get("ref"),
                            base_branch=base.get("ref"),
                            opened_at=_parse_dt_required(raw.get("created_at")),
                            closed_at=_parse_dt(raw.get("closed_at")),
                            merged_at=_parse_dt(raw.get("merged_at")),
                            url=raw.get("html_url"),
                            updated_at=updated_at or datetime.utcnow(),
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to parse PR #%s in %s: %s", raw.get("number"), full_name, exc)
            if not stop:
                url = _parse_link_header(headers.get("link"))

        logger.debug("GitHub: fetched %d PR(s) from %s", len(prs), full_name)
        return prs
