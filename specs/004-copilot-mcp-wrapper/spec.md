# Feature Specification: Copilot MCP Wrapper — Teams Transcript Bridge

**Feature Branch**: `003-copilot-mcp-wrapper`
**Created**: 2026-04-05
**Status**: Draft
**Input**: User description: "Build a small MCP server (src/copilot_mcp/) that wraps the Microsoft Graph API to expose Microsoft Teams meeting transcripts for use by the Meeting Agent. The server must expose exactly three MCP tools: list_meetings, get_transcript, and get_meeting_summary. Authentication uses OAuth 2.0 client credentials flow with OnlineMeetings.Read.All and CallRecords.Read.All permissions. The server runs as an SSE or stdio MCP process configured via COPILOT_MCP_URL and COPILOT_MCP_TOKEN environment variables."

## Problem Statement

The Meeting Agent requires meeting transcript data to analyse team discussions and surface Jira update suggestions. Microsoft Teams is the organisation's meeting platform and Microsoft 365 Copilot generates summaries and action items after each meeting. However, no standard MCP server exists that exposes this data in the tool interface the Meeting Agent's ingestion layer expects.

Without this bridge, the transcript analysis pipeline (`src/ingestion/copilot_client.py`) cannot connect to any real data source, rendering the entire US2 feature — meeting-to-Jira suggestions — inoperative.

This feature closes that gap by providing a purpose-built MCP server that authenticates to the Microsoft Graph API and exposes exactly the three tools the ingestion layer already expects.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Meeting Agent Retrieves Recent Meeting List (Priority: P1)

An operator configures the Meeting Agent with the MCP server's endpoint and a bearer token. When the sync worker runs, it calls the `list_meetings` tool and receives a structured list of recent Teams meetings with metadata (ID, title, start time, participants), which it uses to decide which transcripts to fetch.

**Why this priority**: This is the entry point for all transcript ingestion. Without a working meeting list, no transcripts are ever fetched, and no Jira suggestions are ever created. Everything downstream depends on this.

**Independent Test**: Can be fully tested by starting the MCP server, calling `list_meetings` with valid credentials, and verifying it returns a non-empty list of meeting objects with the expected fields. No downstream Meeting Agent components are required.

**Acceptance Scenarios**:

1. **Given** the MCP server is running with valid Graph API credentials, **When** a client calls `list_meetings`, **Then** the server returns a list of meetings from the past 7 days, each with at minimum: `id`, `title`, `startedAt`, `endedAt`, and `participants`.
2. **Given** valid credentials and a `maxResults` parameter of 10, **When** `list_meetings` is called, **Then** no more than 10 meetings are returned.
3. **Given** the Graph API token has expired, **When** `list_meetings` is called, **Then** the server silently refreshes the token using the configured credentials and returns results without exposing internal token details to the caller.
4. **Given** no meetings occurred in the lookback window, **When** `list_meetings` is called, **Then** an empty list is returned (not an error).

---

### User Story 2 — Meeting Agent Retrieves Speaker-Attributed Transcript (Priority: P1)

After receiving a meeting ID from `list_meetings`, the Meeting Agent calls `get_transcript` with that ID and receives the full meeting transcript with speaker labels, utterance text, and timestamps — ready for entity matching and intent classification.

**Why this priority**: Equal priority to US1 — a transcript without a meeting list and a meeting list without transcripts both deliver zero value. Together they constitute the minimum viable data pipeline.

**Independent Test**: Can be fully tested by calling `get_transcript` with a known meeting ID that has a transcript, and verifying the response contains speaker-attributed text segments with timestamps. Independently verifiable without meeting list or summary tools.

**Acceptance Scenarios**:

1. **Given** a meeting ID for a completed meeting with a Teams transcript, **When** `get_transcript` is called, **Then** the server returns a structured transcript where each segment contains: `speaker` (display name), `text`, and `timestampSeconds`.
2. **Given** a meeting ID for a meeting that has not yet been transcribed (transcript processing in progress), **When** `get_transcript` is called, **Then** `null` is returned (not an error), allowing the caller to skip and retry later.
3. **Given** a meeting ID that does not exist or is not accessible under the configured credentials, **When** `get_transcript` is called, **Then** `null` is returned with a warning logged server-side; no exception is propagated to the caller.
4. **Given** a transcript that spans multiple Graph API pages, **When** `get_transcript` is called, **Then** all pages are automatically fetched and merged into a single response before returning.

