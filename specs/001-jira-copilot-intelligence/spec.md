# Feature Specification: Jira-Copilot Engineering Intelligence Agent

**Feature Branch**: `001-jira-copilot-intelligence`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: User description: "Create a specification for an AI product/agent that connects to both Jira MCP Server and GitHub Copilot / Copilot MCP Server to provide real-time engineering work visibility, ticket tracking intelligence, meeting-based updates, and executive reporting."

## Problem Statement

Engineering teams use Jira to track work and rely on meeting tools like GitHub Copilot for collaboration and transcription. These two sources of truth are rarely synchronized. Jira tickets go stale while real progress happens in meetings. Meetings surface blockers, ownership changes, and completion signals that never make it back into Jira. Leadership lacks a reliable, consolidated view of what is actually being worked on, what is at risk, and how fast the team is moving.

The result: missed deadlines go undetected, sprint health is unclear, managers spend hours manually reconciling meeting notes with ticket status, and executives receive reports that do not reflect reality.

This product eliminates that gap by intelligently connecting meeting activity to project tracking data, surfacing what is actually happening across engineering, and enabling safe, auditable updates back to Jira — all without requiring engineers to manually update tickets after every conversation.

## Goals

- Provide real-time, accurate visibility into engineering work status by combining Jira data with meeting transcript intelligence.
- Automatically detect progress, blockers, ownership changes, and risk signals from meeting transcripts and surface them for review or action.
- Give engineering leaders and executives a consolidated, trustworthy view of sprint health, velocity trends, and delivery risk.
- Enable natural language queries over the combined dataset so anyone can ask questions about work status in plain language.
- Maintain full auditability of all AI-driven insights and any changes proposed or made to Jira.

## Non-Goals

- This product does not replace Jira as the system of record; it augments and synchronizes it.
- This product does not manage or schedule meetings.
- This product does not generate code or provide coding assistance.
- This product does not enforce team processes or workflows beyond what already exists in Jira.
- Direct integration with calendar systems, email, or Slack is out of scope for the initial version.
- This product does not support Jira Service Management (helpdesk) workflows in the initial version; it targets software development boards only.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Real-Time Work Status View (Priority: P1)

An engineering manager opens the dashboard at the start of the day and immediately sees which tickets are actively being worked on, which are blocked, and which have gone stale — without manually checking Jira or reading through meeting notes.

**Why this priority**: This is the core daily use case. Without reliable work visibility, none of the other features deliver value. Engineering managers and leads depend on this to run standups, identify risks early, and respond to blockers without waiting for the next meeting.

**Independent Test**: Can be fully tested by connecting a Jira board with active tickets and verifying that the dashboard displays correct work status classifications for each ticket, derived from both Jira field values and recent activity signals. Delivers clear value as a standalone feature even without meeting integration.

**Acceptance Scenarios**:

1. **Given** a Jira board is connected and tickets have varying statuses and recent activity, **When** the manager opens the dashboard, **Then** each ticket is classified as one of: officially in progress, likely being worked on, blocked, stale, or completed but not updated — with the classification reason displayed.
2. **Given** a ticket is marked "In Progress" in Jira but has had no comments, transitions, or transcript mentions in the past 10 days, **When** the manager views the dashboard, **Then** the ticket is flagged as "stale" with a note showing the last activity date.
3. **Given** a ticket is mentioned in a meeting transcript as being actively worked on today, **When** the dashboard refreshes, **Then** the ticket is reclassified to "likely being worked on" even if its Jira status has not changed.
4. **Given** a manager filters by a specific engineer, **When** the filter is applied, **Then** only tickets assigned to or recently associated with that engineer are shown, along with their current status and activity signals.

---

### User Story 2 — Meeting Transcript Analysis and Jira Update Suggestions (Priority: P2)

After a sprint planning or standup meeting, an engineering lead reviews the system's suggested Jira updates — derived from what was discussed in the meeting — and approves or rejects each one with a single click.

**Why this priority**: Meeting transcripts contain the most current project intelligence that is rarely captured in Jira. Surfacing actionable update suggestions from meetings eliminates manual follow-up work and keeps Jira accurate. This is the highest-leverage automation in the product.

**Independent Test**: Can be fully tested by processing a sample meeting transcript and verifying that the system correctly identifies ticket references, classifies update types, assigns confidence scores, and surfaces them in the review queue. Delivers value independently of dashboards or velocity analysis.

