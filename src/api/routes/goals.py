from fastapi import APIRouter, HTTPException

router = APIRouter()

_GOALS = [
    {"id": "goal-1", "name": "Launch AI Reporting Platform", "owner": "Priya Sharma", "progress_pct": 72, "status": "on_track"},
    {"id": "goal-2", "name": "Improve Onboarding Experience", "owner": "Alex Chen", "progress_pct": 45, "status": "at_risk"},
    {"id": "goal-3", "name": "Reduce Support Ticket Volume", "owner": "Sam Patel", "progress_pct": 61, "status": "on_track"},
    {"id": "goal-4", "name": "Modernize Data Infrastructure", "owner": "Nikhil Rao", "progress_pct": 28, "status": "at_risk"},
]

_GOAL_DETAILS = {
    "goal-1": {"department_objective": "Engineering Productivity", "department_objective_status": "at_risk", "active_projects": 8, "epics_linked": 23, "tickets_in_progress": 114, "prs_merged_this_week": 31, "meeting_mentions": 12, "blockers": 5},
    "goal-2": {"department_objective": "Customer Experience", "department_objective_status": "at_risk", "active_projects": 4, "epics_linked": 11, "tickets_in_progress": 38, "prs_merged_this_week": 7, "meeting_mentions": 6, "blockers": 3},
    "goal-3": {"department_objective": "Operational Efficiency", "department_objective_status": "on_track", "active_projects": 6, "epics_linked": 18, "tickets_in_progress": 72, "prs_merged_this_week": 19, "meeting_mentions": 9, "blockers": 1},
    "goal-4": {"department_objective": "Platform Reliability", "department_objective_status": "at_risk", "active_projects": 3, "epics_linked": 9, "tickets_in_progress": 41, "prs_merged_this_week": 5, "meeting_mentions": 4, "blockers": 7},
}


@router.get("/goals")
async def list_goals() -> dict:
    return {"goals": _GOALS}


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str) -> dict:
    goal = next((g for g in _GOALS if g["id"] == goal_id), None)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    detail = _GOAL_DETAILS.get(goal_id, {})
    return {**goal, **detail}
