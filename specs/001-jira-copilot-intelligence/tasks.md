# Tasks: Jira-Copilot Engineering Intelligence Agent

**Input**: Design documents from `/specs/001-jira-copilot-intelligence/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/rest-api.md ✓, quickstart.md ✓

**Tests**: Not included — not explicitly requested in spec.md. Test infrastructure (pytest config) is set up in Phase 1 for developers to add tests.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks in same phase)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure.

- [x] T001 Create all package directories with `__init__.py` files: `src/ingestion/`, `src/classification/`, `src/analysis/`, `src/velocity/`, `src/storage/migrations/`, `src/api/routes/`, `src/api/middleware/`, `src/workers/`, `tests/unit/`, `tests/integration/`, `tests/contract/`
- [x] T002 Create `pyproject.toml` declaring all dependencies: `anthropic`, `mcp`, `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `pydantic[email]`, `pydantic-settings`, `rapidfuzz`, `apscheduler`, `pytest`, `pytest-asyncio`
- [x] T003 [P] Add `[tool.ruff]` linting configuration to `pyproject.toml` (target Python 3.12, line-length 120)
- [x] T004 [P] Create `.env.example` with all required environment variables per `quickstart.md`: `JIRA_MCP_URL`, `JIRA_MCP_TOKEN`, `COPILOT_MCP_URL`, `COPILOT_MCP_TOKEN`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SYNC_INTERVAL_MINUTES`, `STALE_THRESHOLD_DAYS`, `HIGH_CONFIDENCE_THRESHOLD`, `AUTO_APPLY_ENABLED`
- [x] T005 [P] Add `[tool.pytest.ini_options]` to `pyproject.toml` with `asyncio_mode = "auto"` and testpaths pointing to `tests/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Storage, configuration, and API scaffolding that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Create all 9 SQLAlchemy ORM models in `src/storage/models.py`: `Engineer`, `Ticket`, `TicketSnapshot`, `Sprint`, `StatusMapping`, `Transcript`, `TranscriptMention`, `UpdateSuggestion`, `AuditEntry` — with all fields, types, constraints, relationships, and enums exactly as specified in `data-model.md`
- [x] T007 Initialize Alembic in `src/storage/migrations/` and generate the initial migration covering all 9 entity tables with indexes, unique constraints, and enum types from `data-model.md`
- [x] T008 Implement repository data-access layer in `src/storage/repository.py`: async SQLAlchemy session management; CRUD and query helpers for all 9 entities; no business logic
- [x] T009 [P] Implement app configuration in `src/config.py` using `pydantic-settings`: reads all env vars from `.env`; exposes singleton `Settings` instance consumed by all packages
- [x] T010 [P] Configure structured logging in `src/logging_config.py`: JSON format; log level from `LOG_LEVEL` env var; `get_logger(name)` helper used across all packages
- [x] T011 Create FastAPI application factory in `src/api/app.py`: lifespan handler, global exception handlers (404/422/500), router inclusion with `/api/v1` prefix for all route modules (`tickets`, `velocity`, `suggestions`, `reports`, `query`, `audit`, `sync`)
- [x] T012 [P] Implement auth middleware in `src/api/middleware/auth.py`: validates session token from `Authorization` header; attaches user identity and authorized Jira project list to `request.state`; returns `401` if token missing, `403` if project not authorized
- [x] T013 Create application entry point in `src/main.py`: starts FastAPI via `uvicorn` and APScheduler sync worker in a single process for dev mode; documents prod split-process invocation per `quickstart.md §6`

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — Real-Time Work Status View (Priority: P1) 🎯 MVP
/i
**Goal**: Engineering managers open the dashboard and immediately see which tickets are officially in progress, likely being worked on, blocked, stale, or completed-but-not-updated — with classification reasons citing the specific signals used.

**Independent Test**: Connect a Jira board via MCP → run `python -m src.workers.sync_worker --run-once` → call `GET /api/v1/tickets` → verify each ticket carries `inferred_status`, `inferred_status_reason`, and `inferred_status_signals` matching expected values for its Jira state and activity history. Delivers clear value without any Copilot or transcript data.

