# Research: Copilot MCP Wrapper — Teams Transcript Bridge

**Branch**: `003-copilot-mcp-wrapper` | **Date**: 2026-04-05

---

## 1. Graph API Endpoint Strategy for `list_meetings` (Org-Wide)

**Decision**: Use `GET /v1.0/communications/callRecords` (with `CallRecords.Read.All` application permission) as the primary endpoint for listing meetings across the tenant.

**Rationale**: The `callRecords` API is purpose-built for org-wide, app-only access. Unlike the `onlineMeetings` API — which requires per-user enumeration (`GET /users/{id}/onlineMeetings`) and an additional `User.Read.All` permission — `callRecords` returns all calls/meetings in the tenant in a single paginated feed filtered by `startDateTime`. This directly satisfies the clarified requirement (org-wide, all organisers) without the complexity of user enumeration.

**Alternatives considered**:
- **Per-user enumeration via `/users/{id}/onlineMeetings`**: Requires `User.Read.All` plus iterating every user. Rejected — O(N users) API calls, fragile when user count is large.
- **Subscription/webhook to callRecords**: Event-driven, avoids polling. Rejected per YAGNI — the Meeting Agent polls on a 15-minute cycle; push delivery adds infrastructure complexity without benefit.

**Required permission**: `CallRecords.Read.All` (application).

---

## 2. Graph API Endpoint Strategy for `get_transcript`

**Decision**: Two-step resolution: (1) resolve the `callRecord` → `joinWebUrl` → online meeting ID; (2) fetch transcript content via `GET /users/{organizer-id}/onlineMeetings/{meetingId}/transcripts/{transcriptId}/content?$format=text/vtt`.

**Rationale**: The `callRecords` API returns a `joinWebUrl` per session, which encodes the meeting's online meeting ID. Transcripts are stored under the organiser's `onlineMeetings` resource. The VTT format provides speaker attribution (`WEBVTT`, `NOTE speaker: DisplayName`) and timestamps per utterance — sufficient for the `"Speaker: text\n"` output format required by the ingestion layer.

**Transcript content parsing**: VTT cues are parsed to extract speaker display name (from `NOTE` blocks or `<v Speaker>` tags) and text. Output is assembled as a single `\n`-delimited string of `"Speaker: text"` lines, with `timestampSeconds` derived from the VTT cue start time.

**Pagination**: Transcript content is returned as a single file (not paged). The transcripts *list* (`GET .../transcripts`) may be paged via `@odata.nextLink` if multiple transcript versions exist; the most recent is selected.

**Required permission**: `OnlineMeetings.Read.All` (application).

**Alternatives considered**:
- **JSON transcript format** (`$format=application/json`): Provides structured segments but is a beta endpoint with less stable schema. Rejected in favour of stable VTT.
- **`callRecord/sessions/segments` transcription field**: Available in beta, not v1.0. Rejected for stability.

---

## 3. Graph API Endpoint Strategy for `get_meeting_summary`

**Decision**: Use `GET /beta/users/{organizer-id}/onlineMeetings/{meetingId}/meetingCaption` for Copilot-generated summaries, with `GET /beta/users/{organizer-id}/onlineMeetings/{meetingId}/transcripts/{id}/metadataContent` as a fallback for action items.

**Rationale**: Microsoft 365 Copilot meeting summaries are exposed through the beta Graph API under the `meetingCaption` resource. This endpoint returns `summary` (full AI-generated summary text) and `actionItems` (structured list). Where `meetingCaption` is unavailable (Copilot not licensed or not completed), the endpoint returns 404 — the tool returns `null`.

**Beta API risk mitigation**: The `meetingCaption` endpoint is beta-only. This is acceptable because: (a) `get_meeting_summary` is a P2 feature that degrades gracefully to `null`, (b) the Meeting Agent's pipeline does not block on summary availability, (c) when Microsoft promotes the endpoint to v1.0, only the URL prefix changes.

**Alternatives considered**:
- **Parse summary from transcript VTT**: Copilot sometimes appends summary text to the VTT file. Unreliable — not a guaranteed format. Rejected.
- **Teams meeting notes via OneNote API**: Copilot notes are sometimes stored in OneNote. Adds `Notes.Read.All` permission and complex graph traversal. Rejected per YAGNI.

---

## 4. OAuth 2.0 Client Credentials — Library Choice

**Decision**: Use `msal` (Microsoft Authentication Library for Python) for token acquisition and refresh.

