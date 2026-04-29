# Tasks: Copilot MCP Wrapper — Teams Transcript Bridge

**Input**: Design documents from `/specs/004-copilot-mcp-wrapper/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/mcp-tools.md ✓, quickstart.md ✓

**Tests**: Included — unit tests are written before implementation (Test-First per Constitution Principle III). Integration tests are opt-in behind `COPILOT_MCP_INTEGRATION=1`.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks in same phase)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package scaffolding and dependency registration.

- [x] T001 Create all package directories with `__init__.py` files: `src/copilot_mcp/`, `tests/unit/copilot_mcp/`, `tests/integration/copilot_mcp/`
- [x] T002 Add `msal` to `pyproject.toml` dependencies; add `respx` to dev/test dependencies
- [x] T003 [P] Add Copilot MCP env var entries to `.env.example`: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `MCP_HOST` (default `0.0.0.0`), `MCP_PORT` (default `3001`), `MCP_TOKEN` (optional), `TRANSCRIPT_LOOKBACK_DAYS` (default `7`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config and auth modules that ALL user story phases depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Implement `src/copilot_mcp/config.py` using `pydantic-settings`: required fields `azure_tenant_id`, `azure_client_id`, `azure_client_secret`; optional fields `mcp_host` (default `"0.0.0.0"`), `mcp_port` (default `3001`), `mcp_token` (default `""`), `transcript_lookback_days` (default `7`); raises `ValidationError` at import time if any required field is missing
- [x] T005 [P] Write unit tests for `src/copilot_mcp/config.py` in `tests/unit/copilot_mcp/test_config.py`: missing `AZURE_TENANT_ID` raises `ValidationError`; all required fields present loads correctly; optional fields use correct defaults; `mcp_token` empty string is treated as "no token required"
- [x] T006 Implement `src/copilot_mcp/auth.py`: `GraphTokenManager` class wrapping `msal.ConfidentialClientApplication` with in-memory token cache; `async get_token() -> str` acquires token via `asyncio.to_thread`; raises `RuntimeError` with message `"Graph API authentication failed: {error}"` if MSAL returns an error; scope is `["https://graph.microsoft.com/.default"]`
- [x] T007 [P] Write unit tests for `src/copilot_mcp/auth.py` in `tests/unit/copilot_mcp/test_auth.py`: successful token acquisition returns bearer string; cached token does not make a second MSAL call; expired token triggers re-acquisition; MSAL error raises `RuntimeError` with expected message

**Checkpoint**: Config and auth ready — all user story phases can begin

---

## Phase 3: User Story 1 — Meeting Agent Retrieves Recent Meeting List (Priority: P1) 🎯 MVP

**Goal**: `list_meetings` MCP tool returns structured meeting metadata for all tenant meetings in the lookback window, served over SSE with optional bearer token auth and `GET /health`.

**Independent Test**: Start `python -m src.copilot_mcp` → `curl /health` returns `{"status":"ok"}` → call `list_meetings` via MCP client → verify response contains meeting objects with `id`, `startedAt`, `participants`. Delivers standalone value without transcript or summary tools.

- [x] T008 [P] [US1] Write unit tests for `list_meetings` and `_follow_pages` in `tests/unit/copilot_mcp/test_graph_client.py` using `respx`: mock `GET /v1.0/communications/callRecords` returns meeting list; `_follow_pages` follows `@odata.nextLink` and merges pages; empty `value` array returns `[]`; missing `startDateTime` field causes record to be skipped with warning; `maxResults` clamped to 1–200
- [x] T009 [US1] Implement `list_meetings(token, max_results, lookback_days) -> list[MeetingRecord]` and `_follow_pages(client, url, token) -> list[dict]` in `src/copilot_mcp/graph_client.py`: `httpx.AsyncClient` calls `GET /v1.0/communications/callRecords?$filter=startDateTime ge {date}&$top={max_results}`; pagination via `@odata.nextLink`; maps raw response to `MeetingRecord` dataclass per `data-model.md`; skips records with no `startDateTime` and logs warning
- [x] T010 [US1] Implement `src/copilot_mcp/server.py`: `FastMCP` instance; `@mcp.tool()` for `list_meetings` with optional `maxResults` int param (default 50); Starlette middleware rejects requests with wrong `Authorization: Bearer` header (HTTP 401) when `MCP_TOKEN` is set; `Route("/health", ...)` returns `{"status": "ok"}` with 200; compose ASGI app
- [x] T011 [P] [US1] Write unit tests for `server.py` US1 surface in `tests/unit/copilot_mcp/test_server.py`: `GET /health` returns `200 {"status":"ok"}` without Graph API call; missing `MCP_TOKEN` header returns `401` when token is configured; `list_meetings` tool input schema has optional `maxResults`; `list_meetings` tool output matches wire shape in `contracts/mcp-tools.md` (`id`, `title`, `startedAt`, `endedAt`, `participants`)

**Checkpoint**: US1 fully functional — `list_meetings` tool works end-to-end with health check

---

## Phase 4: User Story 2 — Meeting Agent Retrieves Speaker-Attributed Transcript (Priority: P1)

**Goal**: `get_transcript` MCP tool returns a complete speaker-attributed transcript assembled from VTT content, or `null` if unavailable.

**Independent Test**: Call `get_transcript` with a known meeting ID → verify response contains `rawTranscript` string with `"Speaker: text\n"` format; call with an unknown ID → verify `null` is returned. Testable without `list_meetings` or summary tool.

- [x] T012 [P] [US2] Write unit tests for `get_transcript`, `_parse_vtt`, and transcript list pagination in `tests/unit/copilot_mcp/test_graph_client.py`: VTT with `<v Speaker>` tags parsed to correct `TranscriptSegment` list; `@odata.nextLink` on transcript list followed and most-recent transcript selected; Graph API 404 returns `None`; non-UTF-8 bytes replaced with `?`; empty VTT returns `None`
- [x] T013 [US2] Implement `get_transcript(token, meeting_id) -> TranscriptOut | None` and `_parse_vtt(vtt_text) -> list[TranscriptSegment]` in `src/copilot_mcp/graph_client.py`: resolve `organizer_id` from cached `MeetingRecord` (looked up by `meeting_id`); `GET /v1.0/users/{organizer_id}/onlineMeetings/{meeting_id}/transcripts` to list transcripts; select most-recent; `GET .../content?$format=text/vtt` for VTT content; parse VTT cues to `"Speaker: text\n"` lines assembled into `rawTranscript`; return `None` on 404, empty content, or parse failure
- [x] T014 [US2] Wire `get_transcript` MCP tool in `src/copilot_mcp/server.py`: `@mcp.tool()` with required `meetingId` string param; empty/missing `meetingId` returns MCP structured error `{"error": "missing_param", "param": "meetingId"}`; `None` from graph client returned as JSON `null`; output matches `TranscriptOut` wire shape in `contracts/mcp-tools.md`
- [x] T015 [P] [US2] Write unit tests for `server.py` US2 surface in `tests/unit/copilot_mcp/test_server.py`: empty `meetingId` returns MCP structured error; valid ID with no transcript returns `null`; valid ID with transcript returns object with `rawTranscript`; `rawTranscript` field contains `"Speaker: text\n"` lines

**Checkpoint**: US2 fully functional — `get_transcript` returns speaker-attributed transcript or null

---

## Phase 5: User Story 3 — Meeting Agent Retrieves Copilot Meeting Summary (Priority: P2)

**Goal**: `get_meeting_summary` MCP tool returns Copilot-generated summary and action items, or `null` when unavailable.

**Independent Test**: Call `get_meeting_summary` with a meeting ID for a Copilot-enabled meeting → verify response has `summary` string and `actionItems` list; call for a non-Copilot meeting → verify `null`. Testable without transcript tool.

- [x] T016 [P] [US3] Write unit tests for `get_meeting_summary` in `tests/unit/copilot_mcp/test_graph_client.py`: beta `meetingCaption` response parsed to `MeetingSummaryRecord`; 404 returns `None`; empty `actionItems` returns empty list; non-Copilot tenant (403) returns `None` with warning logged
- [x] T017 [US3] Implement `get_meeting_summary(token, meeting_id) -> SummaryOut | None` in `src/copilot_mcp/graph_client.py`: resolve `organizer_id` from cached `MeetingRecord`; `GET /beta/users/{organizer_id}/onlineMeetings/{meeting_id}/meetingCaption`; map `summary` and `actionItems` fields; return `None` on 404 or 403; log warning on 403 (Copilot not licensed)
- [x] T018 [US3] Wire `get_meeting_summary` MCP tool in `src/copilot_mcp/server.py`: `@mcp.tool()` with required `meetingId`; empty/missing `meetingId` returns structured error; `None` returned as JSON `null`; output matches `SummaryOut` wire shape in `contracts/mcp-tools.md`
- [x] T019 [P] [US3] Write unit tests for `server.py` US3 surface in `tests/unit/copilot_mcp/test_server.py`: empty `meetingId` returns structured error; Copilot-disabled meeting returns `null`; Copilot-enabled meeting returns `summary` + `actionItems`

**Checkpoint**: US3 fully functional — `get_meeting_summary` returns summary or null gracefully

---

## Phase 6: User Story 4 — Operator Configures and Validates the Server (Priority: P2)

**Goal**: Operator can validate Graph API credentials and permission scopes before starting the server, and gets a clear error on misconfiguration.

**Independent Test**: Run `python -m src.copilot_mcp --validate` with correct credentials → all checks pass and exit 0; run with wrong secret → auth failure message and exit 1. Testable without an active MCP client.

- [x] T020 [US4] Implement `src/copilot_mcp/__main__.py`: `argparse` with `--validate` flag; when `--validate` passed, call `GraphTokenManager.get_token()` → verify `CallRecords.Read.All` and `OnlineMeetings.Read.All` scopes in the token claims → print `[✓]` / `[✗]` per check → exit 0 on all pass, exit 1 on any failure; without `--validate`, call `uvicorn.run()` with composed ASGI app from `server.py` on `MCP_HOST:MCP_PORT`; log startup lines per `quickstart.md §5`
- [x] T021 [P] [US4] Write unit tests for `src/copilot_mcp/__main__.py` in `tests/unit/copilot_mcp/test_main.py`: `--validate` with missing `AZURE_TENANT_ID` exits non-zero with message containing `"AZURE_TENANT_ID"`; `--validate` with MSAL auth failure exits non-zero with message containing auth error; `--validate` with missing permission scope prints `[✗] {scope_name}: MISSING` and exits non-zero; all checks pass → prints `[✓]` lines and exits 0

**Checkpoint**: US4 fully functional — operator can validate connectivity before deploying

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Reliability hardening and end-to-end validation.

- [x] T022 [P] Implement 429 retry with `Retry-After` backoff in `src/copilot_mcp/graph_client.py`: on HTTP 429 response, wait `Retry-After` header seconds (or 30s if absent), retry up to 3 total attempts; after 3 failures raise `RuntimeError("Graph API rate limit exceeded after retries")` which the tool layer converts to MCP tool error
- [x] T023 [P] Write unit tests for 429 retry in `tests/unit/copilot_mcp/test_graph_client.py`: single 429 then 200 succeeds and returns data; three consecutive 429s raises `RuntimeError`; `Retry-After: 5` header respected (mock `asyncio.sleep`); missing `Retry-After` defaults to 30s wait
- [x] T024 [P] Write integration test scaffolding in `tests/integration/copilot_mcp/test_mcp_tools.py`: skip all tests unless `COPILOT_MCP_INTEGRATION=1`; full pipeline: `list_meetings` → take first result → `get_transcript(id)` → `get_meeting_summary(id)`; assert each returns expected types or `null` (never raises); assert `rawTranscript` contains at least one `"Speaker: text"` line if not null
- [ ] T025 Validate end-to-end per `quickstart.md`: run `python -m src.copilot_mcp --validate`; start server; `curl http://localhost:3001/health` returns `{"status":"ok"}`; set `COPILOT_MCP_URL` and `COPILOT_MCP_TOKEN` in Meeting Agent `.env`; run `python -m src.workers.sync_worker --run-once` and confirm log line `"Ingested transcript for meeting"` appears; fix any integration issues found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2; independent of US2–US4; delivers usable server alone
- **US2 (Phase 4)**: Depends on Phase 2 + US1 (`graph_client.py` extended; `MeetingRecord` cache populated by `list_meetings` call)
- **US3 (Phase 5)**: Depends on Phase 2 + US1 (same `organizer_id` resolution path)
- **US4 (Phase 6)**: Depends on Phase 2 only (`__main__.py` calls auth + config directly)
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: First — establishes `graph_client.py`, `server.py`, `FastMCP` instance, `/health`, auth middleware; MVP baseline
- **US2 (P1)**: After US1 — extends `graph_client.py` with `get_transcript`; extends `server.py` with second tool
- **US3 (P2)**: After US1 — extends `graph_client.py` with `get_meeting_summary`; can be developed in parallel with US2
- **US4 (P2)**: After Phase 2 — `__main__.py` is independent of US1–US3 implementation

