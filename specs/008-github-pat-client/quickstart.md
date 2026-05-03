# Quickstart & Test Scenarios: GitHub PAT Client

**Feature**: 008-github-pat-client  
**Phase**: 1 — Design  
**Date**: 2026-05-02

---

## Prerequisites

1. `.env` file includes:
   ```
   GITHUB_PAT=ghp_your_real_token_here
   GITHUB_ORG=your-github-org
   GITHUB_REPOS=          # empty = all repos; or comma-separated: repo-a,repo-b
   ```

2. PAT has `repo` scope (read access to private repos) or `public_repo` scope (public only).

3. Application running: `uv run uvicorn "src.api.app:create_app" --factory --reload`

4. DB migration applied: `uv run alembic upgrade head`

---

## Scenario 1: Initial Full Sync

**Goal**: Verify that the GitHub sync fetches repos, commits, and PRs from scratch.

**Steps**:
```bash
# Trigger a single sync cycle (includes GitHub sync)
uv run python -m src.workers.sync_worker --run-once
```

**Expected**:
- Log output: `GitHub sync started for org: <your-org>`
- Log output: `Discovered N repos under <your-org>`
- Log output: `GitHub sync complete: N repos, M commits, K PRs`
- API returns data:
```bash
curl http://localhost:8000/api/v1/github/repos \
  -H "X-API-Key: dev-key"
# → {"repos": [...], "total": N, "synced_count": N}
```

---

## Scenario 2: Commit Listing and Jira Link

**Goal**: Verify commits are stored and Jira keys are extracted.

**Steps**:
```bash
curl "http://localhost:8000/api/v1/github/commits?limit=5" \
  -H "X-API-Key: dev-key"
```

**Expected** (if any commits reference a Jira key):
```json
{
  "commits": [
    {
      "sha": "...",
      "message": "Fix SCRUM-42: ...",
      "jira_keys": ["SCRUM-42"],
      ...
    }
  ]
}
```

**Jira-filtered query**:
```bash
curl "http://localhost:8000/api/v1/github/commits?jira_key=SCRUM-42" \
  -H "X-API-Key: dev-key"
# → only commits mentioning SCRUM-42
```

---

## Scenario 3: PR Listing by State

**Goal**: Verify PRs are stored with correct state.

```bash
# All open PRs
curl "http://localhost:8000/api/v1/github/prs?state=open" \
  -H "X-API-Key: dev-key"

# All merged PRs in a specific repo
curl "http://localhost:8000/api/v1/github/prs?state=merged&repo=myorg/backend" \
  -H "X-API-Key: dev-key"
```

---

## Scenario 4: Incremental Sync

**Goal**: Verify that a second sync only fetches new activity.

**Steps**:
1. Run first sync → note commit count from logs.
2. Wait or make a commit in GitHub.
3. Run sync again.
4. Log shows: `GitHub sync complete: N repos, +M new commits` where M < full history.

---

## Scenario 5: Prism Dashboard — GitHub Nodes Activated

**Goal**: Verify the dashboard updates after sync.

**Steps**:
1. Open `http://localhost:8000/app` in browser.
2. Go to "Org Overview" tab.
3. Before sync: GitHub nodes appear gray with "inactive" status.
4. Run: `uv run python -m src.workers.sync_worker --run-once`
5. Refresh the page.
6. After sync: GitHub nodes appear green with "active" status and a commit count.

---

## Scenario 6: Invalid PAT Handling

**Goal**: Verify graceful failure.

**Steps**:
1. Temporarily set `GITHUB_PAT=ghp_invalid` in `.env`.
2. Restart server to reload config.
3. Run: `uv run python -m src.workers.sync_worker --run-once`

**Expected**:
- Log: `GitHub auth failed: 401 Unauthorized — check GITHUB_PAT`
- Sync cycle completes without crashing (GitHub section skipped, Jira still runs).
- Dashboard GitHub nodes remain `inactive`.

---

## Scenario 7: GITHUB_REPOS Filter

**Goal**: Verify repo filtering when `GITHUB_REPOS` is set.

**Steps**:
1. Set `GITHUB_REPOS=specific-repo` in `.env`.
2. Run sync.
3. `GET /api/v1/github/repos` returns exactly 1 repo.

---

## Dev Utility: Inspect Raw Database

```bash
# See stored repos
sqlite3 data/agent.db "SELECT full_name, last_synced_at FROM github_repos;"

# See stored commits
sqlite3 data/agent.db "SELECT sha, author_login, committed_at FROM github_commits LIMIT 10;"

# See Jira links
sqlite3 data/agent.db "SELECT source_type, commit_sha, jira_key FROM github_jira_links LIMIT 20;"
```