**Rationale**: `msal` is Microsoft's officially supported Python library for AAD/Entra ID authentication. `ConfidentialClientApplication.acquire_token_for_client(scopes)` handles token caching and silent refresh natively — if a cached token is still valid, no network call is made; if expired, a new one is fetched transparently. This satisfies FR-008 (automatic refresh) with zero custom token lifecycle code.

**Token cache**: In-memory only (`SerializableTokenCache` backed by a dict). No file or Redis cache — single process, single client, no persistence needed (token is re-acquired on cold start, cheap).

**Scope**: `["https://graph.microsoft.com/.default"]` — acquires all permissions granted to the app registration.

**Alternatives considered**:
- **Raw `httpx` POST to `/oauth2/v2.0/token`**: Works but requires manual expiry tracking and refresh logic. Rejected — `msal` provides this for free.
- **`azure-identity` `ClientSecretCredential`**: Also valid but designed for the `azure-sdk` ecosystem. `msal` is lighter and sufficient here.

---

## 5. MCP Server Transport and Framework

**Decision**: Use the `mcp` Python SDK's `FastMCP` server class with Starlette/uvicorn for SSE transport. Mount `GET /health` as a standard Starlette route on the same ASGI app.

**Rationale**: `FastMCP` (added in mcp SDK 1.x) provides a decorator-based tool registration API (`@mcp.tool()`) that is clean, minimal, and directly exposes well-typed tool schemas. The underlying SSE transport is a Starlette ASGI app, so adding `/health` is a one-line `Route` addition — no second HTTP server process needed.

**Entry point**: `python -m src.copilot_mcp` starts uvicorn with the composed ASGI app.

**Alternatives considered**:
- **Raw `mcp.server.Server` with manual tool dispatch**: More control but verbose boilerplate. Rejected — `FastMCP` satisfies all requirements with less code (YAGNI).
- **Separate HTTP server for `/health` (e.g., threading + `http.server`)**: Works but two processes sharing a port is fragile. Rejected — single ASGI app is cleaner.
- **stdio transport**: Out of scope per spec clarification.

---

## 6. Module Structure

**Decision**: Flat module under `src/copilot_mcp/` with five files: `config.py`, `auth.py`, `graph_client.py`, `server.py`, `__main__.py`. No tools subdirectory — each tool is a decorated function in `server.py` since all three tools share the same Graph client dependency.

**Rationale**: Five focused files each with a single responsibility (config, auth, Graph HTTP, MCP wiring, entry point). A `tools/` subdirectory would add indirection for only 3 functions — unjustified per YAGNI and Constitution Principle V. If a fourth tool is added, splitting is straightforward.

**Responsibilities**:
- `config.py`: Reads and validates env vars via `pydantic-settings`; raises on missing required vars at import time.
- `auth.py`: Wraps `msal.ConfidentialClientApplication`; exposes `get_token() -> str` (sync, thread-safe via `asyncio.to_thread`).
- `graph_client.py`: All `httpx.AsyncClient` Graph API calls; `list_meetings()`, `get_transcript()`, `get_meeting_summary()` as pure async functions that receive a bearer token.
- `server.py`: `FastMCP` instance; `@mcp.tool()` wrappers that call `graph_client`; Starlette app composition with `/health` route.
- `__main__.py`: `uvicorn.run()` entry point + `--validate` CLI flag handling.

**Alternatives considered**:
- **`tools/` subdirectory with one file per tool**: Cleaner if tools diverge significantly, but premature for 3 simple wrappers. Deferred.
- **Single `server.py` monolith**: Violates Principle II (single responsibility). Rejected.

---

## 7. Testing Strategy

**Decision**: Unit tests mock the `httpx` transport layer (using `respx`) and the `msal` token call. Integration tests (skipped in CI unless `COPILOT_MCP_INTEGRATION=1`) call the real Graph API against a test tenant.

**Unit test targets**:
- `auth.py`: token acquisition, cache hit/miss, token refresh on expiry
- `graph_client.py`: VTT parsing, pagination merge, 429 backoff, null returns for missing transcripts
- `server.py`: MCP tool schema correctness, `/health` response, missing param errors, inbound token rejection

**Rationale**: Graph API VTT parsing and pagination merge logic are pure data-transformation functions — ideal unit test targets. `respx` allows `httpx` mocking without monkey-patching. Integration tests validate the full auth + Graph + MCP chain but require real credentials, so they are opt-in.

**Alternatives considered**:
- **`unittest.mock.patch` on `httpx`**: Works but more brittle than `respx` for async HTTP. Rejected.
- **Full integration tests only**: Requires real credentials in CI. Rejected for the default test suite.
