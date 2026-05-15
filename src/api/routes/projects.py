from fastapi import APIRouter, HTTPException

router = APIRouter()

_PROJECTS = [
    {"id": "proj-ai-dashboard", "name": "AI Project Management Dashboard", "owner": "Product Platform Team", "status": "at_risk", "target_date": "2026-06-30", "confidence_pct": 68},
    {"id": "proj-data-lake", "name": "Data Lake Migration", "owner": "Data Engineering Team", "status": "on_track", "target_date": "2026-07-15", "confidence_pct": 84},
    {"id": "proj-auth-modern", "name": "Auth Modernization", "owner": "Auth & Identity Team", "status": "blocked", "target_date": "2026-05-31", "confidence_pct": 32},
]

_PROJECT_DETAILS = {
    "proj-ai-dashboard": {
        "timeline": [
            {"phase": "Planning", "status": "done"},
            {"phase": "Design", "status": "done"},
            {"phase": "Development", "status": "in_progress"},
            {"phase": "Testing", "status": "not_started"},
            {"phase": "Launch", "status": "not_started"},
        ],
        "workstreams": [
            {"name": "Frontend", "owner": "Team A", "progress_pct": 70, "risk": "low"},
            {"name": "Backend APIs", "owner": "Team B", "progress_pct": 55, "risk": "medium"},
            {"name": "MCP Integrations", "owner": "Team C", "progress_pct": 40, "risk": "high"},
            {"name": "Analytics Layer", "owner": "Team D", "progress_pct": 65, "risk": "medium"},
        ],
        "activity": [
            {"source": "github", "text": "GitHub data not yet integrated — placeholder", "timestamp": "2026-05-01T14:23:00Z"},
            {"source": "jira", "text": "3 tickets moved to Done in Dashboard Layer epic", "timestamp": "2026-05-01T11:00:00Z"},
            {"source": "meeting", "text": "Backend team raised blocker: Copilot transcript access pending", "timestamp": "2026-04-30T10:00:00Z"},
            {"source": "jira", "text": "PR #184 waiting for review for 4 days", "timestamp": "2026-04-28T09:15:00Z"},
        ],
    },
    "proj-data-lake": {
        "timeline": [
            {"phase": "Planning", "status": "done"},
            {"phase": "Design", "status": "done"},
            {"phase": "Development", "status": "in_progress"},
            {"phase": "Testing", "status": "in_progress"},
            {"phase": "Launch", "status": "not_started"},
        ],
        "workstreams": [
            {"name": "Ingestion Pipeline", "owner": "Data Eng", "progress_pct": 82, "risk": "low"},
            {"name": "Schema Registry", "owner": "Platform", "progress_pct": 75, "risk": "low"},
            {"name": "Query Layer", "owner": "Analytics", "progress_pct": 60, "risk": "medium"},
        ],
        "activity": [
            {"source": "jira", "text": "Schema Registry epic moved to Testing", "timestamp": "2026-05-02T08:00:00Z"},
            {"source": "meeting", "text": "Team confirmed timeline on track for July release", "timestamp": "2026-05-01T14:00:00Z"},
        ],
    },
    "proj-auth-modern": {
        "timeline": [
            {"phase": "Planning", "status": "done"},
            {"phase": "Design", "status": "in_progress"},
            {"phase": "Development", "status": "not_started"},
            {"phase": "Testing", "status": "not_started"},
            {"phase": "Launch", "status": "not_started"},
        ],
        "workstreams": [
            {"name": "OAuth2 Migration", "owner": "Auth Team", "progress_pct": 20, "risk": "high"},
            {"name": "Session Management", "owner": "Auth Team", "progress_pct": 10, "risk": "high"},
        ],
        "activity": [
            {"source": "jira", "text": "All development tickets moved back to Blocked", "timestamp": "2026-04-29T16:00:00Z"},
            {"source": "meeting", "text": "External vendor dependency causing full team block", "timestamp": "2026-04-28T10:00:00Z"},
        ],
    },
}


@router.get("/projects")
async def list_projects() -> dict:
    return {"projects": _PROJECTS}


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    project = next((p for p in _PROJECTS if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    detail = _PROJECT_DETAILS.get(project_id, {})
    return {**project, **detail}
