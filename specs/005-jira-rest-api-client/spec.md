# Feature Specification: Jira Direct REST API Client

**Feature Branch**: `005-jira-rest-api-client`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Replace the Jira MCP client with a direct Jira REST API client so the application can run standalone without any MCP server for Jira."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Standalone Application Startup (Priority: P1)

An operator configures the application with their Jira workspace URL, login email, and API token in a `.env` file and starts the application. The application connects directly to Jira without needing any intermediate MCP server process running.

**Why this priority**: This is the foundational change. Without it, the application cannot run at all outside of Claude Code. Every other feature depends on a working Jira connection.

**Independent Test**: Can be fully tested by setting valid Jira credentials in `.env`, starting the application, and verifying it reaches Jira and returns ticket data. No MCP server process should be required.

**Acceptance Scenarios**:

1. **Given** a `.env` file with valid `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`, **When** the application starts, **Then** it successfully connects to Jira and the health check endpoint reports the Jira connection as healthy.
2. **Given** an invalid API token, **When** the application attempts to connect to Jira, **Then** a clear authentication error is logged and the application reports the Jira connection as unhealthy.
3. **Given** the old `JIRA_MCP_URL` and `JIRA_MCP_TOKEN` environment variables are present, **When** the application starts, **Then** these variables are ignored and the new variables are used instead.

---

### User Story 2 — Scheduled Ticket Sync (Priority: P1)

The background sync worker runs on its configured schedule, fetches all tickets from the configured Jira projects, and stores them in the local database — all without an MCP server running.

**Why this priority**: Equal priority to US1 — the sync is the core data pipeline. Without it, no ticket data reaches the dashboard or the AI analysis layer.

**Independent Test**: Can be tested by triggering a manual sync run and verifying that ticket records appear in the local database matching what is visible in Jira. Independent of transcript analysis or the dashboard.

**Acceptance Scenarios**:

1. **Given** a configured Jira project key and valid credentials, **When** the sync worker runs, **Then** all tickets from that project are fetched and stored in the local database.
2. **Given** a ticket has been updated in Jira since the last sync, **When** the sync runs again, **Then** the local record reflects the updated state.
3. **Given** a Jira project with more than 100 tickets, **When** the sync runs, **Then** all tickets are fetched across multiple pages and none are missed.
4. **Given** the Jira API returns a transient error, **When** the sync worker encounters it, **Then** the worker retries with backoff and logs a warning rather than crashing.

---

### User Story 3 — Ticket Updates Written Back to Jira (Priority: P2)

When an approved AI suggestion is applied, the application writes the update directly to Jira via the REST API. No MCP server is involved.

**Why this priority**: Closing the loop from analysis to action is the second most important capability. Without it, suggestions are read-only and operators must manually apply every change in Jira.

**Independent Test**: Can be tested by approving a suggestion and verifying the corresponding Jira ticket reflects the change. Independently verifiable without the dashboard or transcript pipeline.

**Acceptance Scenarios**:

1. **Given** an approved suggestion to update a ticket's status, **When** the update is applied, **Then** the ticket status changes in Jira and the local database reflects the new state.
2. **Given** a Jira ticket that the configured credentials do not have write access to, **When** an update is attempted, **Then** a permission error is logged and the suggestion is marked as failed — no crash occurs.

---

### Edge Cases

- What happens when `JIRA_BASE_URL` is missing the `https://` prefix or has a trailing slash?
- What happens when the Jira API rate limit is hit during a large sync?
- What if a ticket field (e.g. assignee, story points) is absent or null in the Jira response?
- What if the configured project key does not exist in the Jira workspace?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST authenticate with Jira using HTTP Basic Auth (email + API token) on every request.
- **FR-002**: The application MUST fetch ticket lists, individual tickets, sprint data, and comments from Jira without requiring an MCP server.
- **FR-003**: The application MUST support paginated Jira responses so that projects with more than 100 tickets are fully synced.
- **FR-004**: The application MUST write ticket field updates back to Jira directly when an approved suggestion is applied.
- **FR-005**: The configuration MUST accept `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` as the Jira connection settings, replacing the previous `JIRA_MCP_URL` and `JIRA_MCP_TOKEN` fields.
- **FR-006**: The application MUST retry failed Jira API requests with exponential backoff before reporting a failure.
- **FR-007**: All existing parsing logic for tickets, sprints, and comments MUST produce identical output to the previous MCP-based implementation.
- **FR-008**: The application MUST log a clear, actionable error message when Jira credentials are invalid or the workspace URL is unreachable.

### Key Entities

- **Jira Ticket**: A work item with an ID, summary, status, assignee, priority, labels, sprint, and timestamps — unchanged from the existing model.
- **Jira Sprint**: A time-boxed iteration with state (active/future/closed), start date, and end date — unchanged.
- **Jira Comment**: A timestamped message on a ticket with author and body — unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The application starts and connects to Jira successfully with no external processes other than the app itself running.
- **SC-002**: A full sync of a Jira project completes without errors and all tickets visible in Jira appear in the local database.
- **SC-003**: Ticket field updates approved by an operator are reflected in Jira within 5 seconds of approval.
- **SC-004**: All 108 existing unit tests continue to pass after the change.
- **SC-005**: A transient Jira API error during sync does not crash the worker — it retries and recovers automatically.

## Assumptions

- The Jira workspace is Jira Cloud (atlassian.net). Jira Server/Data Center is out of scope.
- The API token has sufficient permissions to read and write tickets in the configured projects.
- The existing Pydantic response models (`JiraIssue`, `JiraSprint`, `JiraComment`) and all parsing logic remain unchanged — only the data fetching mechanism changes.
- The Copilot MCP wrapper (`src/copilot_mcp/`) is unaffected by this change.
- The `mcp` Python package dependency remains in `pyproject.toml` as it is still used by `src/copilot_mcp/`.
