# Implementation Plan: Copilot MCP Wrapper — Teams Transcript Bridge

**Branch**: `003-copilot-mcp-wrapper` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-copilot-mcp-wrapper/spec.md`

## Summary

Build a standalone Python MCP server (`src/copilot_mcp/`) that authenticates to the Microsoft Graph API via OAuth 2.0 client credentials and exposes three tools — `list_meetings`, `get_transcript`, `get_meeting_summary` — over SSE transport. The server plugs into the existing Meeting Agent ingestion layer via `COPILOT_MCP_URL` / `COPILOT_MCP_TOKEN` env vars with no changes to `src/ingestion/copilot_client.py`.

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: `mcp` (FastMCP + SSE transport), `msal` (OAuth2 client credentials), `httpx` (async Graph API calls), `fastapi`/`starlette` + `uvicorn` (ASGI host, already in project), `pydantic-settings` (config, already in project)
**Storage**: None — stateless server; `msal` in-memory token cache only
**Testing**: `pytest` + `pytest-asyncio` + `respx` (httpx mock); unit tests for all modules; opt-in integration tests behind `COPILOT_MCP_INTEGRATION=1`
**Target Platform**: Linux/macOS server process or container
**Project Type**: Standalone network service (MCP server)
**Performance Goals**: `list_meetings` ≤ 3s (100 meetings); `get_transcript` ≤ 10s (paginated, ≤500 utterances); `GET /health` ≤ 1s
**Constraints**: Single client; TLS terminated externally; no persistent state
**Scale/Scope**: Single Azure tenant; one concurrent MCP client (Meeting Agent)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | ✅ PASS | 5 files, each with a clearly bounded concern |
| II. Single Responsibility | ✅ PASS | `auth.py` only manages tokens; `graph_client.py` only calls Graph API; `server.py` only wires MCP tools |
| III. Test-First | ✅ PASS | Unit tests written before implementation per tasks phase ordering |
| IV. Agent Composability | ✅ PASS | Each MCP tool is independently invocable with well-typed JSON schemas |
| V. YAGNI | ✅ PASS | No multi-tenant, no stdio, no per-call lookback override, no tool subdirectory until justified |

No violations — Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/004-copilot-mcp-wrapper/
├── plan.md           ← this file
├── research.md       ← Phase 0 output
├── data-model.md     ← Phase 1 output
├── quickstart.md     ← Phase 1 output
├── contracts/
│   └── mcp-tools.md  ← Phase 1 output
└── tasks.md          ← Phase 2 output (/speckit.tasks)
```

### Source Code

```text
src/copilot_mcp/
├── __init__.py
├── __main__.py          # Entry point: uvicorn.run() + --validate CLI flag
├── config.py            # pydantic-settings: reads AZURE_*, MCP_*, TRANSCRIPT_* env vars
├── auth.py              # msal.ConfidentialClientApplication wrapper; get_token() -> str
├── graph_client.py      # All httpx.AsyncClient Graph API calls:
│                        #   list_meetings(token, max_results, lookback_days) -> list[MeetingRecord]
│                        #   get_transcript(token, meeting_id, organizer_id) -> TranscriptOut | None
│                        #   get_meeting_summary(token, meeting_id, organizer_id) -> SummaryOut | None
│                        #   _follow_pages(client, url, token) -> list[dict]   (pagination helper)
│                        #   _parse_vtt(vtt_text) -> list[TranscriptSegment]  (VTT parser)
└── server.py            # FastMCP instance; @mcp.tool() for all 3 tools;
                         # Starlette app with /health route; inbound token auth middleware

tests/
├── unit/
│   └── copilot_mcp/
│       ├── __init__.py
│       ├── test_config.py          # Env var validation, missing var errors
│       ├── test_auth.py            # Token acquisition, cache hit, refresh on expiry
│       ├── test_graph_client.py    # list_meetings, get_transcript, get_meeting_summary,
│       │                           # _parse_vtt, _follow_pages, 429 backoff, null returns
│       └── test_server.py          # /health endpoint, MCP tool schemas, inbound 401
└── integration/
    └── copilot_mcp/
        ├── __init__.py
        └── test_mcp_tools.py       # Full tool calls against real Graph API (opt-in)
```

---

## Key Design Decisions (from research.md)

| Area | Decision |
|------|----------|
| `list_meetings` Graph endpoint | `GET /v1.0/communications/callRecords?$filter=startDateTime ge {date}` |
| `get_transcript` Graph endpoint | `GET /v1.0/users/{organizer-id}/onlineMeetings/{id}/transcripts/{tid}/content?$format=text/vtt` |
| `get_meeting_summary` Graph endpoint | `GET /beta/users/{organizer-id}/onlineMeetings/{id}/meetingCaption` |
| Auth library | `msal.ConfidentialClientApplication` (in-memory token cache) |
| Token refresh | `asyncio.to_thread` wraps synchronous `msal` call |
| MCP framework | `FastMCP` from `mcp` SDK (decorator-based, Starlette SSE) |
| Health endpoint | Starlette `Route("/health", ...)` mounted on same ASGI app |
| HTTP mocking in tests | `respx` library for `httpx` |

---

## Complexity Tracking

> No Constitution Check violations — table not required.
