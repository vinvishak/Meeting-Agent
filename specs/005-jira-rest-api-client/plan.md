# Implementation Plan: Jira Direct REST API Client

**Branch**: `005-jira-rest-api-client` | **Date**: 2026-04-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-jira-rest-api-client/spec.md`

## Summary

Replace `src/ingestion/jira_client.py` — which connects to a Jira MCP server via SSE — with a direct async HTTP client that calls the Jira Cloud REST API v3 using HTTP Basic Auth (email + API token). Update `src/config.py` and `.env.example` to replace the two MCP-specific settings (`JIRA_MCP_URL`, `JIRA_MCP_TOKEN`) with three direct-connection settings (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`). All Pydantic models and parsing logic remain unchanged. No other modules are affected.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: `httpx` (async HTTP, already a transitive dependency), `pydantic` v2 (existing), `pydantic-settings` (existing)
**Storage**: SQLite via existing Alembic schema — no schema changes
**Testing**: `pytest` + `pytest-asyncio`, `respx` for mocking httpx calls
**Target Platform**: macOS / Linux server (standalone process)
**Project Type**: Web service + background worker
**Performance Goals**: Full project sync completes in under 60 seconds for projects up to 1,000 tickets
**Constraints**: Must not break any of the 108 existing unit tests; no new top-level packages
**Scale/Scope**: Single Jira Cloud workspace; up to ~10 projects, ~1,000 tickets per sync cycle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | PASS | `jira_client.py` is a self-contained module; only that file and `config.py` change |
| II. Single Responsibility | PASS | Client owns exactly one concern: Jira data access |
| III. Test-First | PASS | Unit tests written before implementation; `respx` mocks httpx |
| IV. Agent Composability | PASS | Client is an async context manager with typed inputs/outputs — unchanged interface |
| V. Simplicity First (YAGNI) | PASS | Replacing MCP wrapper with direct HTTP is the simplest path; no new abstractions |

**Post-design re-check**: No violations. No Complexity Tracking entry required.

## Project Structure

### Documentation (this feature)

```text
specs/005-jira-rest-api-client/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── jira-rest-api.md
└── tasks.md
```

### Source Code (modified files only)

```text
src/
├── config.py                    # Replace jira_mcp_url/token → jira_base_url/email/api_token
└── ingestion/
    └── jira_client.py           # Replace MCP SSE transport with httpx REST client

tests/
└── unit/
    └── ingestion/
        └── test_jira_client.py  # New: unit tests using respx to mock Jira API

.env.example                     # Updated Jira config block
```

**Structure Decision**: Single project, modifying two existing source files and one config file. No new packages or directories in `src/`.