---

### User Story 3 — Meeting Agent Retrieves Copilot Meeting Summary (Priority: P2)

After a meeting with Copilot summarisation enabled, the Meeting Agent calls `get_meeting_summary` and receives the Copilot-generated summary text and extracted action items, which supplement the raw transcript with higher-level context.

**Why this priority**: Valuable for enriching suggestions but not strictly required — the transcript alone is sufficient for the entity matching and intent classification pipeline. Summaries improve suggestion quality but are not on the critical path.

**Independent Test**: Can be tested independently by calling `get_meeting_summary` with a meeting ID that has a Copilot summary, and verifying the response contains `summary` text and an `actionItems` list. Delivers standalone value as a data enrichment tool.

**Acceptance Scenarios**:

1. **Given** a meeting ID where Copilot summarisation was enabled and completed, **When** `get_meeting_summary` is called, **Then** the server returns an object with `summary` (string) and `actionItems` (list of strings).
2. **Given** a meeting ID where Copilot summarisation was not enabled or has not completed, **When** `get_meeting_summary` is called, **Then** `null` is returned gracefully.
3. **Given** a meeting ID, **When** `get_meeting_summary` is called, **Then** the same meeting ID is used to fetch both the summary text and action items from the Graph API in a single logical operation (combining endpoints if needed).

---

### User Story 4 — Operator Configures and Validates the Server (Priority: P2)

An operator setting up the Meeting Agent for the first time runs the MCP server with their Azure app registration credentials and verifies it connects successfully to the Graph API before configuring the main agent to use it.

**Why this priority**: Operator experience matters for adoption. Without a clear validation path, misconfigured credentials cause silent failures deep in the sync pipeline that are hard to debug.

**Independent Test**: Can be tested by running the server with intentionally wrong credentials and verifying it surfaces a clear error, then with correct credentials and verifying a health/connectivity check succeeds.

**Acceptance Scenarios**:

1. **Given** all required environment variables are set correctly, **When** the server starts, **Then** it logs a confirmation that Graph API authentication succeeded and is ready to accept MCP tool calls.
2. **Given** an incorrect client secret is provided, **When** the server attempts to authenticate on startup, **Then** it logs a clear error message identifying the authentication failure and exits with a non-zero code.
3. **Given** the server is running, **When** a client connects and calls any of the three tools with a missing required parameter, **Then** the server returns a structured error with the parameter name and why it is required.
4. **Given** all environment variables are set, **When** the server is started with `--validate` flag, **Then** it tests Graph API connectivity, prints a pass/fail result for each required permission scope, and exits without serving.

---

### Edge Cases

- **Transcript not available yet**: Teams transcripts are processed asynchronously after a meeting ends. Calls to `get_transcript` within minutes of meeting completion may return nothing. The server returns `null`; the caller is responsible for retry logic.
- **Copilot not licensed or disabled**: Some tenants or users may not have Copilot summarisation. `get_meeting_summary` must return `null` gracefully rather than raising an error.
- **Meetings without transcription enabled**: Not all Teams meetings are configured to record and transcribe. `get_transcript` returns `null` for these; it does not surface a Graph API error to the caller.
- **Large transcripts**: Meetings several hours long can produce very large transcripts. The server must paginate Graph API responses transparently and return the full merged result.
- **Rate limiting**: The Graph API enforces per-tenant rate limits. The server must handle `429 Too Many Requests` responses with automatic backoff and retry, surfacing an error only after exhausted retries.
- **Token expiry during a long sync**: Access tokens expire after 1 hour. If a token expires mid-batch, the server must refresh silently without dropping the in-flight request.
- **Participant display name conflicts**: Two attendees with the same display name in the same meeting. The server returns whatever the Graph API provides; disambiguation is the caller's responsibility.
- **Missing tenant ID**: If `AZURE_TENANT_ID` is not set, the server must fail fast at startup with a clear error rather than attempting an unauthenticated request.

---

## Requirements *(mandatory)*

### Functional Requirements