- [x] T014 [P] [US1] Implement Jira MCP client adapter in `src/ingestion/jira_client.py`: MCP tool calls for `list_issues`, `get_issue`, `list_sprints`, `get_comments`, `update_issue`; typed Pydantic return models; retry with exponential backoff on failure per `research.md §1`
- [x] T015 [P] [US1] Implement `StatusMapping` seed CLI in `src/storage/seed_status_mappings.py`: parses `--board-id` and `--mapping "raw=normalized"` args; writes `StatusMapping` records mapping raw Jira status names to `open/in_progress/review/done/blocked` per `data-model.md`
- [x] T016 [US1] Implement engineer normalizer in `src/ingestion/normalizer.py`: two-pass cross-system identity resolution — Pass 1: email exact match; Pass 2: `rapidfuzz` token sort ratio ≥ 90 on display name; creates/updates canonical `Engineer` records; `--resolve-engineers` CLI mode for initial setup; prints unresolved identities for manual mapping per `research.md §2`
- [x] T017 [US1] Implement signal extractor in `src/classification/signals.py`: extracts weighted signals per ticket — Jira status match (weight 3), transcript mention within 2 days (weight 2), Jira comment within 5 days (weight 1), status transition within 5 days (weight 1), blocker flag (override), no-activity threshold (`STALE_THRESHOLD_DAYS`, configurable); returns `SignalSet` Pydantic model per `research.md §4`
- [x] T018 [US1] Implement multi-signal classifier in `src/classification/classifier.py`: applies 6-rule classification logic from `research.md §4` (blocker override → done check → score≥4 → score 2–3 → stale → low-confidence); returns `inferred_status` enum + `inferred_status_reason` text citing specific signals for FR-007 transparency
- [x] T019 [US1] Implement sync worker core in `src/workers/sync_worker.py`: fetches Jira tickets and sprints via `jira_client`; normalizes engineers; applies `StatusMapping`; runs classifier; persists `Ticket`, `TicketSnapshot`, and `AuditEntry(event_type=status_inferred)` records; supports `--run-once` CLI flag; logs data freshness on completion
- [x] T020 [US1] Implement APScheduler job registration in `src/workers/scheduler.py`: `BlockingScheduler` with `SYNC_INTERVAL_MINUTES` interval; registers `sync_worker.run_sync_cycle` as recurring job; graceful shutdown on SIGTERM
- [x] T021 [US1] Implement `GET /api/v1/tickets` endpoint in `src/api/routes/tickets.py` per REST contract: paginated ticket list with all query params (team, sprint_id, assignee_id, project, priority, inferred_status, date_from, date_to); enforces auth middleware project scoping; includes `data_freshness` timestamp
- [x] T022 [US1] Implement `GET /api/v1/tickets/{jira_id}` endpoint in `src/api/routes/tickets.py` per REST contract: full ticket detail with `inferred_status_signals` breakdown; `404` if ticket not found or not in user's authorized projects
- [x] T023 [US1] Add `GET /api/v1/sync/status` endpoint in `src/api/routes/sync.py`: returns last sync timestamp, state (running/idle/failed), and most recent `AuditEntry(event_type=sync_completed|sync_failed)` per `quickstart.md` troubleshooting guide

**Checkpoint**: US1 fully functional — engineering managers can view classified ticket status via the API

---

## Phase 4: User Story 2 — Meeting Transcript Analysis and Jira Update Suggestions (Priority: P2)

**Goal**: Engineering leads review AI-generated Jira update suggestions derived from meeting transcripts and approve or reject each with one click. Conflicting statements require manual resolution. High-confidence suggestions can auto-apply when admin-enabled.

**Independent Test**: Provide a sample transcript with known ticket references → run transcript processing → call `GET /api/v1/suggestions` → verify suggestions contain correct `update_type`, `confidence_score`, `confidence_tier`, `excerpt`, `speaker`, `conflict_flag`, and `approval_state=pending` without touching US3–US5 features.

