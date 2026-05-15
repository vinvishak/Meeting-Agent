from fastapi import APIRouter

router = APIRouter()


@router.get("/redundancy")
async def list_redundancy() -> dict:
    return {
        "clusters": [
            {
                "id": "dup-1",
                "theme": "Dashboard Automation",
                "teams": ["Data Platform", "Product Analytics", "BI & Reporting"],
                "similarity_score": 87,
                "recommendation": "Consolidate into one shared reporting framework owned by Platform",
            },
            {
                "id": "dup-2",
                "theme": "GitHub Analytics Integration",
                "teams": ["DevOps", "Platform Engineering"],
                "similarity_score": 74,
                "recommendation": "Reuse the existing GitHub API layer from DevOps in Platform work",
            },
            {
                "id": "dup-3",
                "theme": "Meeting Transcript Summaries",
                "teams": ["PMO", "AI Team"],
                "similarity_score": 52,
                "recommendation": "Evaluate sharing the transcript pipeline — low overlap but worth reviewing",
            },
        ]
    }
