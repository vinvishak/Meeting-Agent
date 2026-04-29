# Meeting_Agent Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-05

## Active Technologies
- Python 3.12+ + `argparse` (stdlib), `getpass` (stdlib), `httpx` (transitive dep via fastapi), `anthropic` (existing), `alembic` (existing), `pydantic-settings` (existing) (002-add-quickstart-option)
- No new persistent storage; existing SQLite DB initialized via Alembic (002-add-quickstart-option)
- Python 3.12+ + `mcp` (FastMCP + SSE transport), `msal` (OAuth2 client credentials), `httpx` (async Graph API calls), `fastapi`/`starlette` + `uvicorn` (ASGI host, already in project), `pydantic-settings` (config, already in project) (004-copilot-mcp-wrapper)
- None — stateless server; `msal` in-memory token cache only (004-copilot-mcp-wrapper)

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
- 004-copilot-mcp-wrapper: Added Python 3.12+ + `mcp` (FastMCP + SSE transport), `msal` (OAuth2 client credentials), `httpx` (async Graph API calls), `fastapi`/`starlette` + `uvicorn` (ASGI host, already in project), `pydantic-settings` (config, already in project)
- 002-add-quickstart-option: Added Python 3.12+ + `argparse` (stdlib), `getpass` (stdlib), `httpx` (transitive dep via fastapi), `anthropic` (existing), `alembic` (existing), `pydantic-settings` (existing)

- 001-jira-copilot-intelligence: Added Python 3.12+ + `anthropic` (Claude API), `mcp` (MCP Python SDK), `fastapi`, `pydantic` v2, `sqlalchemy` 2.x, `rapidfuzz` (entity matching), `apscheduler` (15-min sync scheduler), `pytest` + `pytest-asyncio`

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