- [x] T024 [P] [US2] Implement Copilot MCP client adapter in `src/ingestion/copilot_client.py`: MCP tool calls for `list_meetings`, `get_transcript`, `get_meeting_summary`; typed Pydantic return models; retry with backoff; deduplication via `copilot_meeting_id`
- [x] T025 [US2] Implement two-stage entity matcher in `src/analysis/entity_matcher.py`: Stage 1 regex scan for `[A-Z]+-\d+` patterns (confidence=1.0, `match_type=exact_id`); Stage 2 Claude API embeddings cosine similarity against active ticket titles (threshold ≥ 0.75, confidence=similarity score, `match_type=semantic`); stores unresolved mentions with `match_type=unresolved` per `research.md §3`
- [x] T026 [US2] Implement transcript analyzer in `src/analysis/transcript_analyzer.py`: segments speaker-attributed transcript into candidate mentions; classifies each mention's `mention_intent` via Claude API (progress_update, blocker, completion, ownership_change, eta_change, dependency, future_intent, ambiguous); resolves speaker display name to `Engineer` via normalizer; returns list of `TranscriptMention` candidates
- [x] T027 [US2] Implement update suggester in `src/analysis/update_suggester.py`: converts `TranscriptMention` records into `UpdateSuggestion` records; derives `confidence_tier` (≥0.90→high, 0.70–0.89→medium, <0.70→low; low-tier not surfaced as actionable per `research.md §5`); detects conflicting statements from multiple speakers on the same ticket (sets `conflict_flag=true`, populates `conflict_details`); generates `proposed_value` per `update_type`
- [x] T028 [US2] Extend sync worker in `src/workers/sync_worker.py` to ingest Copilot transcripts after each Jira sync: fetch new transcripts via `copilot_client`; persist `Transcript` records; run entity matching → transcript analysis → update suggestion pipeline; write `AuditEntry(event_type=suggestion_created)` per suggestion
- [x] T029 [US2] Implement `GET /api/v1/suggestions` endpoint in `src/api/routes/suggestions.py` per REST contract: returns review queue with `approval_state` (default: pending), `confidence_tier`, `ticket_jira_id` filters; includes full source excerpt, speaker, meeting title, and `excerpt_timestamp_seconds`
- [x] T030 [US2] Implement `POST /api/v1/suggestions/{id}/approve` in `src/api/routes/suggestions.py`: validates `conflict_flag=false` (409 if conflicted); checks user Jira project authorization (403 if not authorized); calls `jira_client.update_issue`; sets `approval_state=approved`, `applied_at`; writes `AuditEntry(event_type=suggestion_approved)` with full `signal_inputs` (SC-006)
- [x] T031 [P] [US2] Implement `POST /api/v1/suggestions/{id}/reject` in `src/api/routes/suggestions.py`: records `approval_state=rejected`, optional `rejection_reason`, `reviewed_by_id`; writes `AuditEntry(event_type=suggestion_rejected)`; no Jira change made
- [x] T032 [US2] Implement auto-apply logic in `src/analysis/update_suggester.py`: when `AUTO_APPLY_ENABLED=true` and `confidence_tier=high` and `conflict_flag=false`, call `jira_client.update_issue` at suggestion creation time; set `approval_state=auto_applied`, `applied_at`; write `AuditEntry(event_type=suggestion_auto_applied)` with transcript excerpt and confidence score per SC-006

**Checkpoint**: US2 fully functional — transcript analysis populates review queue; approve/reject/auto-apply all work with complete audit trail

---

## Phase 5: User Story 3 — Velocity and Delivery Intelligence (Priority: P2)

**Goal**: Team leads see sprint velocity trends, completion forecasts, risk flags, per-engineer work distribution, and bottleneck tickets — all calculated from Jira historical data.

**Independent Test**: Load historical Jira sprint data → call `GET /api/v1/velocity?board_id=X` → verify velocity per sprint, trend direction, and `current_sprint_forecast` match expected calculations; call `GET /api/v1/bottlenecks?board_id=X` → verify stuck tickets have correct `days_in_status` and `overage_days`.

