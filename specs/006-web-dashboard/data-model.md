# Data Model: Engineering Intelligence Web Dashboard

**Branch**: `006-web-dashboard` | **Date**: 2026-04-28

## Overview

The dashboard is a pure consumer of the backend API. It has no data model of its own — no database, no local storage. This document describes the shape of data the dashboard receives from each endpoint and how it maps to the UI.

---

## API Response Shapes

### Tickets — `GET /api/v1/tickets`

```
{
  "tickets": [
    {
      "jira_id": "SCRUM-3",
      "title": "Notification Preferences",
      "assignee": null | "Alice",
      "sprint": null | "Sprint 1",
      "jira_status": "In Progress",
      "normalized_status": "in_progress",
      "inferred_status": "likely_in_progress" | "stale" | "blocked" | "done" | "open",
      "inferred_status_reason": "...",
      "priority": "High" | "Medium" | "Low" | null,
      "story_points": null | number,
      "updated_at": "2026-04-01T22:08:51.866000"
    }
  ]
}
```

**UI mapping**: Each ticket → one table row. `inferred_status` → colour-coded badge. `updated_at` → formatted as relative time ("3 days ago").

---

### Sprint Health — `GET /api/v1/reports/sprint-health`

```
{
  "sprint_name": "Sprint 1" | null,
  "total_tickets": number,
  "by_status": {
    "done": number,
    "in_progress": number,
    "stale": number,
    "blocked": number,
    "open": number
  },
  "completion_rate": number   (0.0–1.0)
}
```

**UI mapping**: Each status count → a metric card with label, count, and colour. `completion_rate` → a progress bar.

---

### Org Metrics — `GET /api/v1/reports/executive-summary`

```
{
  "total_tickets": number,
  "stale_count": number,
  "blocked_count": number,
  "velocity": {
    "trend": "improving" | "declining" | "stable" | null,
    "throughput_last_period": number | null
  }
}
```

**UI mapping**: `total_tickets`, `stale_count`, `blocked_count` → three metric cards. `velocity.trend` → trend indicator arrow/label.

---

### Suggestions — `GET /api/v1/suggestions`

```
{
  "suggestions": [
    {
      "id": "uuid",
      "ticket_jira_id": "SCRUM-3",
      "update_type": "status_change" | "assignee_change" | "comment",
      "proposed_value": "Done",
      "reasoning": "Mentioned as complete in standup.",
      "confidence_score": 0.94,
      "approval_state": "pending"
    }
  ]
}
```

**UI mapping**: Each suggestion → a card with ticket ID, proposed change, confidence score (as %), reasoning, and Approve/Reject buttons. Only `pending` suggestions are shown.

---

### NL Query — `POST /api/v1/query`

Request:
```
{ "query": "which tickets are at risk?" }
```

Response:
```
{ "response": "Based on current data, SCRUM-2 and SCRUM-4 are stale..." }
```

**UI mapping**: `response` → displayed as plain text below the query input.