**Acceptance Scenarios**:

1. **Given** a meeting transcript contains the phrase "we finished the login feature, closing it out," **When** the transcript is processed, **Then** the system identifies the relevant ticket, creates a suggestion to move it to "Done," assigns a confidence score, quotes the triggering transcript line, and adds it to the review queue.
2. **Given** a transcript contains conflicting statements ("I finished the payment module" from one participant and "we're still waiting on the payment module" from another), **When** processed, **Then** the system flags the conflict, presents both statements with speaker attribution, and requires manual resolution — it does not auto-apply either update.
3. **Given** a suggested update has a confidence score above the high-confidence threshold (e.g., 90%), **When** the admin has enabled auto-apply for high-confidence updates, **Then** the update is applied to Jira automatically with a log entry including the transcript excerpt and confidence score.
4. **Given** a suggested update has a confidence score below the threshold, **When** the lead views the review queue, **Then** the suggestion is shown with the exact transcript quote, proposed action, and confidence level — requiring explicit approval before any change is made.
5. **Given** a lead rejects a suggested update, **When** rejecting, **Then** the system records the rejection with an optional reason, and the update is never applied.

---

### User Story 3 — Velocity and Delivery Intelligence (Priority: P2)

A team lead reviews the sprint forecast dashboard to understand whether the current sprint is on track and where the team's velocity is heading — without building any reports manually.

**Why this priority**: Delivery predictability is a top concern for engineering managers and their stakeholders. Velocity trends and sprint risk flags reduce the surprise element in delivery and allow earlier course-correction.

**Independent Test**: Can be tested with historical Jira data by verifying that velocity metrics are calculated correctly across multiple sprints and that the sprint forecast reflects current progress relative to historical pace. Stands alone as a reporting feature without requiring meeting integration.

**Acceptance Scenarios**:

1. **Given** a team has completed multiple sprints with story points recorded, **When** the lead opens the velocity dashboard, **Then** they see average velocity per sprint, trend direction (improving / declining / stable), and a forecast of whether the current sprint will complete on time.
2. **Given** the current sprint is 60% through its duration but only 30% of story points are completed, **When** the dashboard loads, **Then** a risk flag is shown indicating the sprint is at risk, with the gap quantified and highlighted.
3. **Given** a ticket has remained in the same status for longer than the team's historical cycle time average for that stage, **When** the bottleneck view is opened, **Then** the ticket is listed as a bottleneck with its time-in-stage displayed.
4. **Given** a team lead filters by engineer, **When** the view updates, **Then** velocity, throughput, and work distribution metrics are shown per engineer, making overload visible.

---

### User Story 4 — Executive Summary and Portfolio Reporting (Priority: P3)

An engineering executive opens a weekly summary view and immediately understands the health of each team's sprint, which initiatives are at risk, and how overall delivery velocity is trending — without digging into individual tickets.

**Why this priority**: Executives need aggregated, signal-oriented views. Giving them a reliable summary reduces the need for manual status updates and improves organizational trust in engineering delivery data.

**Independent Test**: Can be tested by configuring multiple Jira projects and verifying that the executive view aggregates data correctly across projects, shows health indicators per team/initiative, and presents a clean summary without ticket-level detail unless the user drills down.

**Acceptance Scenarios**:

1. **Given** multiple Jira projects are connected, **When** an executive opens the portfolio view, **Then** they see each team's current sprint health (on track / at risk / off track), active blocker count, and sprint completion forecast per team.
2. **Given** an initiative spans multiple tickets across teams, **When** the initiative view is accessed, **Then** completion percentage, blocked item count, and estimated completion date are shown for the full initiative.
3. **Given** an executive wants to understand a specific risk, **When** they click on an at-risk indicator, **Then** they can drill into the underlying team dashboard showing the specific tickets contributing to the risk.

---

### User Story 5 — Natural Language Work Queries (Priority: P3)

An engineering manager types "which tickets are blocked and who owns them?" into the product's query interface and receives an accurate, plain-language answer with a supporting ticket list — without learning any query syntax.

**Why this priority**: Natural language access makes the product useful to a broader audience including managers and executives who do not want to learn filter interfaces. It also enables ad-hoc investigation beyond what pre-built dashboards offer.

**Independent Test**: Can be tested end-to-end by running a defined set of natural language questions against a known dataset and verifying that the answers are accurate. Stands alone as a query interface independent of dashboards.

