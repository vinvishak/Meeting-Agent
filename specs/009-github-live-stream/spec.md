# Feature Specification: Real-Time GitHub Activity Stream

**Feature Branch**: `009-github-live-stream`  
**Created**: 2026-05-03  
**Status**: Draft  
**Input**: User description: "Real-time GitHub activity stream — receive GitHub push webhooks the instant a commit is pushed, store it in the database, and push a live update to the engineering dashboard via Server-Sent Events so engineers see new commits appear within seconds without manually refreshing"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Commit Feed on Dashboard (Priority: P1)

An engineer has the engineering dashboard open in their browser. When a teammate pushes a commit to any tracked GitHub repository, the commit appears in the dashboard's activity feed within seconds — without the engineer needing to refresh the page. A "Live" badge confirms the stream is connected.

**Why this priority**: This is the core user-facing value of the feature. Everything else (webhook ingestion, persistence) exists solely to power this real-time update.

**Independent Test**: Can be fully tested by opening the dashboard, simulating a push webhook event, and verifying the commit card appears in the feed within 5 seconds without a page refresh.

**Acceptance Scenarios**:

1. **Given** the dashboard is open and the activity feed is visible, **When** a new commit is pushed to a tracked repository, **Then** the commit appears at the top of the feed within 5 seconds with author, message, repository, and timestamp.
2. **Given** the dashboard is open, **When** the live stream connects successfully, **Then** a green "Live" indicator is visible in the activity section header.
3. **Given** the dashboard has been open for an extended period, **When** no commits have arrived for 20+ seconds, **Then** the connection stays open (keepalive) and the Live badge remains green.
4. **Given** the network connection drops briefly, **When** the connection is restored, **Then** the dashboard automatically reconnects to the live stream without user action.

---

### User Story 2 - Webhook Ingestion and Persistence (Priority: P2)

When GitHub delivers a push webhook to the server, the system validates the request's authenticity, extracts commit metadata, persists every commit to the database, and extracts any Jira ticket keys mentioned in commit messages for cross-linking.

**Why this priority**: Persistence ensures commits survive server restarts and are available to other features (sync, reports). It is a prerequisite for reliable live delivery, but the live-update experience (US1) can be demonstrated independently with in-memory events.

**Independent Test**: Can be fully tested by sending a POST request with a valid GitHub push payload and HMAC signature, then querying the database to confirm commits were stored and Jira keys were extracted.

**Acceptance Scenarios**:

1. **Given** GitHub sends a push webhook with a valid HMAC-SHA256 signature, **When** the server receives it, **Then** all commits in the payload are stored in the database within 2 seconds.
2. **Given** a commit message contains one or more Jira ticket keys (e.g. "ENG-123"), **When** the webhook is processed, **Then** each key is recorded as a link between that commit and the Jira ticket.
3. **Given** GitHub sends a webhook with an invalid or missing signature, **When** the server receives it, **Then** the request is rejected with a 403 response and nothing is stored.
4. **Given** the same commit SHA is received twice (duplicate delivery), **When** the second webhook is processed, **Then** no duplicate record is created — the existing commit is updated in place.

---

### User Story 3 - Dashboard Activity Feed Historical View (Priority: P3)

When an engineer opens the dashboard for the first time or after a page reload, the activity feed is pre-populated with the most recent commits already stored in the database, so there is no blank state waiting for the next live event.

**Why this priority**: Enhances the dashboard's usefulness at load time, but the live stream works independently of historical seeding.

**Independent Test**: Can be fully tested by loading the dashboard after commits exist in the database and confirming they appear in the feed before any new webhook fires.

**Acceptance Scenarios**:

1. **Given** commits exist in the database, **When** the dashboard page loads, **Then** up to 20 recent commits are displayed in reverse-chronological order.
2. **Given** no commits exist in the database, **When** the dashboard page loads, **Then** the feed shows an empty state message ("No recent activity").

---

### Edge Cases

- What happens when GitHub delivers a push event with zero commits (e.g., a branch deletion)? The webhook should be acknowledged (200) but nothing stored.
- What happens when the server has no connected dashboard clients when a commit arrives? The event is dropped gracefully; there is no queue backpressure since SSE clients reconnect.
- What happens when a commit message contains multiple Jira keys (e.g., "Fixes ENG-12 and ENG-34")? Both links are created.
- What happens when many commits arrive in rapid succession (a force-push with 100 commits)? All commits are persisted; only the head commit or a summary is broadcast to avoid flooding the dashboard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an HTTPS endpoint that receives GitHub push webhook payloads.
- **FR-002**: The system MUST validate each incoming webhook request using HMAC-SHA256 signature verification before processing it.
- **FR-003**: The system MUST persist every commit from a valid push payload — including SHA, author name, commit message, repository name, and timestamp — to durable storage.
- **FR-004**: The system MUST extract Jira ticket key references (e.g. "ENG-123") from commit messages and store a link between the commit and the ticket.
- **FR-005**: The system MUST broadcast a live event to all connected dashboard clients within 5 seconds of receiving a valid push webhook.
- **FR-006**: The system MUST provide a streaming endpoint that dashboard clients can subscribe to for real-time commit events without polling.
- **FR-007**: The streaming endpoint MUST keep connections alive with periodic keepalive signals so clients do not time out during idle periods.
- **FR-008**: The streaming endpoint MUST NOT require authentication tokens (to allow browser EventSource connections which cannot set custom headers).
- **FR-009**: The dashboard activity feed MUST display newly arrived commits at the top of the feed without requiring a page refresh.
- **FR-010**: The dashboard MUST display a visual indicator showing whether the live stream connection is active.
- **FR-011**: The dashboard MUST automatically reconnect to the live stream if the connection is interrupted.
- **FR-012**: Duplicate commits (same SHA) MUST be upserted — not duplicated — in storage.

### Key Entities

- **Push Event**: A notification from GitHub that one or more commits were pushed to a repository branch. Contains repository metadata, pusher identity, branch name, and an ordered list of commits.
- **Commit**: A single code change unit with a unique SHA, author, timestamp, message, and parent repository. The persisted record tracks which Jira tickets the commit references.
- **Jira Link**: An association between a commit SHA and a Jira ticket key, derived by parsing the commit message.
- **Live Event**: An ephemeral notification broadcast to connected clients when a new commit is ingested. Contains enough commit metadata for the dashboard to render a card without a follow-up API call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Commits appear in the dashboard activity feed within 5 seconds of a push event reaching the server.
- **SC-002**: 100% of commits from valid webhook payloads are stored in the database (zero loss under normal conditions).
- **SC-003**: Webhooks with invalid signatures are rejected 100% of the time with no data written.
- **SC-004**: The live stream connection stays open indefinitely during an active session without requiring manual reconnection (assuming no network failure).
- **SC-005**: After a network interruption, the dashboard reconnects automatically within 5 seconds of connectivity being restored.
- **SC-006**: Duplicate push deliveries (same SHA) produce exactly one database record per commit — no duplicates.

## Assumptions

- GitHub webhook delivery is trusted at the network level once HMAC validation passes; no additional IP allowlist is required for MVP.
- The dashboard is a single-page application running in a modern browser that supports the EventSource API natively.
- The server runs as a single process (no horizontal scaling), so an in-process event broadcaster is sufficient — no external message broker is needed.
- Commit history from before this feature was deployed is populated through the existing periodic sync mechanism, not through historical webhook replay.
- Push events to any branch of a tracked repository are ingested; branch filtering is out of scope for this feature.
- The dashboard shows a maximum of 20 recent commits in the initial load to keep page performance acceptable.
