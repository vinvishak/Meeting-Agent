# Tasks: Real-Time GitHub Activity Stream

**Input**: Design documents from `/specs/009-github-live-stream/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Context**: This is a retroactive speckit run. Core implementation is already complete.
The highest-priority gap is test coverage (Constitution Principle III violation documented in plan.md).

**Organization**: Tasks are grouped by user story. Implemented tasks are verified; missing tasks are created.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify foundational config and DB schema are in place

- [X] T001 Verify Alembic migration `src/storage/migrations/versions/002_github_schema.py` defines all 4 tables: `github_repos`, `github_commits`, `github_pull_requests`, `github_jira_links`
- [X] T002 Verify `github_webhook_secret: str = ""` field is present in `Settings` class in `src/config.py`
- [X] T003 Add `GITHUB_WEBHOOK_SECRET` entry to `.env.example` with an explanatory comment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure shared by all user stories — broadcaster, auth exemptions, route registration

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Verify `src/api/broadcaster.py` exports `broadcast(event)`, `subscribe()`, and `unsubscribe(q)` using `asyncio.Queue`
- [X] T005 Verify `src/api/middleware/auth.py` includes `/api/v1/webhooks/` and `/api/v1/stream` in `_PUBLIC_PREFIXES`
- [X] T006 Verify `src.api.routes.webhooks` is registered in `_register_routes()` in `src/api/app.py` and that `AsyncIOScheduler` is started in the lifespan context

**Checkpoint**: Broadcaster, auth exemptions, and route registration confirmed — user story phases can proceed

---

## Phase 3: User Story 1 — Live Commit Feed on Dashboard (Priority: P1) 🎯 MVP

**Goal**: Engineers see new commits appear in the dashboard activity feed within 5 seconds, without refreshing, via SSE.

**Independent Test**: Open the dashboard, send a simulated push webhook, confirm a commit card appears at the top of the feed within 5 seconds and the Live badge is green.

### Tests for User Story 1 ⚠️ (Constitution compliance — write first)

> **NOTE: These tests must be created. They address the Test-First gate violation documented in plan.md.**

- [X] T007 [P] [US1] Create `tests/unit/api/__init__.py` (empty) to make the package importable
- [X] T008 [P] [US1] Write unit tests for `src/api/broadcaster.py` in `tests/unit/api/test_broadcaster.py` — test: `subscribe()` returns a Queue; `broadcast(event)` puts event on all subscribed queues; `unsubscribe(q)` removes the queue; unsubscribing a queue not in the list does not raise
- [X] T009 [P] [US1] Write unit tests for the SSE stream in `tests/unit/api/test_webhooks.py` — generator yields retry directive as first chunk; stream endpoint is in public auth prefixes

### Implementation for User Story 1

- [X] T010 [US1] Verify `GET /api/v1/stream` SSE endpoint is implemented in `src/api/routes/webhooks.py` — confirm: generator subscribes/unsubscribes, sends `retry: 3000`, yields `data: …\n\n` on events, yields `: keepalive\n\n` on 20 s timeout
- [X] T011 [P] [US1] Verify Live badge HTML/CSS is present in `frontend/index.html` — confirm `.live-badge`, `.live-dot`, `pulse-dot` animation, and `glow-in` animation are defined
- [X] T012 [US1] Verify `initSSE()` function is implemented in `frontend/index.html` — confirm: creates `EventSource` to `/api/v1/stream`, shows Live badge on `open`, calls `prependLiveCommit(event.commit)` on `new_commit` messages, hides badge on `error`
- [X] T013 [US1] Verify `prependLiveCommit(commit)` function is implemented in `frontend/index.html` — confirm: creates `.activity-item.activity-item-live` card with sha, author, message, repo, jira keys, prepends to `.activity-feed`, removes empty-state if present, updates freshness indicator
- [X] T014 [US1] Verify `initSSE()` is called during `DOMContentLoaded` in `frontend/index.html`

**Checkpoint**: User Story 1 complete — open dashboard, trigger webhook, confirm live commit card appears

---

## Phase 4: User Story 2 — Webhook Ingestion and Persistence (Priority: P2)

**Goal**: Every valid push webhook is authenticated, persisted to SQLite, and Jira keys are extracted.

**Independent Test**: POST a valid push webhook payload, query `github_commits` and `github_jira_links` tables, confirm rows are created; POST with wrong signature, confirm 403 and no DB rows.

### Tests for User Story 2 ⚠️ (Constitution compliance — write first)

- [X] T015 [P] [US2] Write unit tests for `_verify_signature()` in `tests/unit/api/test_webhooks.py` — test: valid HMAC returns True; wrong signature returns False; empty secret returns True (dev mode); mismatched signature returns False
- [X] T016 [P] [US2] Write unit tests for `POST /api/v1/webhooks/github` in `tests/unit/api/test_webhooks.py` — test: ping event returns `{ok:true, message:"pong"}`; push with empty commits returns `{ok:true}` without DB write; push with invalid signature returns 403; valid push with commits returns `{ok:true}` and schedules background ingestion

### Implementation for User Story 2

- [X] T017 [US2] Verify `_verify_signature(secret, body, sig_header)` pure function in `src/api/routes/webhooks.py` — confirm HMAC-SHA256 using `hmac.compare_digest`, dev-mode bypass when secret is empty
- [X] T018 [US2] Verify `POST /api/v1/webhooks/github` endpoint in `src/api/routes/webhooks.py` — confirm: reads raw body before parsing, calls `_verify_signature`, handles `ping` and `push` events, skips empty `commits` arrays, dispatches `_ingest_push` as a `BackgroundTask`
- [X] T019 [US2] Verify `_ingest_push(payload)` background task in `src/api/routes/webhooks.py` — confirm: calls `GitHubRepository.upsert_repo`, `upsert_commit` for each commit, `extract_jira_keys` + `upsert_jira_link` for Jira references, `broadcast()` for each commit event, and `session.commit()`

**Checkpoint**: User Story 2 complete — valid webhooks persist to DB and invalid ones are rejected

---

## Phase 5: User Story 3 — Historical Activity Feed on Page Load (Priority: P3)

**Goal**: When the dashboard first loads, the activity feed is pre-populated with the most recent commits from the database.

**Independent Test**: Run Scenario 5 from quickstart.md — load dashboard after commits exist in DB, confirm feed shows commits before any new webhook fires.

### Implementation for User Story 3

- [X] T020 [US3] Verify `GET /api/v1/github/commits` endpoint exists in `src/api/routes/github.py` with `limit` and `offset` query params, returning `{commits, total, limit, offset}`
- [X] T021 [US3] Verify `frontend/index.html` fetches `/api/v1/github/commits?limit=10` on page load and renders commit cards in the activity feed alongside other activity sources

**Checkpoint**: User Story 3 complete — page load shows historical commits without requiring a live event

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Run all quickstart.md validation scenarios and confirm format compliance

- [X] T022 Run `pytest tests/unit/api/` and confirm all tests pass — 16/16 passed in 0.57s
- [ ] T023 [P] Run quickstart.md Scenario 1 (happy path — live commit appears) against local server
- [ ] T024 [P] Run quickstart.md Scenario 2 (HMAC rejection) against local server
- [ ] T025 [P] Run quickstart.md Scenario 3 (Jira key extraction) and verify DB rows
- [ ] T026 [P] Run quickstart.md Scenario 4 (duplicate delivery idempotency) and verify count = 1
- [X] T027 Run `ruff check src/api/broadcaster.py src/api/routes/webhooks.py tests/unit/api/` and fix any lint errors — all checks passed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — tests first, then verify implementation
- **US2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 once Phase 2 is done
- **US3 (Phase 5)**: Depends on Phase 2 — can run in parallel with US1/US2
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 all being complete

### User Story Dependencies

- **US1 (P1)**: Independent — needs only the broadcaster (foundational)
- **US2 (P2)**: Independent — needs only the DB models (foundational)
- **US3 (P3)**: Independent — needs only the DB (foundational) and the existing github.py endpoint

### Within Each User Story

- Tests (T007–T009, T015–T016) MUST be written before verifying implementation
- Tests must fail on a clean codebase before implementation makes them pass
- Broadcaster tests before SSE stream tests (broadcaster is a dependency)

### Parallel Opportunities

- T007, T008, T009 can run in parallel (different test files/concerns)
- T015, T016 can run in parallel
- T011, T012 (frontend verification tasks) can run in parallel
- US2 (Phase 4) can start in parallel with US1 (Phase 3) once foundational phase is done
- US3 (Phase 5) can start in parallel with US1 and US2

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Tests — launch together:
Task: "Write broadcaster unit tests in tests/unit/api/test_broadcaster.py"  # T008
Task: "Write SSE stream unit tests in tests/unit/api/test_webhooks.py"      # T009

# Frontend verification — launch together:
Task: "Verify Live badge HTML/CSS in frontend/index.html"                    # T011
Task: "Verify initSSE() implementation in frontend/index.html"               # T012
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Foundational verification (CRITICAL — blocks all stories)
3. Write tests T007–T009, run them, confirm they pass
4. Verify US1 implementation T010–T014
5. **STOP and VALIDATE**: Run quickstart.md Scenario 1 and 6
6. Demo the live feed

### Incremental Delivery

1. Setup + Foundational → infrastructure verified
2. US1 tests + verification → live feed confirmed working (MVP!)
3. US2 tests + verification → webhook auth + persistence confirmed
4. US3 verification → historical feed confirmed
5. Polish → all scenarios pass, lint clean

---

## Notes

- [P] tasks = different files, no blocking dependencies between them
- [Story] label maps each task to its user story for traceability
- Constitution Principle III (Test-First) was violated during initial implementation — T007–T009 and T015–T016 are the remediation
- Implementation is largely complete; this task list focuses on test coverage and verification
- Commit after each logical group; reference this spec in PR description
