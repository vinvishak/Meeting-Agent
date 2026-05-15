from fastapi import APIRouter, HTTPException

router = APIRouter()

_TEAMS = [
    {"id": "team-platform", "name": "Data Platform", "status": "at_risk", "sprint_progress_pct": 61, "blocked_tickets": 8, "prs_merged": 14, "open_prs": 6, "last_meeting_summary": "3 blockers raised, 2 decisions made, 1 dependency flagged"},
    {"id": "team-data-eng", "name": "Data Engineering", "status": "on_track", "sprint_progress_pct": 78, "blocked_tickets": 2, "prs_merged": 22, "open_prs": 4, "last_meeting_summary": "Sprint on track, ahead of velocity target"},
    {"id": "team-auth", "name": "Auth & Identity", "status": "blocked", "sprint_progress_pct": None, "blocked_tickets": 11, "prs_merged": 3, "open_prs": 9, "last_meeting_summary": "All work blocked on external dependency"},
]

_SPRINTS = {
    "team-platform": {
        "team_id": "team-platform",
        "sprint_name": "Sprint 14",
        "epics": [
            {"name": "Data Ingestion", "ticket_count": 18, "status": "on_track", "github_activity": "high", "meeting_mentions": 4},
            {"name": "Dashboard Layer", "ticket_count": 11, "status": "at_risk", "github_activity": "medium", "meeting_mentions": 7},
            {"name": "Auth Migration", "ticket_count": 9, "status": "blocked", "github_activity": "low", "meeting_mentions": 3},
        ],
    },
    "team-data-eng": {
        "team_id": "team-data-eng",
        "sprint_name": "Sprint 14",
        "epics": [
            {"name": "Pipeline Refactor", "ticket_count": 14, "status": "on_track", "github_activity": "high", "meeting_mentions": 2},
            {"name": "Schema Registry", "ticket_count": 8, "status": "on_track", "github_activity": "medium", "meeting_mentions": 1},
        ],
    },
    "team-auth": {"team_id": "team-auth", "sprint_name": None, "epics": []},
}


@router.get("/teams")
async def list_teams() -> dict:
    return {"teams": _TEAMS}


@router.get("/teams/{team_id}/sprint")
async def team_sprint(team_id: str) -> dict:
    if team_id not in _SPRINTS:
        raise HTTPException(status_code=404, detail="Team not found.")
    return _SPRINTS[team_id]
