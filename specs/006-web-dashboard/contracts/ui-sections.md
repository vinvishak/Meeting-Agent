# Contract: Dashboard UI Sections

**Branch**: `006-web-dashboard` | **Date**: 2026-04-28

Each section of the dashboard must meet these behavioural contracts regardless of implementation.

---

## All Sections (shared contract)

- MUST show a loading spinner/indicator while data is being fetched
- MUST show a user-friendly error message if the fetch fails (not a raw error object)
- MUST be independently refreshable without reloading the page
- MUST NOT block other sections from loading if they fail

---

## Section 1: Tickets View

**Trigger**: Loads on page open; reloads when status filter changes

| State | Required behaviour |
|-------|--------------------|
| Loading | "Loading tickets..." message visible |
| Loaded (with data) | Table with columns: Ticket ID, Title, Status (badge), Priority, Assignee, Last Updated |
| Loaded (empty) | "No tickets found" message |
| Filter applied | Table re-renders with only matching tickets; no additional API call |
| Error | "Could not load tickets. Retry?" with a retry button |

**Status badge colours**: `likely_in_progress` → blue, `stale` → orange, `blocked` → red, `done` → green, `open` → grey

---

## Section 2: Sprint Health

**Trigger**: Loads on page open

| State | Required behaviour |
|-------|--------------------|
| Loading | Skeleton cards or "Loading..." |
| Loaded | Four metric cards: Done, In Progress, Stale, Blocked — each showing count |
| No data | "No sprint data available" |
| Error | "Could not load sprint health." |

---

## Section 3: Org Performance

**Trigger**: Loads on page open

| State | Required behaviour |
|-------|--------------------|
| Loading | Skeleton cards or "Loading..." |
| Loaded | Three metric cards: Total Tickets, Stale, Blocked + velocity trend indicator |
| No velocity data | Velocity shows "Not enough data yet" |
| Error | "Could not load org metrics." |

---

## Section 4: AI Suggestions

**Trigger**: Loads on page open; refreshes after each approve/reject action

| State | Required behaviour |
|-------|--------------------|
| Loading | "Loading suggestions..." |
| Loaded (with data) | One card per pending suggestion; each has Approve and Reject buttons |
| Approve clicked | Button shows loading state; card removed on success; error shown inline on failure |
| Reject clicked | Button shows loading state; card removed on success; error shown inline on failure |
| Empty | "No pending suggestions" message |
| Error | "Could not load suggestions." |

---

## Section 5: Natural Language Query

**Trigger**: User submits a query via button click or Enter key

| State | Required behaviour |
|-------|--------------------|
| Idle | Query input and Submit button visible; response area empty |
| Loading | Submit button disabled; "Thinking..." indicator visible |
| Response received | Response displayed as plain text below the input |
| Empty query submitted | No API call; inline message "Please enter a question" |
| Error | "Could not get a response. Please try again." |