**Acceptance Scenarios**:

1. **Given** the system has current Jira and transcript data, **When** a user asks "What is the team working on right now?", **Then** the system returns a plain-language summary listing active tickets with engineers and inferred status — not a raw ticket dump.
2. **Given** a user asks "Which engineers may be overloaded?", **When** the query is processed, **Then** the system identifies engineers with ticket counts or story point loads above the team average and explains the basis for the assessment.
3. **Given** a user asks "Which tickets were discussed in meetings but not updated in Jira?", **When** processed, **Then** the system cross-references transcript mentions against Jira update timestamps and returns the matching ticket list.

---

### Edge Cases

- **Informal ticket references**: A meeting mentions "the login bug" but no ticket number is given. The system must use title matching, keyword similarity, and context to resolve the reference. If no confident match exists (below match threshold), the mention is surfaced as an unresolved reference for manual linking.
- **Conflicting participant statements**: One participant says a ticket is done; another says it is still in progress. The system must surface both statements with speaker attribution and require manual resolution. Auto-apply must be blocked in conflict scenarios regardless of confidence score.
- **Verbally closed but technically open**: A ticket is declared "done" in a meeting but its pull request is unmerged or it remains open in Jira. The system should flag the discrepancy rather than automatically closing the ticket.
- **Active Jira ticket with no meeting mentions**: A ticket has been "In Progress" for two sprints with no transcript references. The system should surface it as potentially stale or invisible work, and flag it for manager review.
- **Heavy transcript activity but Jira stale**: A ticket is discussed in three consecutive standup transcripts but its Jira status has not changed in seven days. The system must flag this gap and suggest a status update.
- **Future work referenced in transcripts**: Transcript phrases like "we'll pick this up next sprint" or "plan to start that by end of month" should be tagged as future intent, not current progress, and must not trigger in-progress status updates.
- **One meeting, multiple tickets**: A single meeting discusses many tickets across different teams. The system must correctly scope updates to each ticket independently and not conflate context across tickets.
- **Multiple engineers, one ticket**: Two engineers are contributing to a single ticket. Work attribution and activity signals must account for both without duplicating credit or overwriting each other's updates.
- **Story point distortion**: A team's velocity appears to spike or drop due to poorly estimated tickets. The system should flag sprints where velocity variance is unusually high and allow the lead to exclude outlier sprints from trend calculations.
- **Non-standard Jira workflows**: Some boards use custom status names (e.g., "Awaiting Review" instead of "In Review"). The system must normalize these to standard lifecycle stages (open, in-progress, review, done, blocked) using configurable status mapping rather than hardcoded names.

---

## Requirements *(mandatory)*

### Functional Requirements

**Data Ingestion**

- **FR-001**: The system MUST connect to the Jira MCP Server and ingest ticket data every 15 minutes, including ticket ID, title, description, assignee, sprint, status, priority, story points, labels, created date, updated date, due date, comments, linked issues, and workflow transition history.
- **FR-002**: The system MUST connect to the Copilot MCP Server and ingest meeting transcripts, summaries, action items, and any available code activity context every 15 minutes.
- **FR-003**: The system MUST normalize ingested data from both sources into a unified internal data model that resolves entity overlaps (e.g., same engineer referred to by name, username, or email across systems).
- **FR-004**: The system MUST maintain historical snapshots of ticket state and transcript data for a rolling 12-month window to enable trend analysis over time; data older than 12 months may be purged.
- **FR-005**: The system MUST handle MCP server failures gracefully with automatic retry, and surface data freshness indicators to users when data may be stale due to sync failures.

**Work Status Classification**

- **FR-006**: The system MUST classify each tracked ticket into one of the following statuses: officially in progress, likely being worked on, blocked, stale, or completed but not updated — based on a combination of Jira field values and activity signals.
- **FR-007**: The system MUST display the reason for each inferred classification, citing the specific signals used (e.g., "last transcript mention: 2 days ago," "no Jira update in 8 days").
- **FR-008**: The system MUST allow users to filter work visibility views by engineer, team, sprint, project, priority, date range, and initiative.
- **FR-009**: The system MUST support configurable thresholds for what constitutes "stale" (e.g., no activity in N days), which administrators can adjust per team.

**Transcript Analysis and Jira Updates**