- [x] T033 [P] [US3] Implement velocity calculator in `src/velocity/calculator.py`: `velocity` (completed story points per sprint), `throughput_tickets`, `cycle_time_avg_days` (first transition → done), `lead_time_avg_days` (created → done), planned vs. completed delta; falls back to ticket count for teams without story points; flags sprints with unusually high velocity variance per spec edge cases
- [x] T034 [P] [US3] Implement sprint forecaster in `src/velocity/forecaster.py`: `current_sprint_forecast` using historical average velocity vs. current progress; risk flag based on configurable thresholds (e.g., <40% points completed with <40% days remaining → `at_risk`); bottleneck detection for tickets where `days_in_status > team_avg_days_in_status` per stage; velocity trend classification (improving/declining/stable)
- [x] T035 [US3] Implement `GET /api/v1/velocity` endpoint in `src/api/routes/velocity.py` per REST contract: `board_id` required, `sprint_count` default 6; returns sprint history array, `trend`, `average_velocity`, `current_sprint_forecast` with `forecast_reason`
- [x] T036 [US3] Implement `GET /api/v1/bottlenecks` endpoint in `src/api/routes/velocity.py` per REST contract: `board_id` required; returns tickets with `stuck_in_status`, `days_in_status`, `team_avg_days_in_status`, `overage_days`
- [x] T037 [US3] Extend sync worker in `src/workers/sync_worker.py` to trigger velocity recalculation after each Jira sync: call `calculator.compute_sprint_metrics` and `forecaster.update_forecast` for all active boards; persist updated `Sprint.velocity` and `Sprint.completed_points`

**Checkpoint**: US3 fully functional — velocity, forecast, and bottleneck views all return correct data

---

## Phase 6: User Story 4 — Executive Summary and Portfolio Reporting (Priority: P3)

**Goal**: Executives see aggregated sprint health across all teams and initiative-level risk indicators without digging into individual tickets.

**Independent Test**: Configure 2+ Jira projects → call `GET /api/v1/reports/sprint-health` → verify per-team health indicators (`on_track/at_risk/off_track`) and blocker counts are correct; call `GET /api/v1/reports/executive-summary` → verify initiative rollups show correct completion percentages and risk flags.

- [x] T038 [P] [US4] Implement sprint health aggregator in `src/velocity/aggregator.py`: computes per-team `health` (on_track/at_risk/off_track), `active_blockers` count, `completion_pct`, sprint `forecast`; derives `overall_velocity_trend` across all boards visible to the requesting user
- [x] T039 [P] [US4] Implement initiative aggregator in `src/velocity/aggregator.py`: groups tickets by initiative label across Jira projects; computes `completion_pct`, `blocked_tickets`, `estimated_completion_date`, and `at_risk` flag per initiative
- [x] T040 [US4] Implement `GET /api/v1/reports/sprint-health` endpoint in `src/api/routes/reports.py` per REST contract: aggregates all boards visible to user; returns `teams` array with health, active_blockers, forecast, completion_pct; includes `generated_at` timestamp
- [x] T041 [US4] Implement `GET /api/v1/reports/executive-summary` endpoint in `src/api/routes/reports.py` per REST contract: returns teams summary array + `initiatives` array with completion_pct, blocked_tickets, estimated_completion_date, at_risk; includes `overall_velocity_trend`

**Checkpoint**: US4 fully functional — executive summary and portfolio views aggregate cross-team data correctly

---

## Phase 7: User Story 5 — Natural Language Work Queries (Priority: P3)

**Goal**: Managers ask plain-language questions and receive accurate answers with supporting ticket data — no query syntax needed.

**Independent Test**: Run 3 predefined questions ("What is the team working on right now?", "Which engineers may be overloaded?", "Which tickets were discussed in meetings but not updated in Jira?") against a known dataset → verify answers are accurate and `supporting_data` contains correct ticket lists.

