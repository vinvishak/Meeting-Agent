from fastapi import APIRouter

router = APIRouter()


@router.get("/insights")
async def list_insights() -> dict:
    return {
        "insights": [
            {
                "id": "ins-1",
                "body": "The Data Platform team has high Jira activity but low GitHub commit activity this week.",
                "evidence": "47 Jira ticket transitions in the last 7 days vs. 3 GitHub commits from the same team.",
                "impact": "Planning work may be outpacing engineering execution, creating risk of sprint slip.",
                "recommended_action": "Review with team lead whether development work has started on the committed tickets.",
                "links": [{"label": "Data Platform", "type": "team", "id": "team-platform"}],
            },
            {
                "id": "ins-2",
                "body": "Three teams are independently building dashboard automation tooling with 87% topic similarity.",
                "evidence": "Separate Jira epics detected across Data Platform, Product Analytics, and BI & Reporting with overlapping ticket titles and meeting discussion patterns.",
                "impact": "Estimated 3× duplicated effort — approximately 60 engineering days of redundant work.",
                "recommended_action": "Schedule a consolidation session. The Platform team's existing reporting framework is the best foundation.",
                "links": [{"label": "View Duplicate Map", "type": "team", "id": "team-platform"}],
            },
            {
                "id": "ins-3",
                "body": "Leadership goal 'Modernize Data Infrastructure' has only 28% of linked tickets completed with 7 active blockers.",
                "evidence": "Goal progress at 28% with target date 2026-07-15. 7 tickets in blocked state across linked epics.",
                "impact": "At current velocity, the goal will miss its target date by an estimated 6 weeks.",
                "recommended_action": "Escalate the 7 blockers immediately. Consider a 2-week focused unblocking sprint.",
                "links": [{"label": "Modernize Data Infrastructure", "type": "project", "id": "proj-data-lake"}],
            },
        ]
    }
