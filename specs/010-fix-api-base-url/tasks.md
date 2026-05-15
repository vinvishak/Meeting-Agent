# Tasks: Fix Dashboard API Base URL

**Input**: Design documents from `/specs/010-fix-api-base-url/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, quickstart.md ✓

**Organization**: Single user story — one-line fix in one file.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project structure needed — this fix touches one existing file.

- [X] T001 Verify `frontend/index.html` contains `const API_BASE = 'http://localhost:8000'` on line 613


---

## Phase 2: Foundational

**Purpose**: No shared infrastructure changes required — fix is self-contained.

**Checkpoint**: Setup confirmed — proceed directly to User Story 1.

---

## Phase 3: User Story 1 — Dashboard Works on Any Host (Priority: P1) 🎯 MVP

**Goal**: The dashboard loads data correctly when accessed on Railway or any remote host, without any hardcoded localhost references.

**Independent Test**: Open `https://meeting-agent-production-d7e6.up.railway.app/app` — overview and all tabs load data. Browser DevTools console shows no `ERR_CONNECTION_REFUSED` errors targeting localhost.

### Implementation for User Story 1

- [X] T002 [US1] Change `const API_BASE = 'http://localhost:8000'` to `const API_BASE = ''` in `frontend/index.html` line 613

**Checkpoint**: One line changed — run quickstart.md Scenario 1, 2, and 3 to verify.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T003 Run quickstart.md Scenario 1 — open Railway dashboard URL, confirm overview loads without error banner
- [ ] T004 Run quickstart.md Scenario 2 — open local dashboard, confirm no regression
- [ ] T005 Run quickstart.md Scenario 3 — open browser DevTools console on Railway URL, confirm no localhost fetch errors
- [ ] T006 Commit and push to `main` so Railway redeploys

---

## Dependencies & Execution Order

- **T001** → **T002** → **T003, T004, T005** (can run in parallel) → **T006**

### Parallel Opportunities

- T003, T004, T005 (quickstart scenarios) can all be verified in parallel — different browser tabs

---

## Implementation Strategy

### MVP (only one story)

1. Confirm T001 (find the line)
2. Apply T002 (change the line)
3. Validate T003–T005 (three scenarios)
4. Ship T006 (push to main)

---

## Notes

- Total tasks: 6
- Parallel opportunities: T003, T004, T005
- This is a one-line change — no new files, no new dependencies, no backend changes
- Constitution Principle III (Test-First) exempted — no JS test framework exists in this project (documented in plan.md)