- [x] T042 [P] [US5] Define 6 read-only Claude tool schemas in `src/analysis/query_tools.py` as Pydantic models: `get_active_tickets(filters)`, `get_blocked_tickets()`, `get_velocity(team, sprint_range)`, `get_sprint_risk()`, `get_overloaded_engineers()`, `get_transcript_jira_gaps()` — each maps to a repository query per `research.md §7`; tool implementations call `src/storage/repository.py`
- [x] T043 [US5] Implement NL query handler in `src/analysis/query_handler.py`: injects filtered data context into Claude tool-use prompt (`claude-sonnet-4-6`); executes Claude API tool-use loop; assembles plain-language `answer` + `supporting_data` from tool call results; enforces user's authorized project scope for all tool calls
- [x] T044 [US5] Implement `POST /api/v1/query` endpoint in `src/api/routes/query.py` per REST contract: validates question (non-empty, ≤500 chars); passes `board_id` context to query handler; returns `answer`, `supporting_data`, `data_freshness`; `400` on validation failure; `422` if question cannot be answered from available authorized data

**Checkpoint**: US5 fully functional — natural language queries return accurate plain-language answers with supporting data

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Audit trail access, data retention, reliability hardening, and end-to-end validation.

- [x] T045 [P] Implement `GET /api/v1/audit` endpoint in `src/api/routes/audit.py` per REST contract: admin-only access enforcement; supports `ticket_jira_id`, `event_type`, `from`, `to`, `limit` (default 50, max 200) query params; returns `AuditEntry` records with full `reasoning` and `signal_inputs`
- [x] T046 [P] Implement 12-month rolling retention purge job in `src/workers/maintenance_worker.py`: deletes `TicketSnapshot` and `Transcript` records with `snapshot_at`/`last_synced_at` older than 12 months; registers as nightly APScheduler job in `src/workers/scheduler.py`; `AuditEntry` records are never purged per `data-model.md`
- [x] T047 [P] Verify `data_freshness` field is present and populated on all relevant API responses (`GET /tickets`, `GET /tickets/{id}`, `GET /velocity`, `GET /reports/*`, `POST /query`) using the most recent `AuditEntry(event_type=sync_completed)` timestamp; fix any endpoint missing this field
- [x] T048 Harden MCP client retry in both `src/ingestion/jira_client.py` and `src/ingestion/copilot_client.py`: exponential backoff with jitter; write `AuditEntry(event_type=sync_failed)` on exhausted retries; update `GET /api/v1/sync/status` response with failure details and stale data indicator (FR-005)
- [x] T049 Validate end-to-end setup per `quickstart.md`: `pip install -r requirements.txt` → `alembic upgrade head` → `seed_status_mappings` → `normalizer --resolve-engineers` → `sync_worker --run-once` → `GET /api/v1/tickets` returns populated classified ticket data; fix any integration issues found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — independent of US2–US5; delivers MVP alone
- **US2 (Phase 4)**: Depends on Phase 2 + US1 (transcript analysis needs Jira ticket records for entity matching)
- **US3 (Phase 5)**: Depends on Phase 2 + US1 (velocity needs sprint and ticket data from US1 sync)
- **US4 (Phase 6)**: Depends on US1 + US3 (aggregates sprint health from US3 metrics)
- **US5 (Phase 7)**: Depends on Phase 2 + US1 (needs ticket data; answers are richer with US2/US3 data but independently testable)
- **Polish (Phase 8)**: Depends on all desired stories complete

### User Story Dependencies

- **US1 (P1)**: First — foundational Jira sync and classification pipeline; MVP baseline
- **US2 (P2)**: After US1 — transcript pipeline needs Jira `Ticket` records for entity matching
- **US3 (P2)**: After US1 — velocity calculations need `Sprint` and `TicketSnapshot` data
- **US4 (P3)**: After US1 + US3 — executive reports aggregate sprint health from US3 metrics
- **US5 (P3)**: After US1 — NL query tools read ticket/sprint data; enriched but not blocked by US2/US3

### Within Each User Story

