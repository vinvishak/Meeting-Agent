# Data Model: GitHub PAT Client

**Feature**: 008-github-pat-client  
**Phase**: 1 — Design  
**Date**: 2026-05-02

All entities use the existing `Base` declarative base from `src/storage/models.py`. String UUIDs as primary keys, UTC-aware datetimes, JSON columns for arrays. Alembic migration: `002_github_schema.py`.

---

## Entity: GitHubRepo

**Table**: `github_repos`  
**Purpose**: Represents one synced GitHub repository under the configured org. Tracks last sync state.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | String(36) | PK, default UUID | Internal ID |
| `org` | String(255) | NOT NULL, indexed | GitHub org/owner name |
| `name` | String(255) | NOT NULL | Repository name (without org prefix) |
| `full_name` | String(511) | UNIQUE, NOT NULL | `{org}/{name}` — unique identifier |
| `default_branch` | String(100) | NOT NULL, default `"main"` | Default branch name from GitHub |
| `is_active` | Boolean | NOT NULL, default True | False = excluded from future syncs |
| `last_synced_at` | DateTime(tz) | nullable | Timestamp of last successful sync; `None` = never synced |
| `created_at` | DateTime(tz) | NOT NULL | Record creation time |

**Relationships**:
- `commits` → list[`GitHubCommit`] (one-to-many, backref `repo`)
- `pull_requests` → list[`GitHubPullRequest`] (one-to-many, backref `repo`)

**Indexes**: `(org)`, `UNIQUE(full_name)`

---

## Entity: GitHubCommit

**Table**: `github_commits`  
**Purpose**: A single git commit fetched from GitHub. Deduplicated by SHA.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | String(36) | PK, default UUID | Internal ID |
| `repo_id` | String(36) | FK → `github_repos.id`, NOT NULL, indexed | Which repository |
| `sha` | String(40) | UNIQUE, NOT NULL | Full git SHA |
| `message` | Text | NOT NULL | Full commit message |
| `author_login` | String(255) | nullable | GitHub username of author |
| `author_name` | String(255) | nullable | Git config display name |
| `author_email` | String(255) | nullable | Git config email |
| `committed_at` | DateTime(tz) | NOT NULL, indexed | Author timestamp from GitHub |
| `branch` | String(255) | nullable | Branch name if known (default branch synced) |
| `url` | String(1024) | nullable | GitHub web URL for the commit |
| `created_at` | DateTime(tz) | NOT NULL | Record creation time |

**Relationships**:
- `repo` → `GitHubRepo`
- `jira_links` → list[`GitHubJiraLink`] where `source_type = "commit"`

**Indexes**: `UNIQUE(sha)`, `(repo_id)`, `(committed_at)`

---

## Entity: GitHubPullRequest

**Table**: `github_pull_requests`  
**Purpose**: A GitHub pull request, keyed by `(repo_id, pr_number)`. Status updated on each sync.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | String(36) | PK, default UUID | Internal ID |
| `repo_id` | String(36) | FK → `github_repos.id`, NOT NULL, indexed | Which repository |
| `pr_number` | Integer | NOT NULL | GitHub PR number |
| `title` | String(500) | NOT NULL | PR title |
| `body` | Text | nullable | PR description (may be large) |
| `state` | String(20) | NOT NULL | `"open"`, `"closed"`, `"merged"` |
| `author_login` | String(255) | nullable | GitHub username of PR author |
| `head_branch` | String(255) | nullable | Source branch name |
| `base_branch` | String(255) | nullable | Target branch name |
| `opened_at` | DateTime(tz) | NOT NULL, indexed | When PR was created |
| `closed_at` | DateTime(tz) | nullable | When PR was closed (any state) |
| `merged_at` | DateTime(tz) | nullable | When PR was merged (null if not merged) |
| `url` | String(1024) | nullable | GitHub web URL for the PR |
| `last_synced_at` | DateTime(tz) | NOT NULL | Last time this PR's state was fetched |
| `created_at` | DateTime(tz) | NOT NULL | Record creation time |

**Table constraint**: `UNIQUE(repo_id, pr_number)`

**Relationships**:
- `repo` → `GitHubRepo`
- `jira_links` → list[`GitHubJiraLink`] where `source_type = "pr"`

**Indexes**: `UNIQUE(repo_id, pr_number)`, `(repo_id)`, `(state)`, `(opened_at)`

---

## Entity: GitHubJiraLink

**Table**: `github_jira_links`  
**Purpose**: Association between a GitHub artifact (commit or PR) and a Jira ticket key. A commit can link to multiple tickets; a ticket can be linked from multiple commits/PRs.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | String(36) | PK, default UUID | Internal ID |
| `source_type` | String(10) | NOT NULL | `"commit"` or `"pr"` |
| `commit_sha` | String(40) | nullable, indexed | Set when `source_type = "commit"` |
| `pr_id` | String(36) | FK → `github_pull_requests.id`, nullable, indexed | Set when `source_type = "pr"` |
| `jira_key` | String(50) | NOT NULL, indexed | Extracted key (e.g., `"SCRUM-42"`) |
| `ticket_id` | String(36) | FK → `tickets.id`, nullable, indexed | Resolved internal ticket ID; null = forward ref |
| `created_at` | DateTime(tz) | NOT NULL | Record creation time |

**Table constraint**: `UNIQUE(source_type, commit_sha, jira_key)` (for commit links), `UNIQUE(source_type, pr_id, jira_key)` (for PR links) — enforced via application-level upsert logic since SQLite doesn't support partial unique indexes cleanly.

**Relationships**:
- `pr` → `GitHubPullRequest` (when `source_type = "pr"`)
- `ticket` → `Ticket` (when resolved)

**Indexes**: `(commit_sha)`, `(pr_id)`, `(jira_key)`, `(ticket_id)`

---

## State Transitions

### GitHubRepo.last_synced_at
```
None (never synced)
  → [sync runs, succeeds] → datetime (UTC timestamp of sync completion)
  → [next sync runs] → updated datetime
```

### GitHubPullRequest.state
```
"open"
  → [sync detects merge] → "merged"
  → [sync detects close without merge] → "closed"
```

### GitHubJiraLink.ticket_id
```
None (forward reference — Jira not yet synced)
  → [jira sync runs, ticket arrives] → resolved ticket.id
```

---

## Migration Notes

- New migration file: `src/storage/migrations/versions/002_github_schema.py`
- `down_revision = "001_initial_schema"`
- Creates 4 tables in order: `github_repos` → `github_commits` → `github_pull_requests` → `github_jira_links`
- No changes to existing tables