### Within Each User Story

- Unit tests written and confirmed failing BEFORE implementation
- `graph_client.py` functions before `server.py` tool wiring
- Tool wiring before server-level unit tests
- All tasks in a phase before moving to next phase

### Parallel Opportunities

- **Phase 1**: T002 and T003 run in parallel after T001
- **Phase 2**: T005 runs in parallel with T004; T007 runs in parallel with T006
- **Phase 3**: T008 (tests) runs in parallel with starting T009 (implementation)
- **Phase 4**: T012 (tests) runs in parallel with starting T013 (implementation)
- **Phase 5**: T016 (tests) runs in parallel with starting T017 (implementation); US3 can be developed in parallel with US2 after Phase 2
- **Phase 6**: T021 (tests) runs in parallel with T020 (implementation); US4 can be developed in parallel with US2/US3
- **Phase 7**: T022, T023, T024 run in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2 checkpoint (T007 complete):

# Launch in parallel:
Task T008: "Write unit tests for list_meetings in tests/unit/copilot_mcp/test_graph_client.py"

# Sequential pipeline (T008 must fail before T009 begins):
Task T009: "Implement list_meetings() and _follow_pages() in src/copilot_mcp/graph_client.py"
Task T010: "Implement server.py: FastMCP, list_meetings tool, /health, auth middleware"

