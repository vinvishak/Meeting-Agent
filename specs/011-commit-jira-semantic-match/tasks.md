# Tasks: GitHub Commit to Jira Semantic Matching

**Input**: Design documents from `/specs/011-commit-jira-semantic-match/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story. Tests written before implementation (Constitution Principle III).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the DB schema and repository layer — required by all user stories

- [ ] T001 Write Alembic migration `src/storage/migrations/versions/003_commit_suggestion_source.py` — ALTER `update_suggestions.transcript_mention_id` to nullable; ADD COLUMN `source_type` VARCHAR(20) NOT NULL DEFAULT 'transcript'; ADD COLUMN `commit_sha` VARCHAR(40) NULLABLE; ADD UNIQUE INDEX on `commit_sha` where not null
- [ ] T002 Update `UpdateSuggestion` model in `src/storage/models.py` — make `transcript_mention_id` optional (`Mapped[str | None]`), add `source_type: Mapped[str]` (default `'transcript'`), add `commit_sha: Mapped[str | None]`
- [ ] T003 Add `has_suggestion_for_commit(session, sha) -> bool` and `create_commit_suggestion(session, sha, ticket_id, confidence, confidence_tier) -> UpdateSuggestion` to `src/storage/repository.py`
- [ ] T004 Create `tests/unit/analysis/__init__.py` (empty) to make the package importable

**Checkpoint**: Migration, model, and repository layer ready — user story phases can proceed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new `commit_matcher.py` module is the shared core called by both integration points

- [ ] T005 Write unit tests for `src/analysis/commit_matcher.py` in `tests/unit/analysis/test_commit_matcher.py` — test: explicit Jira ID in message returns False without calling AI; duplicate SHA returns False; unresolved match (low confidence) returns False; ambiguous match (top two scores within 0.10) returns False; confident match above threshold creates suggestion and returns True; AI unavailable returns False without raising
- [ ] T006 Implement `src/analysis/commit_matcher.py` — public function `match_and_suggest_commit(session, sha, message, anthropic_client) -> bool` following the contract in `contracts/commit-matcher.md`: skip if explicit ID found, skip if duplicate, fetch active tickets, call `match_excerpt`, apply ambiguity check, create suggestion via repository, return True/False

**Checkpoint**: Run `pytest tests/unit/analysis/test_commit_matcher.py` — all tests must pass before proceeding

---

## Phase 3: User Story 1 — Automatic Ticket Matching from Commit Message (Priority: P1) 🎯 MVP

**Goal**: Every incoming commit without an explicit Jira ID is automatically evaluated and, if a confident match is found, a suggestion is queued.

**Independent Test**: Run quickstart.md Scenario 1 — push a commit whose message describes an open ticket without including the ticket ID; verify a suggestion appears in `/api/v1/suggestions`.

### Implementation for User Story 1

- [ ] T007 [US1] Wire `match_and_suggest_commit` into `_ingest_push()` in `src/api/routes/webhooks.py` — after each `upsert_commit` call, call `match_and_suggest_commit(session, sha=raw["id"], message=raw.get("message",""), anthropic_client=get_anthropic_client())`
- [ ] T008 [US1] Wire `match_and_suggest_commit` into `_sync_github()` in `src/workers/sync_worker.py` — after each `upsert_commit` call, call `match_and_suggest_commit` with the same session and commit data

**Checkpoint**: Run quickstart.md Scenario 1 and Scenario 3 — semantic match works, vague message produces no suggestion

---

## Phase 4: User Story 2 — Review and Approve Suggestions (Priority: P2)

**Goal**: Commit-sourced suggestions appear in the existing suggestion queue and can be approved or rejected through the existing endpoint.

**Independent Test**: Run quickstart.md Scenario 4 — approve a commit suggestion, verify Jira is updated.

### Implementation for User Story 2

- [ ] T009 [US2] Verify `GET /api/v1/suggestions` in `src/api/routes/suggestions.py` returns commit-sourced suggestions (those with `source_type='commit'`) — confirm the response includes `commit_sha` and `source_type` fields, add them to the response serialization if missing
- [ ] T010 [US2] Verify `POST /api/v1/suggestions/{id}/approve` and `POST /api/v1/suggestions/{id}/reject` work correctly for commit-sourced suggestions — the approval logic must not assume `transcript_mention_id` is present

**Checkpoint**: Run quickstart.md Scenario 4 (approve) and Scenario 4 rejection variant — Jira updated on approve, unchanged on reject

---

## Phase 5: User Story 3 — Low Confidence Commits Are Silently Skipped (Priority: P3)

**Goal**: Vague or ambiguous commit messages never produce suggestions, keeping the queue signal-to-noise ratio high.

**Independent Test**: Run quickstart.md Scenario 3 — push a commit with "minor fix", verify no suggestion is created.

### Implementation for User Story 3

- [ ] T011 [US3] Verify the ambiguity guard in `src/analysis/commit_matcher.py` — confirm that when top two similarity scores differ by ≤ 0.10, `match_and_suggest_commit` returns False (covered by unit tests in T005; this task verifies it end-to-end via quickstart Scenario 3)

**Checkpoint**: Run quickstart.md Scenarios 3 and 5 — no suggestion for vague message, no duplicate for repeated delivery

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T012 [P] Run `pytest tests/unit/analysis/` and confirm all tests pass
- [ ] T013 [P] Run quickstart.md Scenario 2 — explicit ticket ID in commit message skips AI and creates no suggestion
- [ ] T014 [P] Run quickstart.md Scenario 5 — duplicate commit delivery produces exactly one suggestion
- [ ] T015 Run `ruff check src/analysis/commit_matcher.py src/storage/models.py src/storage/repository.py src/api/routes/webhooks.py src/workers/sync_worker.py` and fix any lint errors
- [ ] T016 Commit all changes to branch `011-commit-jira-semantic-match`, push, open PR to `main`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T001–T004) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (T005–T006) — tests must pass first
- **US2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 once Phase 2 done
- **US3 (Phase 5)**: Covered by T005 unit tests — verify end-to-end after US1
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 all complete

### Within Each Phase

- T001 → T002 → T003 (sequential — each builds on the previous)
- T004 is independent [P] within Phase 1
- T005 must be written and fail before T006 is implemented (TDD)
- T007 and T008 can run in parallel [P] — different files

### Parallel Opportunities

- T004 can run alongside T001–T003
- T007 and T008 can run in parallel once T006 is complete
- T012, T013, T014 (quickstart scenarios) can run in parallel
- US2 (T009, T010) can run in parallel with US1 (T007, T008) once Phase 2 is done

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Once T006 is complete, launch both wiring tasks together:
Task: "Wire match_and_suggest_commit into _ingest_push() in src/api/routes/webhooks.py"   # T007
Task: "Wire match_and_suggest_commit into _sync_github() in src/workers/sync_worker.py"   # T008
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Schema + repository layer (T001–T004)
2. Complete Phase 2: Write tests (T005), implement module (T006) — tests must pass
3. Complete Phase 3: Wire into both ingestion paths (T007, T008)
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 — push a descriptive commit, see suggestion appear
5. Demo the suggestion queue

### Incremental Delivery

1. Setup + Foundational → DB schema extended, matcher module tested
2. US1 → semantic matching live in both webhook and sync paths
3. US2 → review queue fully functional for commit suggestions
4. US3 → confirmed via existing unit tests + quickstart
5. Polish → lint clean, all scenarios pass, PR opened

---

## Notes

- [P] tasks = different files, no blocking dependencies
- Constitution Principle III enforced: T005 (tests) written and run before T006 (implementation)
- `match_and_suggest_commit` is idempotent — safe to call on already-processed commits
- No Jira changes without explicit approval — the suggestion queue is always the gate
- Total tasks: 16
