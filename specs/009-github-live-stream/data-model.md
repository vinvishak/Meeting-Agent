# Data Model: Real-Time GitHub Activity Stream

**Feature**: `009-github-live-stream` | **Date**: 2026-05-03

All entities are persisted in SQLite via Alembic migration `002_github_schema.py`. No schema changes are needed beyond what that migration already defines.

---

## Entity: GitHubRepo

Represents a GitHub repository tracked by the system.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID string | PK | Internal identifier |
| org | string(255) | NOT NULL, indexed | GitHub org/user login |
| name | string(255) | NOT NULL | Repository short name |
| full_name | string(511) | NOT NULL, UNIQUE | `org/repo` canonical name |
| default_branch | string(100) | NOT NULL | e.g. `main` |
| is_active | boolean | NOT NULL | Whether actively synced |
| last_synced_at | datetime(tz) | nullable | Timestamp of last periodic sync |
| created_at | datetime(tz) | NOT NULL | Row creation timestamp |

**Key invariant**: `full_name` is the natural key. Upsert on `full_name` — create or update.

---

## Entity: GitHubCommit

A single commit received via push webhook or periodic sync.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID string | PK | Internal identifier |
| repo_id | UUID string | FK → GitHubRepo, indexed | Parent repository |
| sha | string(40) | NOT NULL, UNIQUE | Git SHA (40 hex chars) |
| message | text | NOT NULL | Full commit message |
| author_login | string(255) | nullable | GitHub username of author |
| author_name | string(255) | nullable | Display name from Git config |
| author_email | string(255) | nullable | Email from Git config |
| committed_at | datetime(tz) | NOT NULL, indexed | Commit timestamp |
| branch | string(255) | nullable | Branch the push targeted |
| url | string(1024) | nullable | GitHub web URL |
| created_at | datetime(tz) | NOT NULL | Row creation timestamp |

**Key invariant**: `sha` is the natural key. Upsert on `sha` — duplicate deliveries are idempotent.

---

## Entity: GitHubJiraLink

Association between a commit (or PR) and a Jira ticket key extracted from the message/title.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID string | PK | Internal identifier |
| source_type | string(10) | NOT NULL | `"commit"` or `"pr"` |
| commit_sha | string(40) | nullable, indexed | FK-by-value to GitHubCommit.sha |
| pr_id | UUID string | nullable, indexed, FK → GitHubPullRequest | Set when source_type = "pr" |
| jira_key | string(50) | NOT NULL, indexed | e.g. `ENG-123` |
| ticket_id | UUID string | nullable, FK → tickets.id | Resolved after Jira sync |
| created_at | datetime(tz) | NOT NULL | Row creation timestamp |

**Key invariant**: One row per (commit_sha, jira_key) pair. Created during webhook ingestion; `ticket_id` resolved during the periodic Jira sync.

---

## Entity: GitHubPullRequest

Pull requests synced from GitHub (via periodic sync, not webhooks — out of scope for this feature but defined in the same migration).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID string | PK | Internal identifier |
| repo_id | UUID string | FK → GitHubRepo, indexed | Parent repository |
| pr_number | integer | NOT NULL | GitHub PR number |
| title | string(500) | NOT NULL | PR title |
| body | text | nullable | PR description |
| state | string(20) | NOT NULL, indexed | `"open"`, `"closed"`, `"merged"` |
| author_login | string(255) | nullable | GitHub username |
| head_branch | string(255) | nullable | Source branch |
| base_branch | string(255) | nullable | Target branch |
| opened_at | datetime(tz) | NOT NULL, indexed | PR creation timestamp |
| closed_at | datetime(tz) | nullable | When closed |
| merged_at | datetime(tz) | nullable | When merged |
| url | string(1024) | nullable | GitHub web URL |
| last_synced_at | datetime(tz) | NOT NULL | Last sync timestamp |
| created_at | datetime(tz) | NOT NULL | Row creation timestamp |

**Key invariant**: `(repo_id, pr_number)` is unique. Managed by periodic sync, not by this feature's webhooks.

---

## Ephemeral: Live Event (SSE payload)

Not persisted — broadcast in-memory from server to connected dashboard clients.

| Field | Type | Description |
|-------|------|-------------|
| type | string | Always `"new_commit"` for push events |
| commit.sha | string(8) | Short SHA (first 8 chars) |
| commit.message | string(120) | First line of commit message, truncated to 120 chars |
| commit.author_login | string | GitHub username or display name |
| commit.url | string | GitHub web URL to the commit |
| commit.committed_at | ISO 8601 string | Commit timestamp |
| commit.jira_keys | string[] | Extracted Jira ticket keys (may be empty) |
| commit.repo | string | `org/repo` full name |

---

## Relationships

```
GitHubRepo ──< GitHubCommit ──< GitHubJiraLink >── tickets (JiraTicket)
           ──< GitHubPullRequest ──< GitHubJiraLink
```