- **FR-010**: The system MUST analyze meeting transcripts to identify: ticket progress updates, blocker declarations, owner changes, ETA changes, newly mentioned work items, completion signals, and inter-ticket dependencies.
- **FR-011**: The system MUST match transcript ticket references to Jira tickets even when only informal names, feature descriptions, or shorthand terms are used, and must assign a match confidence score to each resolved reference.
- **FR-012**: The system MUST NOT apply any Jira update automatically unless an explicit auto-apply configuration is set by an administrator AND the confidence score meets or exceeds the configured high-confidence threshold.
- **FR-013**: All suggested Jira updates MUST be presented in a review queue showing: the proposed change, the exact transcript excerpt that triggered it, the confidence score, the speaker, and the timestamp within the meeting.
- **FR-014**: The system MUST allow any authenticated user to approve, reject, or edit suggested Jira updates, limited to tickets within projects they are already authorized to access in Jira.
- **FR-015**: The system MUST log every applied, rejected, or auto-applied update with a full audit record including: source transcript, triggering excerpt, confidence score, action taken, user who approved or rejected, and timestamp.
- **FR-016**: The system MUST surface conflicting transcript statements as unresolvable conflicts requiring manual resolution, and must block auto-application for any update in a conflict state.
- **FR-017**: The system MUST support the following Jira update types from transcript evidence: status transition, comment addition (summarizing meeting discussion), assignee update, blocker flag with reason, and sprint note or due date update.

**Velocity and Delivery Metrics**

- **FR-018**: The system MUST calculate and display velocity per sprint using story points completed, ticket count completed, and throughput (tickets per day or week).
- **FR-019**: The system MUST calculate cycle time (time from first transition to done) and lead time (time from ticket creation to done) per ticket, team, and sprint.
- **FR-020**: The system MUST compare planned vs. completed work at the end of each sprint when sprint commitment data is available.
- **FR-021**: The system MUST identify bottlenecks by detecting tickets that have remained in a single status longer than the team's historical average for that stage.
- **FR-022**: The system MUST generate a sprint completion forecast based on current progress and historical velocity, updated each time data is refreshed.
- **FR-023**: The system MUST flag sprints at risk of incompletion based on configurable risk thresholds (e.g., fewer than 40% of points completed with fewer than 40% of sprint days remaining).

**Reporting and Dashboards**

- **FR-024**: The system MUST provide a team operational dashboard and a separate executive summary dashboard as distinct views.
- **FR-025**: The system MUST support the following visualizations: tickets by status, sprint burndown/burnup, velocity trend by sprint, cycle time trend, blocker count over time, overdue tickets by assignee or team, work distribution by engineer, and sprint completion forecast.
- **FR-026**: The system MUST support natural language queries over the combined Jira and transcript dataset, returning plain-language answers with supporting ticket lists or data.
- **FR-027**: The system MUST support portfolio-level views aggregating metrics across multiple Jira projects or boards.

**Security and Access**

- **FR-028**: The system MUST enforce permission-aware access so that users can only view tickets and transcript data for projects and meetings they are authorized to access in the source systems.
- **FR-029**: The system MUST transmit and store all Jira and Copilot data using encryption.
- **FR-030**: The system MUST provide a clear audit trail for all AI-driven reasoning, including which data signals contributed to each classification or suggestion.

---

### Key Entities

