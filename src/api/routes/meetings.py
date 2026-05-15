from fastapi import APIRouter

router = APIRouter()

# Demo meeting — uncomment to show a fresh Copilot transcript appearing during a demo
_DEMO_MEETING = {
    "id": "mtg-demo",
    "name": "Engineering Leadership Sync — Q2 Checkpoint",
    "date": "2026-05-04",
    "summary_bullets": [
        "Q2 is tracking at 65% completion — on target for end-of-quarter delivery",
        "Auth & Identity team fully blocked on external vendor dependency (escalated to VP)",
        "Decision made to accelerate Prism dashboard rollout ahead of board demo",
        "Platform team to absorb one Auth ticket to unblock the critical path",
    ],
    "extracted_items": [
        {"type": "blocker", "item": "Auth vendor has not responded in 4 business days — VP escalation required", "owner": "Vishak", "linked_ticket": "SCRUM-301"},
        {"type": "decision", "item": "Prism dashboard demo moved to May 12 — all teams to prioritize readiness", "owner": "Vishak", "linked_ticket": None},
        {"type": "risk", "item": "Q2 velocity may drop if Auth blocker persists beyond this week", "owner": "Priya", "linked_ticket": "SCRUM-298"},
        {"type": "action", "item": "Platform team to pick up SCRUM-299 by Wednesday to unblock Auth critical path", "owner": "Alex", "linked_ticket": "SCRUM-299"},
    ],
}


@router.get("/meetings")
async def list_meetings() -> dict:
    return {
        "meetings": [
            # Uncomment to simulate a new Copilot transcript arriving during the demo:
            # _DEMO_MEETING,
            {
                "id": "mtg-1",
                "name": "Sprint Planning — Platform Team",
                "date": "2026-05-01",
                "summary_bullets": [
                    "Team committed to 18 tickets for Sprint 14",
                    "Main blocker is GitHub MCP auth token expiry",
                    "Dashboard API work is behind schedule by 3 days",
                    "Decision made to prioritize Jira integration before GitHub",
                ],
                "extracted_items": [
                    {"type": "blocker", "item": "Copilot transcript access pending vendor approval", "owner": "Alex", "linked_ticket": "SCRUM-221"},
                    {"type": "decision", "item": "Prioritize Jira integration before GitHub connector", "owner": "Priya", "linked_ticket": "SCRUM-198"},
                    {"type": "risk", "item": "Backend API timeline may slip by one week", "owner": "Sam", "linked_ticket": "SCRUM-207"},
                    {"type": "action", "item": "Update API schema documentation by Friday", "owner": "Nikhil", "linked_ticket": "SCRUM-233"},
                ],
            },
            {
                "id": "mtg-2",
                "name": "Weekly Standup — Data Engineering",
                "date": "2026-04-30",
                "summary_bullets": [
                    "Pipeline refactor is 82% complete, ahead of target",
                    "Schema registry PR approved and merged",
                    "No blockers reported",
                ],
                "extracted_items": [
                    {"type": "decision", "item": "Use Parquet format for all new data lake tables", "owner": "Nikhil", "linked_ticket": "SCRUM-189"},
                    {"type": "action", "item": "Run load test on ingestion pipeline before EOW", "owner": "Sam", "linked_ticket": None},
                ],
            },
        ]
    }