- MCP client adapters before sync worker extension
- Signal extraction before classification
- Classification before API endpoint exposure
- Repository helpers before route implementations
- Sync worker extension before verifying data via API

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 run in parallel after T002
- **Phase 2**: T009, T010, T012 run in parallel; T011 and T013 after T008/T009
- **Phase 3**: T014 and T015 run in parallel; T017→T018→T019 are sequential; T021, T022, T023 run in parallel after T019
- **Phase 4**: T024 runs in parallel with the T025–T028 sequential pipeline; T030 and T031 run in parallel after T029
- **Phase 5**: T033 and T034 run in parallel; T035 and T036 run in parallel after T033/T034
- **Phase 6**: T038 and T039 run in parallel; T040 and T041 run in parallel after T038/T039
- **Phase 7**: T042 and T043 start in parallel; T044 depends on T043
- **Phase 8**: T045, T046, T047 run in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2 checkpoint (T013 complete):

# Launch in parallel:
Task T014: "Implement Jira MCP client adapter in src/ingestion/jira_client.py"
Task T015: "Implement StatusMapping seed CLI in src/storage/seed_status_mappings.py"

# Then sequential pipeline:
Task T016: "Implement engineer normalizer in src/ingestion/normalizer.py"  # needs T014
Task T017: "Implement signal extractor in src/classification/signals.py"   # needs T016
Task T018: "Implement multi-signal classifier in src/classification/classifier.py"  # needs T017
Task T019: "Implement sync worker core in src/workers/sync_worker.py"      # needs T018
Task T020: "Implement APScheduler scheduler in src/workers/scheduler.py"   # needs T019

# After T019/T020, launch API endpoints in parallel:
Task T021: "Implement GET /api/v1/tickets in src/api/routes/tickets.py"
Task T022: "Implement GET /api/v1/tickets/{jira_id} in src/api/routes/tickets.py"
Task T023: "Add GET /api/v1/sync/status in src/api/routes/sync.py"
```

---

## Parallel Example: User Story 2

```bash
# After US1 baseline is functional:

# Can start in parallel with the analysis pipeline:
Task T024: "Implement Copilot MCP client adapter in src/ingestion/copilot_client.py"

# Sequential pipeline:
Task T025: "Implement two-stage entity matcher in src/analysis/entity_matcher.py"
Task T026: "Implement transcript analyzer in src/analysis/transcript_analyzer.py"
Task T027: "Implement update suggester in src/analysis/update_suggester.py"
Task T028: "Extend sync worker in src/workers/sync_worker.py for Copilot ingestion"

# After T028, launch in parallel:
Task T029: "Implement GET /api/v1/suggestions in src/api/routes/suggestions.py"
Task T030: "Implement POST /suggestions/{id}/approve in src/api/routes/suggestions.py"
Task T031: "Implement POST /suggestions/{id}/reject in src/api/routes/suggestions.py"

# After T027:
Task T032: "Implement auto-apply logic in src/analysis/update_suggester.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T013) — **CRITICAL**: blocks all stories
3. Complete Phase 3: User Story 1 (T014–T023)
4. **STOP and VALIDATE**: `sync_worker --run-once` → `GET /api/v1/tickets` → confirm classified ticket data with reasons
5. Demo to engineering managers — US1 delivers full standalone value

### Incremental Delivery

1. **Foundation** → **US1** (Jira sync + ticket status) → **MVP demo**
2. + **US2** (transcript analysis + suggestions) → **Sprint review demo**
3. + **US3** (velocity + forecasts + bottlenecks) → **Sprint health demo**
4. + **US4** (executive reports) → **Leadership demo**
5. + **US5** (NL queries) → **Full product launch**

### Parallel Team Strategy

With multiple developers (after Phase 2 complete):
- **Developer A**: US1 — Jira sync pipeline + classification + tickets API
- **Developer B**: US2 — Copilot sync + transcript analysis + suggestions API
- **Developer C**: US3 — Velocity calculator + forecaster + velocity API

All three stories independently testable and mergeable.

---

## Notes

- [P] tasks target different files with no unresolved dependencies within their phase
- [Story] label maps each task to a user story for traceability and scoping
- Every applied Jira update (T030, T032) must write an `AuditEntry` — this is SC-006 and non-negotiable
- `conflict_flag=true` on an `UpdateSuggestion` blocks `auto_applied` state in all code paths (T027, T030, T032)
- Each user story phase is independently completable, testable, and deliverable as an increment
- Commit after each task or logical group; stop at any checkpoint to validate the story before proceeding
