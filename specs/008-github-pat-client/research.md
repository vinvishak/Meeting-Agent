# Research: GitHub PAT Client

**Feature**: 008-github-pat-client  
**Phase**: 0 — Research  
**Date**: 2026-05-02

---

## Decision 1: GitHub Authentication Method

**Decision**: Personal Access Token (PAT) via `Authorization: Bearer <token>` header on all requests to `https://api.github.com`.

**Rationale**: Agreed with user — PAT is the simplest approach for a POC. The GitHub REST API supports PAT with `repo` scope, giving read access to commits, PRs, and repo listing for any org the PAT has access to. No OAuth dance, no server-side callback URL needed.

**Alternatives considered**:
- GitHub App (installation tokens): More appropriate for production — app-level permissions, no personal identity tied to token, supports webhook events. Chosen as future upgrade path once PAT POC is validated.
- OAuth user tokens: Requires web browser flow; impractical for a backend daemon process.

---

## Decision 2: HTTP Client

**Decision**: `httpx` (async) — same client already used by `JiraClient` in `src/ingestion/jira_client.py`.

**Rationale**: Already a transitive dependency; consistent with existing ingestion layer pattern. No new package needed.

**Alternatives considered**:
- `aiohttp`: Functionally equivalent, but `httpx` is already present and the codebase has established patterns around it.
- PyGitHub: Higher-level SDK but adds a dependency and hides the raw HTTP calls that the spec needs (rate limit headers, pagination cursors).

---

## Decision 3: Jira Key Extraction Pattern

**Decision**: Regex `[A-Z][A-Z0-9]+-\d+` applied to commit messages and PR titles + bodies.

**Rationale**: Matches standard Jira project key format (1+ uppercase letters followed by digits, then hyphen + issue number). Applied to: full commit message, PR title, PR body first 2000 chars (to avoid giant PR bodies becoming expensive). Extraction runs after data is stored — in the `GitHubJiraLink` upsert step.

**Pattern reasoning**: `[A-Z][A-Z0-9]+-\d+` correctly matches `SCRUM-42`, `DATA-7`, `PROJ123-99`. Avoids false positives like version strings (`v1.2-3`).

**Alternatives considered**:
- Search for known project keys (from `jira_project_keys` config): More precise but requires Jira to be configured first; a chicken-and-egg problem.
- Full Jira API resolution per link: Too slow for batch processing; linking is a local regex pass only.

---

## Decision 4: Incremental Sync Strategy

**Decision**: Per-repository `last_synced_at` timestamp stored on `GitHubRepo`. On incremental sync, pass `since=<ISO8601>` to GitHub's `GET /repos/{owner}/{repo}/commits` endpoint. For PRs, use `state=all&sort=updated&direction=desc` and stop when `updated_at < last_synced_at`.

**Rationale**: GitHub's commits endpoint supports a `since` parameter directly, making incremental commit sync efficient. PRs require fetching by `updated_at` sort and stopping early — a standard GitHub API pagination pattern.

**Alternatives considered**:
- Webhook-based real-time sync: More responsive but requires a publicly reachable URL; not available in this local POC context.
- Always fetch full history: Simple but prohibitively slow for repos with thousands of commits.

---

## Decision 5: Module Structure

**Decision**: New module `src/ingestion/github_client.py` following the exact pattern of `src/ingestion/jira_client.py` — `async with GitHubClient() as client:` context manager, Pydantic response models, retry with exponential backoff on 429/5xx, structured logging.

**Rationale**: Constitutes a single-responsibility module (Principle II). Keeps all GitHub HTTP concerns isolated from sync orchestration. Mirrors the proven JiraClient pattern so the codebase stays consistent.

**New files**:
- `src/ingestion/github_client.py` — HTTP client + Pydantic models
- `src/storage/models.py` — 4 new ORM models appended (GitHubRepo, GitHubCommit, GitHubPullRequest, GitHubJiraLink)
- `src/storage/migrations/versions/002_github_schema.py` — Alembic migration
- `src/api/routes/github.py` — 3 new route handlers
- `src/workers/sync_worker.py` — `_sync_github()` function added to existing `run_sync_cycle()`
- `src/config.py` — 3 new settings fields

**No new packages required**: `httpx` already present, `re` is stdlib.

---

## Decision 6: Rate Limit Handling

**Decision**: Respect `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. If remaining hits 0, sleep until the reset timestamp before retrying. Log the wait duration. This matches GitHub's documented behavior for PAT rate limits (5,000 req/hour for authenticated requests).

**Rationale**: Required by spec FR-005. Avoids data loss from unhandled 403 rate-limit responses. Consistent with the existing JiraClient retry logic.

---

## Decision 7: Frontend Wiring Strategy

**Decision**: The Prism dashboard frontend (`frontend/index.html`) fetches `/api/v1/github/repos` to determine if GitHub is synced, then uses commit count from the response to update tree nodes from `inactive` → `active`. No new JS files — the existing inline `<script>` in `index.html` is extended.

**Rationale**: Simplicity First (Principle V) — no bundler, no new files, inline script already manages all API calls. A single `fetchGitHubStatus()` function checks repos endpoint and patches the DOM state attribute on `[data-type="github"]` nodes.
