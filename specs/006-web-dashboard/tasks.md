# Tasks: Engineering Intelligence Web Dashboard

**Input**: Design documents from `/specs/006-web-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-sections.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- All paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Create the project structure and wire the frontend into FastAPI.

- [X] T001 Create `frontend/` directory and empty `frontend/index.html`
- [X] T002 Mount `frontend/` as a StaticFiles directory in `src/api/app.py` at path `/app` using `from starlette.staticfiles import StaticFiles` and `app.mount("/app", StaticFiles(directory="frontend"), name="frontend")`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared HTML shell, CSS design system, and JS `api()` helper that all five sections depend on.

**⚠️ CRITICAL**: No user story section can be built until this phase is complete.

- [X] T003 Write the HTML skeleton in `frontend/index.html`: `<!DOCTYPE html>` with `<head>` (charset, viewport, title "Meeting Agent"), and a `<body>` containing a `<header>` with the app title, a `<nav>` with five tab buttons (Tickets, Sprint Health, Org Metrics, Suggestions, Query), and five `<section>` elements with ids `section-tickets`, `section-sprint`, `section-org`, `section-suggestions`, `section-query` — only one visible at a time
- [X] T004 Write the CSS in a `<style>` block in `frontend/index.html`: CSS custom properties for colours (`--blue`, `--orange`, `--red`, `--green`, `--grey`, `--bg`, `--surface`, `--text`); reset styles; header bar; nav tab styling (active tab highlighted); section layout using CSS Grid; status badge pill styles for each inferred status (`likely_in_progress` → blue, `stale` → orange, `blocked` → red, `done` → green, `open` → grey); metric card styles; table styles; button styles (primary, danger, disabled state); loading and error message styles
- [X] T005 Write the JavaScript foundation in a `<script>` block in `frontend/index.html`: (a) `const API_BASE = 'http://localhost:8000'` and `const TOKEN = 'dev'`; (b) `async function api(path, options={})` that calls `fetch(API_BASE + path, { headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' }, ...options })`, throws on non-2xx, and returns parsed JSON; (c) `function badge(status)` that returns an HTML string `<span class="badge badge-{status}">{label}</span>` mapping each inferred_status value to a human-readable label; (d) `function relativeTime(isoString)` that returns a string like "3 days ago"; (e) tab navigation logic that shows the active section and hides the others when a nav button is clicked; (f) a `loadAll()` function that calls all five section loaders on page load

**Checkpoint**: Opening `http://localhost:8000/app/index.html` shows the app shell with nav tabs switching between empty sections.

---

## Phase 3: User Story 1 — Ticket Status Overview (Priority: P1) 🎯 MVP

**Goal**: All synced Jira tickets are displayed in a table with status badges, priority, assignee, and last updated. A filter dropdown reduces the visible set by inferred status.

**Independent Test**: Open the dashboard, verify all SCRUM tickets appear in the table with colour-coded status badges. Select "Stale" from the filter and verify only stale tickets remain visible.

- [X] T006 [US1] Implement `loadTickets()` in `frontend/index.html`: fetch `GET /api/v1/tickets`; on loading show `<p class="loading">Loading tickets...</p>` in `#section-tickets`; on success render a `<div class="toolbar">` containing a `<select id="status-filter">` with options All/In Progress/Stale/Blocked/Done, followed by a `<table>` with `<thead>` columns Ticket, Title, Status, Priority, Assignee, Last Updated and a `<tbody id="tickets-body">`; call `renderTickets(tickets, filter)` to populate the tbody; on error show `<p class="error">Could not load tickets. <button onclick="loadTickets()">Retry</button></p>`
- [X] T007 [US1] Implement `renderTickets(tickets, filter)` in `frontend/index.html`: filter the tickets array by `inferred_status` when filter is not "all"; for each ticket render a `<tr>` with: `<td><a href="https://vinv8290.atlassian.net/browse/{jira_id}" target="_blank">{jira_id}</a></td>`, `<td>{title}</td>`, `<td>{badge(inferred_status)}</td>`, `<td>{priority ?? '—'}</td>`, `<td>{assignee ?? 'Unassigned'}</td>`, `<td>{relativeTime(updated_at)}</td>`; if filtered list is empty show a single row with "No tickets found" spanning all columns
- [X] T008 [US1] Wire the status filter `<select>` change event in `frontend/index.html` to call `renderTickets(cachedTickets, selectedValue)` without re-fetching from the API; store the fetched tickets in a module-level `let cachedTickets = []`

**Checkpoint**: Tickets table loads with real SCRUM data. Filter dropdown works client-side with no additional API calls.

---

## Phase 4: User Story 2 — Sprint Health View (Priority: P1)

**Goal**: A summary of ticket counts per status category gives an instant sprint health reading.

**Independent Test**: Open Sprint Health tab and verify the counts for Done, In Progress, Stale, and Blocked match the totals visible in the Tickets tab.

- [X] T009 [US2] Implement `loadSprintHealth()` in `frontend/index.html`: fetch `GET /api/v1/reports/sprint-health`; on loading show `<p class="loading">Loading sprint health...</p>` in `#section-sprint`; on success render a `<h2>{sprint_name ?? 'Current Sprint'}</h2>`, a `<div class="metrics-grid">` containing four `<div class="metric-card">` elements for Done (green), In Progress (blue), Stale (orange), Blocked (red) — each showing the count and label — and a progress bar `<div class="progress-bar"><div class="progress-fill" style="width:{completion_rate*100}%"></div></div>` with a label "{n}% complete"; on error show `<p class="error">Could not load sprint health.</p>`

**Checkpoint**: Sprint Health tab shows four metric cards with correct counts and a progress bar.

---

## Phase 5: User Story 3 — Org Performance Summary (Priority: P2)

**Goal**: Three headline metrics (total tickets, stale, blocked) plus a velocity trend indicator give an executive-level snapshot.

**Independent Test**: Open Org Metrics tab and verify the total ticket count matches the count visible in the Tickets tab. Velocity shows "Not enough data yet" or a trend indicator.

- [X] T010 [US3] Implement `loadOrgMetrics()` in `frontend/index.html`: fetch `GET /api/v1/reports/executive-summary`; on loading show `<p class="loading">Loading org metrics...</p>` in `#section-org`; on success render a `<div class="metrics-grid">` with three metric cards — Total Tickets (grey), Stale (orange), Blocked (red) — and a velocity section `<div class="velocity">` showing a trend arrow (↑ improving, → stable, ↓ declining) and label, or "Not enough data yet" if `velocity.trend` is null; on error show `<p class="error">Could not load org metrics.</p>`

**Checkpoint**: Org Metrics tab shows three cards with real counts and a velocity indicator.

---

## Phase 6: User Story 4 — AI Suggestion Review (Priority: P2)

**Goal**: Pending AI suggestions are displayed as cards; approve/reject with one click removes the card.

**Independent Test**: If suggestions exist, click Approve on one and verify the card disappears and the remaining count decreases. If no suggestions exist, verify the empty state message is shown.

- [X] T011 [US4] Implement `loadSuggestions()` in `frontend/index.html`: fetch `GET /api/v1/suggestions`; filter to only `approval_state === 'pending'`; on loading show `<p class="loading">Loading suggestions...</p>` in `#section-suggestions`; on success render a `<div id="suggestions-list">` containing one `<div class="suggestion-card" data-id="{id}">` per pending suggestion showing: ticket ID as a link, update type label, proposed value, reasoning text, confidence percentage, and two buttons `<button class="btn-approve" onclick="approveSuggestion('{id}')">Approve</button>` and `<button class="btn-reject" onclick="rejectSuggestion('{id}')">Reject</button>`; if no pending suggestions show `<p class="empty">No pending suggestions.</p>`; on error show `<p class="error">Could not load suggestions.</p>`
- [X] T012 [US4] Implement `approveSuggestion(id)` and `rejectSuggestion(id)` in `frontend/index.html`: disable both buttons on the card while the request is in flight; call `api('/api/v1/suggestions/{id}/approve', {method:'POST'})` or `reject` respectively; on success remove the card from the DOM; if the list is now empty replace `#suggestions-list` content with the empty state message; on error re-enable the buttons and show an inline `<span class="error">Failed. Try again.</span>` on the card

**Checkpoint**: Suggestions section shows pending suggestions (or empty state). Clicking Approve/Reject removes the card without page reload.

---

## Phase 7: User Story 5 — Natural Language Query (Priority: P3)

**Goal**: A text input lets the user ask plain-English questions about their tickets and see Claude's response.

**Independent Test**: Type "which tickets are at risk?" and press Ask. Verify a loading indicator appears and a text response is rendered below the input within 10 seconds.

- [X] T013 [US5] Implement the query section UI in `frontend/index.html` inside `#section-query`: render a `<div class="query-container">` with `<textarea id="query-input" placeholder="Ask a question about your tickets..." rows="3"></textarea>`, a `<button id="query-btn" onclick="submitQuery()">Ask</button>`, and a `<div id="query-response"></div>`; pressing Enter in the textarea (without Shift) should also trigger `submitQuery()`
- [X] T014 [US5] Implement `submitQuery()` in `frontend/index.html`: read the trimmed value of `#query-input`; if empty set `#query-response` to `<p class="error">Please enter a question.</p>` and return; disable `#query-btn` and set its text to "Thinking..."; set `#query-response` to `<p class="loading">Thinking...</p>`; call `api('/api/v1/query', {method:'POST', body: JSON.stringify({query: text})})`; on success set `#query-response` to `<div class="response-text">{response}</div>`; on error set `#query-response` to `<p class="error">Could not get a response. Please try again.</p>`; re-enable `#query-btn` and reset its text to "Ask"

**Checkpoint**: Query box submits, shows loading state, and displays Claude's response or a clear error.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, visual polish, and validation.

- [X] T015 Call `loadAll()` on `DOMContentLoaded` in `frontend/index.html` to trigger all five section loaders; ensure the Tickets tab is active by default on load
- [X] T016 [P] Add a `<meta name="color-scheme" content="light">` and a favicon `<link>` pointing to a simple emoji favicon (`data:image/svg+xml,...` inline SVG with a chart emoji) in the `<head>` of `frontend/index.html`
- [X] T017 [P] Add responsive table behaviour in the CSS: `overflow-x: auto` on a wrapper div around each table so wide tables scroll horizontally on smaller screens rather than breaking the layout
- [X] T018 Manually verify in browser: (a) all five tabs load without console errors, (b) SCRUM tickets appear with correct badge colours, (c) status filter works client-side, (d) sprint health counts are non-zero, (e) org metrics cards show correct totals, (f) suggestions shows empty state, (g) query returns a response for "which tickets are stale?"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1
- **US1–US5 (Phases 3–7)**: All depend on Phase 2 (shared shell + api() helper)
- **US3, US4, US5 can run in parallel** after Phase 2 if desired
- **Polish (Phase 8)**: Depends on all stories complete

### Parallel Opportunities

```
# After Phase 2 completes, these can run in parallel:
T009  (Sprint Health)
T010  (Org Metrics)
T011+T012  (Suggestions)
T013+T014  (Query)

# Within Phase 2, these are sequential (same file, building on each other):
T003 → T004 → T005
```

---

## Implementation Strategy

### MVP (US1 + US2 only — ~1 hour)

1. Phase 1: Setup (T001, T002)
2. Phase 2: Foundation (T003, T004, T005)
3. Phase 3: Tickets (T006, T007, T008)
4. Phase 4: Sprint Health (T009)
5. **STOP and validate**: Open browser, verify tickets and sprint health work
6. Continue to remaining stories

### Full Delivery

Complete all phases in order. Each phase checkpoint is a working, demonstrable increment.

---

## Notes

- All tasks modify a single file: `frontend/index.html` (except T001 creating it and T002 modifying `src/api/app.py`)
- Because most tasks touch the same file, only T001/T002, T016, and T017 are marked `[P]` — the rest must run sequentially
- `cachedTickets` is the only client-side state; no localStorage or sessionStorage used
- The `api()` helper is the single point for auth and error handling — do not inline `fetch()` calls in section functions
