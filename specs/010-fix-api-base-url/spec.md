# Feature Specification: Fix Dashboard API Base URL

**Feature Branch**: `010-fix-api-base-url`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "Fix dashboard API base URL — the frontend hardcodes http://localhost:8000 as the API base URL, which breaks the dashboard when deployed to any remote host like Railway. The fix should make the frontend call the API on whatever host served the page, so the dashboard works both locally and in production without any code changes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Works in Production (Priority: P1)

An engineer opens the dashboard on the Railway-hosted URL and sees data load correctly — goals, tickets, activity — without any configuration changes or environment-specific builds.

**Why this priority**: This is the root cause of the current production outage. The dashboard is completely non-functional in any deployed environment because every API call silently fails by targeting a non-existent local server.

**Independent Test**: Open the dashboard at the Railway URL. All sections (Overview, Goals, Teams, Projects, Meetings, Insights) should load data. No errors in the browser console about failed network requests to localhost.

**Acceptance Scenarios**:

1. **Given** the dashboard is accessed on Railway, **When** the page loads, **Then** the overview section displays org health data without an error banner
2. **Given** the dashboard is accessed on Railway, **When** a user clicks any navigation tab, **Then** data loads successfully for that section
3. **Given** the dashboard is accessed locally during development, **When** the page loads, **Then** it still works exactly as before with no regression

---

### Edge Cases

- What happens when the API server is unreachable? The dashboard should show a user-friendly error, not silently fail or show a blank page.
- Does the fix work when the app is served from a subpath (e.g. `/app`)? API calls must still resolve correctly relative to the page origin.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST call the backend API on the same host and port that served the page, without any hardcoded addresses
- **FR-002**: The fix MUST require zero configuration — no environment variables, build flags, or code changes are needed when deploying to a new host
- **FR-003**: The dashboard MUST continue to work identically in local development as it did before the fix
- **FR-004**: All dashboard sections MUST load data correctly after the fix with no partial regressions

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of dashboard sections load data successfully when accessed via the Railway production URL
- **SC-002**: Zero changes to developer workflow — local development continues to work without any additional steps
- **SC-003**: No new environment-specific configuration is required to deploy the dashboard to any host

## Assumptions

- The backend API and frontend are served from the same origin (same host and port), which is true for this project's architecture
- The fix applies only to the frontend — no backend changes are needed
- Local development uses a local server, and the fix must not break that workflow
