# Meeting_Agent Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-15

## Active Technologies
- Python 3.12+ + `argparse` (stdlib), `getpass` (stdlib), `httpx` (transitive dep via fastapi), `anthropic` (existing), `alembic` (existing), `pydantic-settings` (existing) (002-add-quickstart-option)
- No new persistent storage; existing SQLite DB initialized via Alembic (002-add-quickstart-option)
- Python 3.12+ + `mcp` (FastMCP + SSE transport), `msal` (OAuth2 client credentials), `httpx` (async Graph API calls), `fastapi`/`starlette` + `uvicorn` (ASGI host, already in project), `pydantic-settings` (config, already in project) (004-copilot-mcp-wrapper)
- None — stateless server; `msal` in-memory token cache only (004-copilot-mcp-wrapper)
- Python 3.12+ + `httpx` (async HTTP, already a transitive dependency), `pydantic` v2 (existing), `pydantic-settings` (existing) (005-jira-rest-api-client)
- SQLite via existing Alembic schema — no schema changes (005-jira-rest-api-client)
- HTML5, CSS3, vanilla JavaScript (ES2022) + None — no npm, no bundler, no framework. Fetch API for HTTP, CSS custom properties for theming. (006-web-dashboard)
- None — all data comes from the backend API; no client-side persistence needed (006-web-dashboard)
- HTML5, CSS3, vanilla JavaScript (ES2022) + None — Fetch API, CSS custom properties, no external libraries (007-prism-dashboard)
- None — all data fetched from backend API on demand (007-prism-dashboard)
- Python 3.12+ + `httpx` (already present), `re` (stdlib), `pydantic` v2 (existing), `pydantic-settings` (existing), `sqlalchemy` 2.x (existing), `alembic` (existing), `fastapi` (existing), `apscheduler` (existing) (008-github-pat-client)
- SQLite via existing Alembic migrations — new migration `002_github_schema.py` adds 4 tables (008-github-pat-client)
- Python 3.12+ (backend) · HTML5/CSS3/JavaScript ES2022 (frontend) + FastAPI + Starlette (existing) · APScheduler (existing) · SQLAlchemy 2.x async (existing) · Alembic (existing) · `hmac`/`hashlib` stdlib · `asyncio` stdlib (009-github-live-stream)
- SQLite via Alembic migrations — 4 new tables added in `002_github_schema.py` (github_repos, github_commits, github_pull_requests, github_jira_links) (009-github-live-stream)
- Python 3.12+ + `anthropic` (Claude API — already present), `sqlalchemy` 2.x async (existing), `alembic` (existing), `fastapi` (existing) (011-commit-jira-semantic-match)
- SQLite — one new Alembic migration (`003_commit_suggestion_source.py`) to extend `update_suggestions` (011-commit-jira-semantic-match)

- Python 3.12+ + `anthropic` (Claude API), `mcp` (MCP Python SDK), `fastapi`, `pydantic` v2, `sqlalchemy` 2.x, `rapidfuzz` (entity matching), `apscheduler` (15-min sync scheduler), `pytest` + `pytest-asyncio` (001-jira-copilot-intelligence)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.12+: Follow standard conventions

## Recent Changes
- 011-commit-jira-semantic-match: Added Python 3.12+ + `anthropic` (Claude API — already present), `sqlalchemy` 2.x async (existing), `alembic` (existing), `fastapi` (existing)
- 009-github-live-stream: Added Python 3.12+ (backend) · HTML5/CSS3/JavaScript ES2022 (frontend) + FastAPI + Starlette (existing) · APScheduler (existing) · SQLAlchemy 2.x async (existing) · Alembic (existing) · `hmac`/`hashlib` stdlib · `asyncio` stdlib
- 008-github-pat-client: Added Python 3.12+ + `httpx` (already present), `re` (stdlib), `pydantic` v2 (existing), `pydantic-settings` (existing), `sqlalchemy` 2.x (existing), `alembic` (existing), `fastapi` (existing), `apscheduler` (existing)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
