from fastapi import APIRouter

router = APIRouter()


@router.get("/org/health")
async def org_health() -> dict:
    return {
        "health_score": 82,
        "goals_on_track_pct": 73,
        "projects_at_risk": 12,
        "blocked_tickets": 47,
        "duplicate_work_areas": 9,
        "meeting_updates_avoided": 34,
    }


@router.get("/org/tree")
async def org_tree() -> dict:
    return {
        "id": "root",
        "label": "Launch AI Reporting Platform",
        "layer": "company_goal",
        "status": "on_track",
        "tooltip": None,
        "children": [
            {
                "id": "obj-1",
                "label": "Engineering Productivity",
                "layer": "department_objective",
                "status": "at_risk",
                "tooltip": None,
                "children": [
                    {
                        "id": "ini-1",
                        "label": "Dashboard Initiative",
                        "layer": "team_initiative",
                        "status": "at_risk",
                        "tooltip": None,
                        "children": [
                            {
                                "id": "epic-1",
                                "label": "Dashboard Layer",
                                "layer": "epic",
                                "status": "at_risk",
                                "tooltip": None,
                                "children": [
                                    {
                                        "id": "ticket-1",
                                        "label": "SCRUM-42: Build metrics API",
                                        "layer": "ticket",
                                        "status": "blocked",
                                        "tooltip": "Waiting on auth middleware PR review for 4 days",
                                        "children": [
                                            {
                                                "id": "github-1",
                                                "label": "GitHub data not yet integrated",
                                                "layer": "github",
                                                "status": "inactive",
                                                "tooltip": None,
                                                "children": [
                                                    {
                                                        "id": "meeting-1",
                                                        "label": "Sprint Planning: blocker raised",
                                                        "layer": "meeting_update",
                                                        "status": "on_track",
                                                        "tooltip": None,
                                                        "children": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "id": "ticket-2",
                                        "label": "SCRUM-43: Frontend components",
                                        "layer": "ticket",
                                        "status": "at_risk",
                                        "tooltip": None,
                                        "children": [],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "id": "obj-2",
                "label": "Data Infrastructure",
                "layer": "department_objective",
                "status": "on_track",
                "tooltip": None,
                "children": [
                    {
                        "id": "ini-2",
                        "label": "Data Lake Migration",
                        "layer": "team_initiative",
                        "status": "on_track",
                        "tooltip": None,
                        "children": [
                            {
                                "id": "epic-2",
                                "label": "Data Ingestion Pipeline",
                                "layer": "epic",
                                "status": "on_track",
                                "tooltip": None,
                                "children": [
                                    {
                                        "id": "ticket-3",
                                        "label": "SCRUM-55: Implement batch ETL",
                                        "layer": "ticket",
                                        "status": "on_track",
                                        "tooltip": None,
                                        "children": [
                                            {
                                                "id": "github-2",
                                                "label": "GitHub data not yet integrated",
                                                "layer": "github",
                                                "status": "inactive",
                                                "tooltip": None,
                                                "children": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }
