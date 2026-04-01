# REST API Contract: Jira-Copilot Engineering Intelligence Agent

**Branch**: `001-jira-copilot-intelligence` | **Date**: 2026-03-31  
**Base path**: `/api/v1`  
**Auth**: All endpoints require a valid session token (inherited from organization's identity system). Access is scoped per-user to the Jira projects they are authorized to view.

---

## Work Visibility

### GET /tickets

Returns classified work status for all tickets visible to the current user.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team` | string | no | Filter by team name |
| `sprint_id` | string | no | Filter by sprint Jira ID |
| `assignee_id` | UUID | no | Filter by engineer ID |
| `project` | string | no | Filter by Jira project key |
| `priority` | string | no | Filter by Jira priority |
| `inferred_status` | string | no | One of: `officially_in_progress`, `likely_in_progress`, `blocked`, `stale`, `completed_not_updated` |
| `date_from` | ISO date | no | Filter tickets updated after this date |
| `date_to` | ISO date | no | Filter tickets updated before this date |

**Response** `200 OK`:
```json
{
  "tickets": [
    {
      "jira_id": "PROJ-123",
      "title": "Implement login flow",
      "assignee": { "id": "uuid", "display_name": "Alex Johnson" },
      "sprint": { "id": "uuid", "name": "Sprint 14" },
      "jira_status": "In Progress",
      "normalized_status": "in_progress",
      "inferred_status": "likely_in_progress",
      "inferred_status_reason": "Mentioned in standup transcript 1 day ago; no Jira update in 4 days.",
      "priority": "High",
      "story_points": 5,
      "updated_at": "2026-03-29T14:22:00Z"
    }
  ],
  "total": 42,
  "data_freshness": "2026-03-31T09:15:00Z"
}
```

---

### GET /tickets/{jira_id}

Returns full detail for a single ticket including recent activity signals.

**Response** `200 OK`:
```json
{
  "jira_id": "PROJ-123",
  "title": "Implement login flow",
  "description": "...",
  "assignee": { "id": "uuid", "display_name": "Alex Johnson" },
  "sprint": { "id": "uuid", "name": "Sprint 14" },
  "jira_status": "In Progress",
  "normalized_status": "in_progress",
  "inferred_status": "likely_in_progress",
  "inferred_status_reason": "Mentioned in standup transcript 1 day ago; no Jira update in 4 days.",
  "inferred_status_signals": {
    "jira_status_weight": 3,
    "recent_transcript_mention_weight": 2,
    "recent_comment_weight": 0,
    "recent_transition_weight": 0
  },
  "story_points": 5,
  "labels": ["auth", "frontend"],
  "linked_issues": ["PROJ-100", "PROJ-101"],
  "created_at": "2026-03-10T10:00:00Z",
  "updated_at": "2026-03-29T14:22:00Z",
  "due_date": "2026-04-05"
}
```

---

## Transcript Suggestions

### GET /suggestions

Returns the review queue of pending Jira update suggestions.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `approval_state` | string | no | Default: `pending`. One of: `pending`, `approved`, `rejected`, `auto_applied` |
| `confidence_tier` | string | no | One of: `high`, `medium`, `low` |
| `ticket_jira_id` | string | no | Filter by ticket |

**Response** `200 OK`:
```json
{
  "suggestions": [
    {
      "id": "uuid",
      "ticket": { "jira_id": "PROJ-123", "title": "Implement login flow" },
      "update_type": "status_transition",
      "proposed_value": { "new_status": "done" },
      "confidence_score": 0.93,
      "confidence_tier": "high",
      "approval_state": "pending",
      "conflict_flag": false,
      "source": {
        "transcript_id": "uuid",
        "meeting_title": "Sprint 14 Standup",
        "started_at": "2026-03-31T09:00:00Z",
        "excerpt": "Yeah, the login flow is done, I merged it this morning.",
        "speaker": "Alex Johnson",
        "excerpt_timestamp_seconds": 142
      },
      "created_at": "2026-03-31T09:17:00Z"
    }
  ],
  "total": 7
}
```

---

### POST /suggestions/{id}/approve

Approves a pending suggestion and applies the Jira update.

**Request body**: none required (optional `note` field).

```json
{ "note": "Confirmed with Alex in follow-up." }
```

**Response** `200 OK`:
```json
{
  "id": "uuid",
  "approval_state": "approved",
  "applied_at": "2026-03-31T10:05:00Z"
}
```

**Error responses**:
- `409 Conflict`: suggestion has `conflict_flag = true` — cannot approve until conflict is manually resolved.
- `403 Forbidden`: user does not have Jira access to the ticket's project.

---

### POST /suggestions/{id}/reject

Rejects a pending suggestion. No Jira change is made.

**Request body**:
```json
{ "reason": "Alex confirmed it's not actually done yet." }
```

**Response** `200 OK`:
```json
{
  "id": "uuid",
  "approval_state": "rejected",
  "rejection_reason": "Alex confirmed it's not actually done yet."
}
```

---

## Velocity & Metrics

### GET /velocity

Returns velocity metrics for one or more sprints.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `board_id` | string | yes | Jira board identifier |
| `sprint_count` | integer | no | Number of past sprints to include (default: 6) |

**Response** `200 OK`:
```json
{
  "board_id": "BOARD-1",
  "sprints": [
    {
      "sprint_id": "uuid",
      "name": "Sprint 13",
      "start_date": "2026-03-03",
      "end_date": "2026-03-16",
      "committed_points": 40,
      "completed_points": 36,
      "velocity": 36,
      "cycle_time_avg_days": 3.2,
      "lead_time_avg_days": 7.5,
      "throughput_tickets": 12
    }
  ],
  "trend": "stable",
  "average_velocity": 34.5,
  "current_sprint_forecast": {
    "sprint_id": "uuid",
    "name": "Sprint 14",
    "points_completed": 18,
    "points_remaining": 22,
    "days_remaining": 5,
    "forecast": "at_risk",
    "forecast_reason": "60% of duration elapsed; only 45% of points completed."
  }
}
```

---

### GET /bottlenecks

Returns tickets stuck in a stage longer than the team's historical average.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `board_id` | string | yes | Jira board identifier |

**Response** `200 OK`:
```json
{
  "bottlenecks": [
    {
      "ticket": { "jira_id": "PROJ-120", "title": "Payment module refactor" },
      "stuck_in_status": "In Review",
      "days_in_status": 8,
      "team_avg_days_in_status": 2.1,
      "overage_days": 5.9
    }
  ]
}
```

---

## Reports & Portfolio

### GET /reports/sprint-health

Returns sprint health summary across all boards visible to the user.

**Response** `200 OK`:
```json
{
  "teams": [
    {
      "board_id": "BOARD-1",
      "team_name": "Platform",
      "sprint_name": "Sprint 14",
      "health": "at_risk",
      "active_blockers": 2,
      "forecast": "at_risk",
      "completion_pct": 45
    }
  ],
  "generated_at": "2026-03-31T10:00:00Z"
}
```

---

### GET /reports/executive-summary

Returns aggregated portfolio view for leadership.

**Response** `200 OK`:
```json
{
  "summary_date": "2026-03-31",
  "teams": [ ... ],
  "initiatives": [
    {
      "name": "Q2 Auth Overhaul",
      "completion_pct": 62,
      "blocked_tickets": 1,
      "at_risk": true,
      "estimated_completion_date": "2026-04-18"
    }
  ],
  "overall_velocity_trend": "stable"
}
```

---

## Natural Language Query

### POST /query

Accepts a plain-language question and returns a plain-language answer with supporting data.

**Request body**:
```json
{
  "question": "Which engineers may be overloaded right now?",
  "context": { "board_id": "BOARD-1" }
}
```

**Response** `200 OK`:
```json
{
  "answer": "Two engineers appear overloaded based on current ticket load: Jordan Lee has 8 active tickets totaling 34 story points (team average: 19 points). Sam Chen has 6 active tickets with 3 in blocked state.",
  "supporting_data": {
    "engineers": [
      { "display_name": "Jordan Lee", "active_tickets": 8, "story_points": 34 },
      { "display_name": "Sam Chen", "active_tickets": 6, "blocked_tickets": 3 }
    ]
  },
  "data_freshness": "2026-03-31T09:15:00Z"
}
```

**Error responses**:
- `400 Bad Request`: question is empty or exceeds 500 characters.
- `422 Unprocessable Entity`: question cannot be answered from available data (e.g., references a team the user cannot access).

---

## Audit

### GET /audit

Returns audit log entries. Available to administrators only.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticket_jira_id` | string | no | Filter by ticket |
| `event_type` | string | no | Filter by event type |
| `from` | ISO datetime | no | Start of time range |
| `to` | ISO datetime | no | End of time range |
| `limit` | integer | no | Default 50, max 200 |

**Response** `200 OK`:
```json
{
  "entries": [
    {
      "id": "uuid",
      "event_type": "suggestion_auto_applied",
      "ticket": { "jira_id": "PROJ-123", "title": "Implement login flow" },
      "reasoning": "Transcript excerpt matched ticket with 0.93 confidence. Auto-apply enabled by admin. Update: status → done.",
      "signal_inputs": { "confidence_score": 0.93, "match_type": "semantic" },
      "created_at": "2026-03-31T09:17:32Z"
    }
  ],
  "total": 143
}
```