- **Ticket**: A Jira work item with fields including ID, title, description, assignee, sprint, status, priority, story points, labels, dates, comments, linked issues, and workflow transition history.
- **Sprint**: A fixed-duration iteration containing a planned set of tickets, with start/end dates, velocity, and completion metrics.
- **Transcript**: A meeting record from the Copilot system containing speaker-attributed text, timestamps, associated meeting metadata, action items, and extracted summaries.
- **TranscriptMention**: A resolved or unresolved reference within a transcript to a specific ticket or work item, with a match confidence score and triggering text excerpt.
- **UpdateSuggestion**: A proposed Jira change derived from a transcript mention, including the proposed action, confidence score, triggering excerpt, and approval state (pending / approved / rejected / auto-applied).
- **Engineer**: A person contributing to work, resolvable across Jira (username/display name) and Copilot (meeting participant name/email).
- **AuditEntry**: A log record for any system-generated insight, suggestion, or applied change, including all reasoning inputs and the outcome.
- **StatusMapping**: A configurable rule that maps a team-specific Jira status name to a normalized lifecycle stage (open, in-progress, review, done, blocked).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Engineering managers can determine what the team is currently working on within 60 seconds of opening the dashboard, without consulting Jira or meeting notes directly.
- **SC-002**: At least 80% of ticket references in meeting transcripts are correctly matched to Jira tickets without manual correction, as measured in user acceptance testing on real team data.
- **SC-003**: The review queue for Jira update suggestions is processed by team leads within 24 hours of meeting completion in at least 90% of cases, as tracked by queue age metrics.
- **SC-004**: Sprint health indicators correctly predict whether a sprint will complete on time with at least 75% accuracy when measured at the sprint midpoint, compared to actual outcomes.
- **SC-005**: Engineers report spending at least 30% less time manually updating Jira after meetings compared to their pre-adoption baseline, measured via quarterly survey.
- **SC-006**: Zero Jira updates are applied without an audit entry that includes the triggering transcript excerpt, confidence score, and action taken.
- **SC-007**: The system supports at least 10 concurrent teams with 200+ active tickets per team without dashboard load times exceeding 5 seconds for standard views.
- **SC-008**: Executives report that the summary dashboard gives them sufficient project health information without needing to request manual status reports from engineering managers, as measured by survey after 60 days of use.

---

## Assumptions

- Users have valid access credentials to both the Jira MCP Server and the Copilot MCP Server; the product does not manage authentication setup.
- The Copilot MCP Server provides structured transcript data with speaker attribution; raw audio processing is out of scope.
- Teams are using Jira for software development work (Scrum or Kanban boards); service desk or IT support Jira workflows are out of scope for the initial version.
- Story points are used by at least some teams for velocity calculation; teams without story points will use ticket count and throughput as alternative velocity metrics.
- The organization has pre-existing Jira permissions that govern who can view which projects; this product inherits and enforces those permissions without replacing them.
- Each engineer can be identified across Jira and Copilot systems by a resolvable identifier (name, email, or username); cases where names cannot be matched across systems will require manual entity resolution during initial setup.
- Meetings conducted via platforms integrated with GitHub Copilot for transcript capture are the only source of meeting intelligence; other meeting platforms are out of scope unless they surface data through the Copilot MCP Server.
- The initial version targets teams of 5–20 engineers on a single Jira instance; multi-instance Jira federation is a future capability.
- Administrators configure the confidence thresholds and auto-apply settings; the product ships with conservative defaults (no auto-apply enabled by default, high-confidence threshold set at 90%).
- This product is internal tooling with no formal external compliance requirements (no GDPR, SOC 2, or regulatory audit obligations); standard organizational security practices apply.
- No formal uptime SLA is required; the system operates on a best-effort basis with failures handled reactively. Data freshness indicators (FR-005) communicate sync status to users when the system is unavailable or delayed.

## Clarifications

### Session 2026-03-31

- Q: What compliance or regulatory requirements apply to this product? → A: No formal compliance requirement — internal tooling only.
- Q: How frequently should the system sync data from Jira and Copilot MCP servers? → A: Every 15 minutes.
- Q: Who can approve suggested Jira updates in the review queue? → A: Any authenticated user, scoped to projects they are already authorized to access in Jira.
- Q: How long should the system retain historical ticket state and transcript snapshots? → A: 12 months (rolling window).
- Q: What availability/uptime target applies to this product? → A: Best-effort; no formal uptime SLA required.

### Session 2026-04-05

- Q: Does a "Copilot MCP Server" exist that can be directly configured via URL and token? → A: No stable, published Copilot MCP Server with the required tool surface exists. The Copilot integration MUST be implemented as a purpose-built MCP server (`src/copilot_mcp/`) that wraps the Microsoft Graph API to expose Teams meeting transcripts. The server MUST expose exactly three tools matching the expected interface: `list_meetings` (returns meeting metadata for a configurable lookback window), `get_transcript` (returns full speaker-attributed transcript for a given meeting ID), and `get_meeting_summary` (returns Copilot-generated summary and action items for a given meeting ID). Authentication to Graph API uses OAuth 2.0 client credentials flow (app registration with `OnlineMeetings.Read.All` and `CallRecords.Read.All` delegated or application permissions). The MCP server runs as a local stdio or SSE process and is configured via `COPILOT_MCP_URL` / `COPILOT_MCP_TOKEN` in the same way as the Jira MCP Server, so the rest of the ingestion layer requires no changes.
