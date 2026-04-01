# Data Model: Jira-Copilot Engineering Intelligence Agent

**Branch**: `001-jira-copilot-intelligence` | **Date**: 2026-03-31

All entities are persisted in SQLite via SQLAlchemy ORM. The 12-month rolling retention window applies to `TicketSnapshot` and `Transcript` records. All other reference entities are retained until explicitly deleted.

---

## Entity: Engineer

Canonical cross-system identity for a person who appears in Jira or Copilot data.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | Internal canonical ID |
| `display_name` | String | NOT NULL | Canonical display name (typically from Jira) |
| `email` | String | UNIQUE, nullable | Primary cross-system match key |
| `jira_username` | String | UNIQUE, nullable | Jira account ID or username |
| `copilot_display_names` | JSON Array | NOT NULL, default `[]` | All observed name variants from Copilot transcripts |
| `created_at` | DateTime | NOT NULL | |
| `updated_at` | DateTime | NOT NULL | |

**Relationships**: one-to-many with `Ticket` (as assignee), `TranscriptMention` (as speaker)

**Validation rules**:
- At least one of `email` or `jira_username` must be non-null.
- `copilot_display_names` must contain at least one entry once the engineer appears in a transcript.

---

## Entity: Ticket

Point-in-time snapshot of a Jira work item. The `Ticket` table holds the **current** state; `TicketSnapshot` holds historical states.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | Internal ID |
| `jira_id` | String | UNIQUE, NOT NULL | e.g., `PROJ-123` |
| `title` | String | NOT NULL | |
| `description` | Text | nullable | |
| `assignee_id` | UUID | FK → Engineer, nullable | |
| `sprint_id` | UUID | FK → Sprint, nullable | |
| `jira_status` | String | NOT NULL | Raw Jira status name |
| `normalized_status` | Enum | NOT NULL | One of: `open`, `in_progress`, `review`, `done`, `blocked` |
| `priority` | String | nullable | |
| `story_points` | Float | nullable | |
| `labels` | JSON Array | NOT NULL, default `[]` | |
| `created_at` | DateTime | NOT NULL | Ticket creation in Jira |
| `updated_at` | DateTime | NOT NULL | Last Jira update |
| `due_date` | Date | nullable | |
| `linked_issue_ids` | JSON Array | NOT NULL, default `[]` | Jira IDs of linked issues |
| `last_synced_at` | DateTime | NOT NULL | Last time this record was fetched from Jira |
| `inferred_status` | Enum | NOT NULL | One of: `officially_in_progress`, `likely_in_progress`, `blocked`, `stale`, `completed_not_updated` |
| `inferred_status_reason` | Text | NOT NULL | Human-readable explanation of signals used |
| `inferred_status_updated_at` | DateTime | NOT NULL | |

**State transitions** (`normalized_status`): `open` → `in_progress` → `review` → `done`. `blocked` is an overlay state that can apply at any stage. Non-standard Jira workflow statuses are mapped to this set via `StatusMapping`.

---

## Entity: TicketSnapshot

Immutable historical record of a ticket's state at a point in time. Retained for 12 months.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `ticket_id` | UUID | FK → Ticket, NOT NULL | |
| `jira_status` | String | NOT NULL | |
| `normalized_status` | Enum | NOT NULL | |
| `assignee_id` | UUID | FK → Engineer, nullable | |
| `sprint_id` | UUID | FK → Sprint, nullable | |
| `story_points` | Float | nullable | |
| `inferred_status` | Enum | NOT NULL | |
| `snapshot_at` | DateTime | NOT NULL | When this snapshot was taken |

**Retention**: Records older than 12 months are eligible for purge on the nightly maintenance job.

---

## Entity: Sprint

A Jira sprint (Scrum) or time-boxed reporting period (Kanban).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `jira_sprint_id` | String | UNIQUE, NOT NULL | |
| `name` | String | NOT NULL | |
| `board_id` | String | NOT NULL | Jira board identifier |
| `start_date` | Date | nullable | |
| `end_date` | Date | nullable | |
| `state` | Enum | NOT NULL | One of: `future`, `active`, `closed` |
| `committed_points` | Float | nullable | Story points committed at sprint start |
| `completed_points` | Float | nullable | Populated when sprint closes |
| `velocity` | Float | nullable | Computed: completed_points / sprint_duration_weeks |

---

## Entity: StatusMapping

Configurable rule that maps a raw Jira status name to a normalized lifecycle stage.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `board_id` | String | NOT NULL | Scoped to a specific Jira board |
| `jira_status_name` | String | NOT NULL | Raw status name as returned by Jira |
| `normalized_status` | Enum | NOT NULL | Target normalized stage |
| `created_at` | DateTime | NOT NULL | |

**Unique constraint**: `(board_id, jira_status_name)`

---

## Entity: Transcript

