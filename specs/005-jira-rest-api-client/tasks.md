# Tasks: Jira Direct REST API Client

**Input**: Design documents from `/specs/005-jira-rest-api-client/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/jira-rest-api.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- All paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Add the one new dev dependency required for testing.

- [x] T001 Add `respx` to dev dependencies in `pyproject.toml` and run `uv sync` to update `uv.lock`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Update configuration and env example so all user story phases can reference the correct settings.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Update `src/config.py`: remove `jira_mcp_url: str` and `jira_mcp_token: str`; add `jira_base_url: str = "https://yourcompany.atlassian.net"`, `jira_email: str = ""`, `jira_api_token: str = ""`
- [x] T003 [P] Update `.env.example`: replace the `# Jira MCP Server` block with a `# Jira Cloud` block containing `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`; remove `JIRA_MCP_URL` and `JIRA_MCP_TOKEN`

**Checkpoint**: Config updated — user story implementation can now begin.

---

## Phase 3: User Story 1 — Standalone Application Startup (Priority: P1) 🎯 MVP

**Goal**: The application connects to Jira using only `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`. No MCP server process required.

**Independent Test**: Set valid credentials in `.env`, start the app with `python -m src.main`, and confirm the health check or sync log shows a successful Jira connection. No separate MCP server should be running.

- [x] T004 Rewrite `src/ingestion/jira_client.py`: replace the `JiraMCPClient` class with `JiraClient` using `httpx.AsyncClient` and `httpx.BasicAuth(settings.jira_email, settings.jira_api_token)`; keep the module docstring, all Pydantic models (`JiraIssue`, `JiraSprint`, `JiraComment`), all parsing helpers (`_parse_issue`, `_parse_sprint`, `_parse_comment`, `_parse_datetime`, `_parse_date`), and `_MAX_RETRIES`/`_RETRY_BASE_SECONDS` constants unchanged; implement `__aenter__`/`__aexit__` to open and close the `httpx.AsyncClient`; implement the private `_call(method, url, **kwargs)` helper with exponential-backoff retry on HTTP 429 and 5xx only (no retry on 401/403/404); remove all `mcp` imports
- [x] T005 [P] [US1] Update import in `src/workers/sync_worker.py`: change `from src.ingestion.jira_client import JiraMCPClient` to `from src.ingestion.jira_client import JiraClient` and rename all usages of `JiraMCPClient` to `JiraClient` within that file
- [x] T006 [P] [US1] Create `tests/unit/ingestion/__init__.py` (empty) and `tests/unit/ingestion/test_jira_client.py`; write unit tests using `respx` to mock `httpx`: (a) valid credentials return the client instance, (b) HTTP 401 raises `RuntimeError` without retrying, (c) HTTP 429 is retried up to 3 times with backoff, (d) HTTP 500 is retried up to 3 times with backoff

**Checkpoint**: `python -m src.main` starts without errors and logs a Jira connection attempt. All new unit tests pass.

---

## Phase 4: User Story 2 — Scheduled Ticket Sync (Priority: P1)

**Goal**: The sync worker fetches all tickets, sprints, and comments from Jira via direct REST API calls, with full pagination support.

**Independent Test**: Run `python -m src.workers.sync_worker --run-once` and verify ticket records appear in the local SQLite database matching what is visible in Jira. No MCP server running.

- [x] T007 [US2] Implement `list_issues(project_key, max_results)` in `src/ingestion/jira_client.py`: call `GET {jira_base_url}/rest/api/3/search` with JQL `project={project_key} ORDER BY created ASC`, fetch in pages of 100 using `startAt` offset until `startAt >= total`, parse each issue with `_parse_issue`, return `list[JiraIssue]`
- [x] T008 [P] [US2] Implement `get_issue(jira_id)` in `src/ingestion/jira_client.py`: call `GET {jira_base_url}/rest/api/3/issue/{jira_id}`, parse with `_parse_issue`, return `JiraIssue | None` (return `None` on 404/403, raise on other errors after retries)
- [x] T009 [P] [US2] Implement `list_sprints(board_id)` in `src/ingestion/jira_client.py`: call `GET {jira_base_url}/rest/agile/1.0/board/{board_id}/sprint`, parse each entry with `_parse_sprint`, return `list[JiraSprint]`
- [x] T010 [P] [US2] Implement `get_comments(jira_id, max_results)` in `src/ingestion/jira_client.py`: call `GET {jira_base_url}/rest/api/3/issue/{jira_id}/comment?maxResults={max_results}`, parse each with `_parse_comment`, return `list[JiraComment]`
- [x] T011 [P] [US2] Add unit tests to `tests/unit/ingestion/test_jira_client.py` for `list_issues`: (a) single-page response returns correct `JiraIssue` list, (b) multi-page response fetches all pages and merges results, (c) empty project returns empty list
- [x] T012 [P] [US2] Add unit tests to `tests/unit/ingestion/test_jira_client.py` for `get_issue`, `list_sprints`, and `get_comments`: (a) 404 on `get_issue` returns `None`, (b) sprint list parsed correctly, (c) comments parsed with correct `issue_jira_id`

