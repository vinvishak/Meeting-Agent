# Feature Specification: Engineering Intelligence Web Dashboard

**Feature Branch**: `006-web-dashboard`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Build a web dashboard frontend for the Meeting Agent application providing a comprehensive view of the organisation's engineering performance."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ticket Status Overview (Priority: P1)

An engineering manager opens the dashboard and immediately sees all Jira tickets with their AI-inferred status, priority, assignee, and last updated time. They can filter by status (stale, blocked, in progress, done) to focus on what needs attention.

**Why this priority**: This is the core daily-use case. Without reliable ticket visibility the dashboard delivers no value. Everything else builds on top of this view.

**Independent Test**: Can be fully tested by opening the dashboard with the backend running and verifying that tickets from the SCRUM project appear with correct statuses, priorities, and timestamps. Filter controls reduce the visible set correctly.

**Acceptance Scenarios**:

1. **Given** the backend is running with synced tickets, **When** the user opens the dashboard, **Then** all tickets are displayed in a table with columns for ticket ID, title, status badge, priority, assignee, and last updated time.
2. **Given** tickets with different inferred statuses are present, **When** the user selects "Stale" from the status filter, **Then** only stale tickets are shown.
3. **Given** no tickets match the selected filter, **When** the filter is applied, **Then** a clear "No tickets found" message is shown rather than a blank area.
4. **Given** the backend is unreachable, **When** the dashboard loads, **Then** a friendly error message is shown with a retry option.

---

### User Story 2 — Sprint Health View (Priority: P1)

An engineering manager checks the current sprint's health at a glance — how many tickets are done, in progress, stale, or blocked — to prepare for standups or stakeholder updates.

**Why this priority**: Sprint health is the second most critical view. It gives leaders an immediate signal on whether the team is on track without manually counting tickets.

**Independent Test**: Can be tested independently by viewing the sprint health section and verifying that the counts of tickets in each status category match what the tickets view shows.

**Acceptance Scenarios**:

1. **Given** synced tickets exist, **When** the user views the sprint health section, **Then** they see a summary with counts for: Done, In Progress, Stale, and Blocked.
2. **Given** all tickets are in "To Do" status, **When** the sprint health section loads, **Then** the counts reflect this accurately with zero done and zero blocked.

---

### User Story 3 — Org Performance Summary (Priority: P2)

A team lead views the org performance summary to track key metrics: total ticket count, stale ticket count, blocked count, and velocity trends — providing an executive-level snapshot.

**Why this priority**: Valuable for weekly reporting and trend visibility, but less urgent than the live ticket and sprint views which are needed daily.

**Independent Test**: Can be tested by verifying the summary metrics panel shows accurate totals matching what is visible in the tickets list.

**Acceptance Scenarios**:

1. **Given** tickets are synced, **When** the user views the org summary, **Then** they see total tickets, stale count, and blocked count as prominent metric cards.
2. **Given** velocity data is available, **When** the user views the summary, **Then** a simple velocity trend indicator shows whether throughput is improving or declining.

---

### User Story 4 — AI Suggestion Review (Priority: P2)

An engineering lead reviews AI-generated suggestions for Jira ticket updates — such as status changes or assignee updates derived from meeting transcripts — and approves or rejects each one with a single click.

**Why this priority**: This closes the loop between meeting intelligence and Jira, but requires transcript data to be meaningful. Lower priority than the read-only views which work immediately.

**Independent Test**: Can be tested by checking the suggestions panel with and without pending suggestions, verifying approve and reject buttons trigger correctly and the suggestion disappears from the list after action.

**Acceptance Scenarios**:

1. **Given** AI suggestions exist, **When** the user opens the suggestions view, **Then** each suggestion shows the affected ticket, the proposed change, the confidence score, and the source (transcript mention).
2. **Given** a suggestion is displayed, **When** the user clicks "Approve", **Then** the suggestion is removed from the list and a success confirmation is shown.
3. **Given** a suggestion is displayed, **When** the user clicks "Reject", **Then** the suggestion is removed from the list without applying any change to Jira.
4. **Given** no suggestions are pending, **When** the user views the suggestions panel, **Then** a clear "No pending suggestions" message is shown.

