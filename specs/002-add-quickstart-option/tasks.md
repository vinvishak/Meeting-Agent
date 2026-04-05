# Tasks: Add Quickstart Option

**Input**: Design documents from `/specs/002-add-quickstart-option/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/cli.md ✓, quickstart.md ✓

**Tests**: Included — Constitution Principle III mandates test-first for all implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `src/quickstart/` package skeleton and test directory so all subsequent tasks have a place to write to.

- [x] T001 Create `src/quickstart/` package with empty stub files: `__init__.py`, `config_schema.py`, `prompts.py`, `env_writer.py`, `connectivity.py`, `db_migrator.py`
- [x] T002 Create `tests/unit/quickstart/__init__.py` to establish the test package

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data structures and the argparse entry-point skeleton that all three user stories build on. No user story can be completed until T005–T007 pass.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Write failing unit tests for `ConfigField` dataclass and canonical field list in `tests/unit/quickstart/test_config_schema.py` (verify field attributes: key, description, example, default, secret, required, validator)
- [x] T004 [P] Write failing unit tests for `.env` file reader in `tests/unit/quickstart/test_env_writer.py` (verify: parse existing `.env`, detect missing keys vs `.env.example`, return dict of current values)
- [x] T005 Implement `ConfigField` dataclass and `QUICKSTART_FIELDS: list[ConfigField]` (one entry per variable in `.env.example`) in `src/quickstart/config_schema.py` — make T003 tests pass
- [x] T006 Implement `.env` file reader (parse existing `.env` line-by-line, compare against `.env.example` keys, return `dict[str, str]`) in `src/quickstart/env_writer.py` — make T004 tests pass
- [x] T007 Implement argparse entry point with mode routing in `src/quickstart/__init__.py`: parse `--non-interactive`, `--check`, `--force`, and all value flags from `contracts/cli.md`; route to `interactive_flow()`, `noninteractive_flow()`, or `check_flow()` stubs that raise `NotImplementedError`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — First-Time Interactive Setup (Priority: P1) 🎯 MVP

**Goal**: A new user runs `python -m src.quickstart`, is prompted for each credential, sees a masked summary, confirms, gets connectivity check results, has `.env` written, and has the database migrated — all in one command.

**Independent Test**: `rm -f .env && python -m src.quickstart` on a clean environment completes and the agent starts with `python -m src.main`.

### Tests for User Story 1 ⚠️ Write these FIRST — ensure they FAIL before implementing

- [x] T008 [P] [US1] Write failing unit tests for prompt helpers in `tests/unit/quickstart/test_prompts.py` (verify: `prompt_field()` returns value, `prompt_secret()` uses getpass, `mask_secret()` returns `****<last4>`, existing-value detection branches)
- [x] T009 [P] [US1] Write failing unit tests for `.env` write and merge in `tests/unit/quickstart/test_env_writer.py` (verify: write new file, overwrite existing, merge preserving unrelated keys, summary output with secrets masked)
- [x] T010 [P] [US1] Write failing unit tests for connectivity probes in `tests/unit/quickstart/test_connectivity.py` (verify: `ConnectionCheckResult` fields, httpx probe returns ok=True/False, anthropic key probe mock, db probe)
- [x] T011 [P] [US1] Write failing unit tests for DB migrator in `tests/unit/quickstart/test_db_migrator.py` (verify: calls `alembic.command.upgrade(cfg, "head")`, handles `CommandError`, idempotent on already-migrated DB)

### Implementation for User Story 1

- [x] T012 [P] [US1] Implement prompt helpers in `src/quickstart/prompts.py`: `prompt_field(field, existing)` using `input()`, `prompt_secret(field, existing)` using `getpass.getpass()`, `mask_secret(value)` returning `****<last4>` — make T008 tests pass
- [x] T013 [P] [US1] Implement `.env` write and merge logic in `src/quickstart/env_writer.py`: `write_env(values, force)` writes all fields, `merge_env(existing, new_values)` preserves unrelated keys, `print_summary(fields, values)` prints masked table — make T009 tests pass
- [x] T014 [P] [US1] Implement connectivity probes in `src/quickstart/connectivity.py`: `check_mcp(name, url, token)` via `httpx.get` with 5s timeout, `check_anthropic(api_key)` via `anthropic.Anthropic().models.list()`, `check_db(database_url)` via alembic config inspect, each returning `ConnectionCheckResult` — make T010 tests pass
- [x] T015 [US1] Implement Alembic migration runner in `src/quickstart/db_migrator.py`: `run_migrations(database_url)` builds `alembic.config.Config("alembic.ini")`, sets `sqlalchemy.url`, calls `alembic.command.upgrade(cfg, "head")`, raises `RuntimeError` on failure — make T011 tests pass
- [x] T016 [US1] Wire complete interactive flow into `interactive_flow(args, fields)` in `src/quickstart/__init__.py`: detect existing `.env` → prompt each field (reuse existing values as defaults) → print masked summary → confirm → write `.env` → run connectivity checks and print pass/fail report → run migrations → print success message with `python -m src.main`

**Checkpoint**: `python -m src.quickstart` (interactive) fully functional and independently testable.

---

## Phase 4: User Story 2 — Non-Interactive Mode (Priority: P2)

**Goal**: `python -m src.quickstart --non-interactive --jira-mcp-url ... [all required flags]` exits 0 on success and 1 with a missing-flags list when any required flag is absent.

**Independent Test**: Run with all required flags in a script; verify exit code 0 and `.env` written. Run with a missing flag; verify exit code 1 and error message.

### Tests for User Story 2 ⚠️ Write these FIRST

- [x] T017 [P] [US2] Write failing unit tests for non-interactive mode in `tests/unit/quickstart/test_non_interactive.py` (verify: all required flags present → returns values dict; any required flag missing → prints missing list and raises `SystemExit(1)`; optional flags use defaults when absent)

### Implementation for User Story 2

- [x] T018 [US2] Implement `noninteractive_flow(args, fields)` in `src/quickstart/__init__.py`: collect values from parsed argparse namespace, validate all `required=True` fields have non-empty values, `sys.exit(1)` with missing-flag list if validation fails, otherwise reuse interactive flow's write/check/migrate logic — make T017 tests pass

**Checkpoint**: Non-interactive mode fully functional; interactive mode unchanged.

---

## Phase 5: User Story 3 — Health Check Mode (Priority: P3)

**Goal**: `python -m src.quickstart --check` reads existing `.env`, probes all services, prints a per-service pass/fail report, and exits without writing any files or running migrations.

**Independent Test**: Run `python -m src.quickstart --check` against an existing `.env`; verify report prints and no files are modified.

### Tests for User Story 3 ⚠️ Write these FIRST

- [x] T019 [P] [US3] Write failing unit tests for health check mode in `tests/unit/quickstart/test_health_check.py` (verify: reads `.env`, calls each connectivity probe, prints pass/fail per service, no `.env` write, no migration call, exit 0 when all pass, exit 1 when any fail)

### Implementation for User Story 3

- [x] T020 [US3] Implement `check_flow(args, fields)` in `src/quickstart/__init__.py`: load values from existing `.env` (error and exit 1 if missing), run all `connectivity.py` probes, print formatted pass/fail report from `contracts/cli.md`, exit 0 if all pass / exit 1 if any fail — make T019 tests pass

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and documentation update.

- [x] T021 Run all 6 test scenarios from `specs/002-add-quickstart-option/quickstart.md` manually and verify each passes (clean setup, existing .env, missing flag, health check, partial .env, idempotency)
- [x] T022 [P] Update `specs/001-jira-copilot-intelligence/quickstart.md` §2 "Configure Environment" to reference `python -m src.quickstart` as the preferred setup method

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 — no dependency on US1 (reuses helpers but doesn't require US1 to be complete)
- **US3 (Phase 5)**: Depends on Phase 2 and `connectivity.py` from US1 (T014) — must wait for T014
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2. No dependency on US2/US3.
- **US2 (P2)**: Starts after Phase 2. Shares `env_writer.py` and `connectivity.py` from US1 but does not require US1's interactive flow to be complete.
- **US3 (P3)**: Starts after T014 (`connectivity.py`) is complete.

### Within Each Phase

- Test tasks (T008–T011, T017, T019) MUST be written and **failing** before their implementation counterparts
- T012–T014 are parallel (different files); T015 and T016 are sequential (T016 depends on T012–T015)
- T018 depends on T016 (reuses interactive flow logic)
- T020 depends on T014 (reuses connectivity probes)

---

## Parallel Opportunities

### Phase 2 (Foundational)

```
T003 [test_config_schema.py]   ─┐
T004 [test_env_writer.py]      ─┤ run in parallel
                                ↓