**Checkpoint**: `python -m src.workers.sync_worker --run-once` completes without errors and populates the database with tickets from all configured projects.

---

## Phase 5: User Story 3 — Ticket Updates Written Back to Jira (Priority: P2)

**Goal**: Approved AI suggestions are written directly to Jira via the REST API.

**Independent Test**: Approve a suggestion via `POST /api/v1/suggestions/{id}/approve` and verify the corresponding Jira ticket reflects the updated field value in the Jira UI.

- [x] T013 [US3] Implement `update_issue(jira_id, fields)` in `src/ingestion/jira_client.py`: call `PUT {jira_base_url}/rest/api/3/issue/{jira_id}` with JSON body `{"fields": fields}`; return `True` on HTTP 204, log error and return `False` on 403/404/4xx without raising; retry on 429/5xx per standard policy
- [x] T014 [P] [US3] Add unit tests to `tests/unit/ingestion/test_jira_client.py` for `update_issue`: (a) successful 204 returns `True`, (b) 403 logs error and returns `False` without raising, (c) 429 is retried and eventually returns `True` on success

**Checkpoint**: Approving a suggestion results in the Jira ticket being updated and the suggestion marked as applied in the local database.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, cleanup, and documentation.

- [x] T015 Run the full unit test suite (`pytest tests/unit/ -v`) and confirm all tests pass, including the 108 pre-existing tests and all new Jira client tests
- [x] T016 [P] Run `ruff check src/ingestion/jira_client.py src/config.py` and fix any linting issues
- [x] T017 [P] Update the module docstring in `src/ingestion/jira_client.py` to remove references to "MCP Server" and "SSE transport"; update the usage example to show `JiraClient` with `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN`
- [x] T018 [P] Update the module docstring in `src/workers/sync_worker.py` to remove the reference to `JiraMCPClient` and replace with `JiraClient`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1
- **US1 (Phase 3)**: Depends on Phase 2 — **must complete before US2 or US3**
- **US2 (Phase 4)**: Depends on Phase 3 (T004 must be done — methods are added to the client created in T004)
- **US3 (Phase 5)**: Depends on Phase 3 (T004), can run in parallel with Phase 4
- **Polish (Phase 6)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational phase
- **US2 (P1)**: Depends on US1 (client scaffold from T004 must exist before adding methods)
- **US3 (P2)**: Depends on US1; can proceed in parallel with US2

### Within Each Phase

- T005 and T006 can run in parallel after T004
- T007, T008, T009, T010, T011, T012 can all run in parallel after T004
- T013 and T014 can run in parallel

### Parallel Opportunities

```bash
# Phase 2 (run together):
T002  # src/config.py
T003  # .env.example

# Phase 3 (T004 first, then in parallel):
T005  # src/workers/sync_worker.py import update
T006  # tests/unit/ingestion/test_jira_client.py (auth/retry tests)

# Phase 4 (all in parallel after T004):
T007  # list_issues
T008  # get_issue
T009  # list_sprints
T010  # get_comments
T011  # list_issues tests
T012  # get_issue/list_sprints/get_comments tests

# Phase 5 (in parallel):
T013  # update_issue
T014  # update_issue tests
```

---

## Implementation Strategy

### MVP (US1 only — ~2 hours)

1. Complete Phase 1 (T001)
2. Complete Phase 2 (T002, T003)
3. Complete Phase 3 (T004, T005, T006)
4. **STOP and VALIDATE**: `python -m src.main` starts; connection to Jira confirmed
5. All existing 108 tests still pass

### Full Delivery

1. Setup + Foundational → config ready
2. US1 → client scaffold with auth + retry working
3. US2 → all read operations working, sync populates database
4. US3 → write-back working, suggestions close the loop
5. Polish → linting, docs, full test run

---

## Notes

- `[P]` tasks touch different files and have no incomplete task dependencies — safe to run in parallel
- The public interface of `JiraClient` is identical to the old `JiraMCPClient` — only the class name and transport change
- `respx` mocks `httpx` at the transport level — no real Jira API calls are made in unit tests
- Commit after each phase checkpoint to keep history clean
- The `mcp` package remains in `pyproject.toml` — it is still used by `src/copilot_mcp/`