---

### User Story 5 — Natural Language Query (Priority: P3)

A team member types a plain-English question such as "which tickets are at risk this sprint?" into a query box and receives a direct answer from Claude based on the current ticket data.

**Why this priority**: Useful power feature but not critical for daily operations. The first four stories cover structured data access; this adds unstructured conversational access on top.

**Independent Test**: Can be tested by typing a question and verifying a response appears. The response does not need to be evaluated for accuracy during testing — only that the round-trip works end-to-end.

**Acceptance Scenarios**:

1. **Given** the query box is visible, **When** the user types a question and submits, **Then** a loading indicator appears and a text response is shown within a few seconds.
2. **Given** a question is submitted, **When** the response arrives, **Then** it is displayed in a readable format below the query box, not replacing the box.
3. **Given** the backend query fails, **When** the response is returned, **Then** a user-friendly error message is shown and the query box remains editable.

---

### Edge Cases

- What happens when the backend is slow to respond — does the UI show a loading state?
- What if a ticket has no assignee or no priority set?
- What if the suggestions list is very long (50+ items)?
- What if the natural language query returns an empty response?
- What if the user submits an empty query?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST display all synced tickets with ticket ID, title, inferred status badge, priority, assignee, and last updated date.
- **FR-002**: Users MUST be able to filter the ticket list by inferred status (all, in progress, stale, blocked, done).
- **FR-003**: The dashboard MUST show a sprint health summary with ticket counts per status category.
- **FR-004**: The dashboard MUST show an org performance summary with total tickets, stale count, and blocked count as metric cards.
- **FR-005**: Users MUST be able to approve or reject individual AI suggestions with a single click, and the suggestion MUST disappear from the list after the action.
- **FR-006**: The dashboard MUST include a natural language query input that sends the question to the backend and displays the response.
- **FR-007**: All sections MUST show a loading state while data is being fetched.
- **FR-008**: All sections MUST show a clear, friendly error message if the backend is unreachable or returns an error.
- **FR-009**: The dashboard MUST work in a modern web browser without requiring any installation or build step by the user.
- **FR-010**: Inferred status values MUST be displayed with distinct visual treatment (e.g. colour-coded badges) so different statuses are immediately distinguishable.

### Key Entities

- **Ticket**: A Jira work item with ID, title, inferred status, Jira status, priority, assignee, and last updated timestamp.
- **Sprint Summary**: Aggregated count of tickets per status category for the current sprint.
- **Org Metrics**: Top-level counts — total tickets, stale, blocked — and a velocity trend indicator.
- **Suggestion**: An AI-generated proposed change to a ticket, with ticket reference, proposed update, confidence score, and approve/reject actions.
- **Query**: A plain-English question submitted by the user, paired with a Claude-generated response.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ticket list loads and displays all synced tickets within 2 seconds of opening the dashboard.
- **SC-002**: A user can identify which tickets are stale or blocked within 10 seconds of opening the dashboard, without reading documentation.
- **SC-003**: Approving or rejecting a suggestion takes no more than 2 clicks and completes within 3 seconds.
- **SC-004**: A natural language query receives a visible response within 10 seconds of submission.
- **SC-005**: The dashboard is fully usable on a 1280×800 desktop screen without horizontal scrolling.
- **SC-006**: All five views are accessible without page reload — navigation between sections is instant.

## Assumptions

- The backend API is running on `localhost:8000` and is accessible from the browser.
- Authentication uses a fixed bearer token `dev` for all API calls — no login screen is required.
- The dashboard targets desktop browsers only; mobile layout is out of scope for v1.
- Velocity trend data may not be available if no historical syncs have run; the UI should handle this gracefully with a "not enough data" message.
- The suggestions view will show an empty state if no transcripts have been processed yet — this is expected and not an error.
- A single HTML file with embedded CSS and JavaScript is acceptable if it avoids a build step; a lightweight multi-file structure is also acceptable.