**Tool Interface**

- **FR-001**: The server MUST expose exactly three MCP tools: `list_meetings`, `get_transcript`, and `get_meeting_summary`, with input and output schemas that match the interface expected by `src/ingestion/copilot_client.py` in the Meeting Agent.
- **FR-002**: `list_meetings` MUST accept an optional `maxResults` integer parameter (default 50) and return a list of meeting objects from across the entire tenant (all organisers), each containing: `id`, `title`, `startedAt`, `endedAt` (nullable), and `participants` (list of display name strings). Scoping to a specific organiser is out of scope.
- **FR-003**: `get_transcript` MUST accept a required `meetingId` string and return either a transcript object or `null`. The transcript object MUST contain: `id`, `title`, `startedAt`, `endedAt`, `participants`, and `rawTranscript` (a speaker-attributed string in the format `"DisplayName: utterance text\n"`).
- **FR-004**: `get_meeting_summary` MUST accept a required `meetingId` string and return either a summary object or `null`. The summary object MUST contain: `summary` (string) and `actionItems` (list of strings).
- **FR-005**: All three tools MUST return `null` for meetings that exist but lack the requested data (no transcript, no summary, transcription not enabled), rather than raising an error.

**Authentication**

- **FR-006**: The server MUST authenticate to the Microsoft Graph API using OAuth 2.0 client credentials flow (app-only, no user sign-in required).
- **FR-007**: The server MUST read credentials from environment variables: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`. It MUST fail at startup with a clear error message if any of these are absent.
- **FR-008**: The server MUST automatically refresh the Graph API access token before expiry and MUST NOT require a restart to obtain a new token.
- **FR-009**: The server MUST require `OnlineMeetings.Read.All` and `CallRecords.Read.All` application permissions on the Azure app registration. If these scopes are missing, the startup validation MUST surface a clear permission error.

**Transport and Configuration**

- **FR-010**: The server MUST support SSE (Server-Sent Events) transport, listening on a configurable host and port over plain HTTP. TLS termination is the responsibility of the deployment platform (reverse proxy or container ingress); the server itself does not handle certificates.
- **FR-011**: The server MUST be configurable entirely via environment variables, with no required config files. At minimum: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `MCP_HOST` (default `0.0.0.0`), `MCP_PORT` (default `3001`), `MCP_TOKEN` (optional bearer token for inbound auth), `TRANSCRIPT_LOOKBACK_DAYS` (default 7).
- **FR-012**: If `MCP_TOKEN` is set, the server MUST reject inbound MCP connections that do not present a matching `Authorization: Bearer <token>` header, returning a 401 response.
- **FR-013**: The server MUST handle `429 Too Many Requests` responses from the Graph API by waiting the duration specified in the `Retry-After` header (or 30 seconds if absent) and retrying the request, up to 3 total attempts before returning an error.

**Reliability and Observability**

- **FR-014**: The server MUST log each tool call (tool name, meeting ID if applicable, outcome, and duration) at INFO level using structured JSON logging.
- **FR-015**: The server MUST expose a `--validate` CLI flag that checks Graph API connectivity and required permission scopes, prints a human-readable pass/fail summary, and exits without starting the MCP server.
- **FR-016**: The server MUST handle Graph API pagination transparently: when a response contains a `@odata.nextLink`, the server MUST follow it and merge all pages before returning the result to the caller.
- **FR-017**: The server MUST expose a `GET /health` HTTP endpoint that returns `200 OK` with a JSON body `{"status": "ok"}` whenever the server process is running and accepting connections. This endpoint MUST NOT make any Graph API calls and MUST respond within 1 second.

---

### Key Entities

- **Meeting**: A Teams meeting record returned by Graph API, identified by its `id`. Contains title, start/end times, and participant list.
- **TranscriptSegment**: A single speaker turn within a meeting transcript: speaker display name, utterance text, and timestamp in seconds from meeting start.
- **MeetingSummary**: The Copilot-generated output for a meeting: a summary paragraph and a list of action item strings.
- **GraphToken**: An OAuth 2.0 access token with expiry time, held in memory and refreshed automatically. Never logged or returned to callers.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After configuration with valid Azure app credentials, the Meeting Agent's sync worker completes a full transcript ingestion cycle (list meetings → fetch transcripts → generate suggestions) without any manual intervention or credential errors.
- **SC-002**: `list_meetings` returns results within 3 seconds for a tenant with up to 100 meetings in the lookback window, under normal Graph API conditions.
- **SC-002b**: `get_transcript` returns a complete assembled transcript within 10 seconds per meeting under normal Graph API conditions, including transparent pagination for meetings with up to 500 utterances.
- **SC-003**: `get_transcript` correctly assembles paginated transcripts for meetings with more than 500 utterances, returning a complete and correctly ordered result on every call.
- **SC-004**: When presented with invalid credentials at startup, the server surfaces a human-readable error identifying the problem within 5 seconds, without requiring the operator to inspect raw HTTP responses.
- **SC-005**: The `--validate` flag correctly identifies missing Graph API permission scopes and reports them by name, enabling an operator to fix the Azure app registration without consulting documentation.
- **SC-006**: A token expiry event during an active batch of `get_transcript` calls does not cause any tool call to fail — the refresh is transparent and the result is returned successfully.
- **SC-007**: The server is deployable and runnable with a single command using only environment variables, with no additional config file creation required.

---

## Assumptions

- The organisation uses Microsoft 365 with Teams and has an Azure Active Directory tenant where an app registration can be created with application (not delegated) permissions.
- Meeting transcription is enabled at the tenant or meeting level for the meetings the agent needs to process; the server does not enable transcription — it only reads existing transcripts.
- Copilot summarisation (for `get_meeting_summary`) is available for at least some meetings; the server handles its absence gracefully and this is not a hard dependency.
- The Meeting Agent's `CopilotMCPClient` (`src/ingestion/copilot_client.py`) connects to the MCP server over SSE using the existing `COPILOT_MCP_URL` and `COPILOT_MCP_TOKEN` config — no changes to the ingestion layer are required.
- The MCP server runs as a separate process (or container) from the main Meeting Agent; it does not share in-process state with the agent.
- Access tokens obtained via client credentials flow are sufficient; no user-delegated permissions or interactive login flows are needed.
- The Graph API `callRecords` endpoint provides transcript content; if the tenant's retention policy has purged a transcript, `null` is the correct return value.
- No formal uptime SLA is required for this internal tool; best-effort availability with clear error logging is sufficient.
- The server is designed for a single concurrent client (the Meeting Agent). Multi-instance deployments are a future concern handled at the platform level; the server itself imposes no concurrency guarantees beyond single-client correctness.

## Clarifications

### Session 2026-04-05

- Q: Should the server support stdio transport in addition to SSE? → A: SSE is the primary transport (matches the existing `sse_client` in `src/ingestion/copilot_client.py`). stdio support is out of scope for this version.
- Q: Should lookback window be configurable per `list_meetings` call or only via env var? → A: Env var only (`TRANSCRIPT_LOOKBACK_DAYS`, default 7). Per-call override is out of scope to keep the interface minimal.
- Q: Is the `MCP_TOKEN` bearer token for inbound auth the same as `COPILOT_MCP_TOKEN` in the Meeting Agent? → A: Yes — the operator sets `MCP_TOKEN` on the server and the same value as `COPILOT_MCP_TOKEN` in the Meeting Agent's `.env`.
- Q: Which meetings does `list_meetings` return — all tenant meetings or scoped to a specific organiser? → A: All meetings in the tenant (org-wide, any organiser), enabled by application-level `OnlineMeetings.Read.All` permission. Per-organiser scoping is out of scope.
- Q: Does the server handle TLS directly or delegate to the deployment platform? → A: TLS terminated externally (reverse proxy or container ingress); the server runs plain HTTP. No certificate management in the application.
- Q: What is the latency target for `get_transcript`? → A: 10 seconds per transcript under normal Graph API conditions, covering paginated responses up to 500 utterances.
- Q: Does the server need a runtime health endpoint for container orchestration? → A: Yes — `GET /health` returning `200 OK` with `{"status": "ok"}`, no Graph API probe, responds within 1 second.
- Q: How many concurrent MCP client connections must the server support? → A: Single client only (the Meeting Agent); no multi-client concurrency requirements.