# After T010, parallel:
Task T011: "Write unit tests for server.py list_meetings surface"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T007) — **CRITICAL: blocks everything**
3. Complete Phase 3: User Story 1 (T008–T011)
4. **STOP and VALIDATE**: `python -m src.copilot_mcp` → `curl /health` → MCP `list_meetings` call → confirm meeting list returned
5. Configure Meeting Agent with server URL and run `sync_worker --run-once` to confirm connectivity

### Incremental Delivery

1. **Foundation** → **US1** (`list_meetings` + `/health`) → validate connectivity with Meeting Agent
2. + **US2** (`get_transcript`) → run full transcript ingestion cycle end-to-end
3. + **US3** (`get_meeting_summary`) → verify summary enrichment in suggestions pipeline
4. + **US4** (`--validate`) → operator experience complete
5. + **Polish** (429 retry, integration tests, end-to-end) → production-ready

### Parallel Team Strategy

After Phase 2 complete:
- **Developer A**: US2 — `get_transcript` + VTT parsing (T012–T015)
- **Developer B**: US3 — `get_meeting_summary` (T016–T019)
- **Developer C**: US4 — `__main__.py` + `--validate` (T020–T021)

---

## Notes

- [P] tasks target different files with no unresolved dependencies within their phase
- [Story] label maps each task to a user story for traceability
- Unit tests for each module MUST be written before implementation (Constitution Principle III)
- `respx` is the mock library for `httpx` — do not use `unittest.mock.patch` on httpx directly
- `MeetingRecord` cache (populated during `list_meetings`) is used by `get_transcript` and `get_meeting_summary` to resolve `organizer_id` — US2 and US3 depend on a prior `list_meetings` call having been made in the same session
- Integration tests require `COPILOT_MCP_INTEGRATION=1` env var — never run in default CI
- Commit after each task or logical group; stop at any checkpoint to validate the story independently
