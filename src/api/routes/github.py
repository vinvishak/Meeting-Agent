from typing import Annotated

from fastapi import APIRouter, Query

from src.storage.database import AsyncSessionLocal
from src.storage.repository import GitHubRepository

router = APIRouter()


@router.get("/github/repos")
async def list_github_repos() -> dict:
    async with AsyncSessionLocal() as session:
        rows = await GitHubRepository.list_repos(session)

    repos = [
        {
            "id": repo.id,
            "full_name": repo.full_name,
            "org": repo.org,
            "name": repo.name,
            "default_branch": repo.default_branch,
            "is_active": repo.is_active,
            "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
            "commit_count": commit_count,
            "open_pr_count": open_pr_count,
        }
        for repo, commit_count, open_pr_count in rows
    ]
    synced = sum(1 for r in repos if r["last_synced_at"] is not None)
    return {
        "repos": repos,
        "total": len(repos),
        "synced_count": synced,
        "never_synced_count": len(repos) - synced,
    }


@router.get("/github/commits")
async def list_github_commits(
    repo: Annotated[str | None, Query()] = None,
    jira_key: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    async with AsyncSessionLocal() as session:
        rows, total = await GitHubRepository.list_commits(
            session,
            repo_full_name=repo,
            jira_key=jira_key,
            limit=limit,
            offset=offset,
        )

    commits = [
        {
            "sha": commit.sha,
            "repo": commit.repo_id,  # resolved via join in list_commits
            "author_login": commit.author_login,
            "author_name": commit.author_name,
            "message": commit.message,
            "committed_at": commit.committed_at.isoformat(),
            "url": commit.url,
            "jira_keys": keys,
        }
        for commit, keys in rows
    ]
    return {"commits": commits, "total": total, "limit": limit, "offset": offset}


@router.get("/github/prs")
async def list_github_prs(
    repo: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    jira_key: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    async with AsyncSessionLocal() as session:
        rows, total = await GitHubRepository.list_prs(
            session,
            repo_full_name=repo,
            state=state,
            jira_key=jira_key,
            limit=limit,
            offset=offset,
        )

    prs = [
        {
            "id": pr.id,
            "repo": pr.repo_id,
            "pr_number": pr.pr_number,
            "title": pr.title,
            "state": pr.state,
            "author_login": pr.author_login,
            "head_branch": pr.head_branch,
            "opened_at": pr.opened_at.isoformat(),
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
            "url": pr.url,
            "jira_keys": keys,
        }
        for pr, keys in rows
    ]
    return {"prs": prs, "total": total, "limit": limit, "offset": offset}