T005 [config_schema.py]        ─┐
T006 [env_writer.py]           ─┤ run in parallel (after T003/T004)
                                ↓
T007 [__init__.py skeleton]
```

### Phase 3 (US1)

```
T008 [test_prompts.py]       ─┐
T009 [test_env_writer.py]    ─┤ run in parallel (write tests first)
T010 [test_connectivity.py]  ─┤
T011 [test_db_migrator.py]   ─┘
           ↓
T012 [prompts.py]            ─┐
T013 [env_writer.py write]   ─┤ run in parallel (after tests fail)
T014 [connectivity.py]       ─┘
           ↓
T015 [db_migrator.py]
           ↓
T016 [__init__.py interactive flow]
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (T008 → T016)
4. **STOP and VALIDATE**: Run `rm -f .env && python -m src.quickstart` end-to-end
5. Interactive setup is fully usable — ship as MVP

### Incremental Delivery

1. Setup + Foundational → skeleton in place
2. User Story 1 → interactive quickstart working (MVP)
3. User Story 2 → adds CI/scripted mode
4. User Story 3 → adds ongoing health-check utility
5. Polish → docs updated, all scenarios verified

---

## Notes

- [P] tasks touch different files — safe to parallelize
- Constitution Principle III: every test task MUST fail before its implementation task is started
- `connectivity.py` probes use injected values (not `get_settings()`) so they are testable without a real `.env`
- The `--force` flag (bypasses confirmation in interactive mode) is wired in T007 and respected in T013
- Secret masking (`****<last4>`) is implemented in T012 and reused in T013 (summary) and T020 (health check display)
