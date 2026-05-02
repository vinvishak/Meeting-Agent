# Quickstart: Engineering Intelligence Web Dashboard

**Branch**: `006-web-dashboard` | **Date**: 2026-04-28

## Prerequisites

- The backend is running: `python -m src.main`
- At least one sync has completed: `python -m src.workers.sync_worker --run-once`

## Open the Dashboard

Navigate to:

```
http://localhost:8000/app/index.html
```

That's it. No installation, no build step.

## What You'll See

| Section | Data source | Notes |
|---------|-------------|-------|
| Tickets | `/api/v1/tickets` | All synced Jira tickets with status badges |
| Sprint Health | `/api/v1/reports/sprint-health` | Counts by status category |
| Org Metrics | `/api/v1/reports/executive-summary` | Total, stale, blocked counts + velocity |
| Suggestions | `/api/v1/suggestions` | Pending AI suggestions (empty until transcripts are processed) |
| Query | `/api/v1/query` | Ask Claude a question about your tickets |

## Filtering Tickets

Use the status filter dropdown at the top of the tickets section to show only:
- All tickets
- In Progress
- Stale
- Blocked
- Done

## Approving/Rejecting Suggestions

Click **Approve** to apply the suggested Jira update, or **Reject** to dismiss it. The suggestion disappears from the list either way.

## Asking a Question

Type any question into the query box at the bottom of the page and press **Ask** or hit Enter. Example questions:
- "Which tickets are at risk this sprint?"
- "Who has the most stale tickets?"
- "What was completed last week?"

## Troubleshooting

**Dashboard shows "Could not load..."**: Check that `python -m src.main` is still running.

**Suggestions section is empty**: This is expected until meeting transcripts are processed. The Jira sync and ticket views work independently.

**Velocity shows "Not enough data"**: Run the sync worker a few more times over different days — velocity is calculated from historical snapshots.