A meeting record ingested from the Copilot MCP Server. Retained for 12 months.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `copilot_meeting_id` | String | UNIQUE, NOT NULL | |
| `title` | String | nullable | Meeting title |
| `started_at` | DateTime | NOT NULL | |
| `ended_at` | DateTime | nullable | |
| `participants` | JSON Array | NOT NULL, default `[]` | List of display names from Copilot |
| `raw_transcript` | Text | NOT NULL | Full speaker-attributed text |
| `copilot_summary` | Text | nullable | Copilot-generated summary |
| `action_items` | JSON Array | NOT NULL, default `[]` | Copilot-extracted action items |
| `processed_at` | DateTime | nullable | When analysis was last run on this transcript |
| `last_synced_at` | DateTime | NOT NULL | |

---

## Entity: TranscriptMention

A reference to a Jira ticket found within a transcript, with resolution metadata.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `transcript_id` | UUID | FK → Transcript, NOT NULL | |
| `ticket_id` | UUID | FK → Ticket, nullable | Null if unresolved |
| `speaker_name` | String | NOT NULL | As attributed in the transcript |
| `speaker_engineer_id` | UUID | FK → Engineer, nullable | Resolved engineer (if matched) |
| `excerpt` | Text | NOT NULL | The specific transcript passage |
| `excerpt_timestamp_seconds` | Integer | nullable | Offset within the meeting |
| `match_type` | Enum | NOT NULL | One of: `exact_id`, `semantic`, `unresolved` |
| `match_confidence` | Float | NOT NULL | 0.0–1.0 |
| `mention_intent` | Enum | NOT NULL | One of: `progress_update`, `blocker`, `completion`, `ownership_change`, `eta_change`, `dependency`, `future_intent`, `ambiguous` |
| `created_at` | DateTime | NOT NULL | |

---

## Entity: UpdateSuggestion

A proposed Jira change derived from a `TranscriptMention`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `transcript_mention_id` | UUID | FK → TranscriptMention, NOT NULL | |
| `ticket_id` | UUID | FK → Ticket, NOT NULL | |
| `update_type` | Enum | NOT NULL | One of: `status_transition`, `add_comment`, `update_assignee`, `set_blocked`, `update_due_date` |
| `proposed_value` | JSON | NOT NULL | The proposed new value (varies by update_type) |
| `confidence_score` | Float | NOT NULL | 0.0–1.0 |
| `confidence_tier` | Enum | NOT NULL | One of: `high`, `medium`, `low` |
| `approval_state` | Enum | NOT NULL | One of: `pending`, `approved`, `rejected`, `auto_applied` |
| `conflict_flag` | Boolean | NOT NULL, default `false` | True if conflicting statements detected |
| `conflict_details` | Text | nullable | Description of conflicting statements |
| `reviewed_by_id` | UUID | FK → Engineer, nullable | Who approved or rejected |
| `reviewed_at` | DateTime | nullable | |
| `rejection_reason` | Text | nullable | Optional reason when rejected |
| `applied_at` | DateTime | nullable | When the change was applied to Jira |
| `created_at` | DateTime | NOT NULL | |

**Validation rules**:
- `conflict_flag = true` → `approval_state` may never be `auto_applied`.
- `approval_state = approved` requires `reviewed_by_id` to be non-null.
- `confidence_tier` is derived from `confidence_score`: ≥0.90 → high, 0.70–0.89 → medium, <0.70 → low.

---

## Entity: AuditEntry

Immutable log of any AI-driven classification, suggestion, application, or rejection.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | |
| `event_type` | Enum | NOT NULL | One of: `status_inferred`, `suggestion_created`, `suggestion_approved`, `suggestion_rejected`, `suggestion_auto_applied`, `sync_completed`, `sync_failed` |
| `ticket_id` | UUID | FK → Ticket, nullable | |
| `update_suggestion_id` | UUID | FK → UpdateSuggestion, nullable | |
| `transcript_mention_id` | UUID | FK → TranscriptMention, nullable | |
| `actor_engineer_id` | UUID | FK → Engineer, nullable | Human actor (if any) |
| `reasoning` | Text | NOT NULL | Human-readable explanation of why the system took this action |
| `signal_inputs` | JSON | NOT NULL, default `{}` | Raw signal values that contributed to the decision |
| `created_at` | DateTime | NOT NULL | Immutable — never updated |

**Retention**: AuditEntry records are never purged (they are lightweight and serve as the permanent audit trail per FR-015, FR-030).

---

## Entity Relationships Summary

```
Engineer ─────────────────────────────────────────────────────────────────────┐
  │ (assignee)                                                                  │
  ▼                                                                            │
Ticket ──── TicketSnapshot (history, 12-month retention)                      │
  │                                                                            │
  └──── Sprint (via sprint_id)                                                 │
  │                                                                            │
  └──── StatusMapping (via board_id → normalized_status)                      │
                                                                               │
Transcript ──── TranscriptMention ──── Ticket (resolved reference)            │
                     │                                                         │
                     └──── Engineer (speaker, via copilot_display_names) ─────┘
                     │
                     └──── UpdateSuggestion ──── AuditEntry
                                 │
                                 └──── Engineer (reviewer)
```
