# Feature Specification: GitHub PAT Client

**Feature Branch**: `008-github-pat-client`
**Created**: 2026-05-02
**Status**: Draft
**Input**: User description: "GitHub PAT Client: REST API integration using Personal Access Token authentication to sync commits and PRs, link them to Jira tickets, and activate GitHub nodes in the Prism dashboard"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - GitHub Commit & PR Sync (Priority: P1)

A team lead wants to see real GitHub activity in the Prism dashboard — commits and pull requests from their team's repositories — without manually exporting data. The system periodically fetches commits and PRs from GitHub using a configured Personal Access Token, stores them locally, and makes them queryable.

**Why this priority**: Core data acquisition layer — every other user story depends on this data being available. Without synced GitHub data, all downstream features are inert.

**Independent Test**: After configuring `GITHUB_PAT`, `GITHUB_ORG`, and `GITHUB_REPOS` in `.env` and triggering a sync, the user can query the backend and see commits and PRs returned from the database.

**Acceptance Scenarios**:

1. **Given** valid PAT, org, and repo config in `.env`, **When** a sync runs, **Then** commits and PRs from all configured repos are fetched from GitHub and stored in the local database.
2. **Given** `GITHUB_REPOS` is empty, **When** a sync runs, **Then** all repositories visible to the PAT under the org are discovered automatically and synced.
3. **Given** the sync has already run once, **When** a second sync runs, **Then** only activity since the last sync timestamp is fetched (incremental sync).
4. **Given** an invalid or revoked PAT, **When** a sync runs, **Then** the system logs a clear authentication error and does not crash.
5. **Given** GitHub API rate limit is hit, **When** a sync runs, **Then** the system waits for the reset window before retrying and logs the delay.

---

### User Story 2 - Jira Ticket Linking (Priority: P2)

An engineering manager wants to see which commits and PRs are linked to specific Jira tickets, so they can track progress without switching between Jira and GitHub. The system scans commit messages and PR titles/bodies for Jira ticket keys (e.g., `SCRUM-42`, `DATA-7`) and records the association.

**Why this priority**: Transforms raw GitHub activity into actionable intelligence — the bridge between code work and planning artifacts.

**Independent Test**: After syncing, querying the API for a Jira ticket that appears in a commit message returns the linked commits/PRs in the response.

**Acceptance Scenarios**:

1. **Given** a commit message contains `SCRUM-42`, **When** linking runs, **Then** the commit is associated with ticket `SCRUM-42` in the database.
2. **Given** a PR title contains `[DATA-7] Add pipeline`, **When** linking runs, **Then** the PR is associated with ticket `DATA-7`.
3. **Given** a commit message contains multiple ticket keys (e.g., `Fix SCRUM-1 and SCRUM-2`), **When** linking runs, **Then** the commit is associated with both tickets.
4. **Given** a commit message contains no recognizable ticket key, **When** linking runs, **Then** the commit is stored without a Jira link and no error is raised.
5. **Given** the Jira ticket key references a ticket not yet in the local DB, **When** linking runs, **Then** the link is stored as a forward reference and resolved on next Jira sync.

---

### User Story 3 - Prism Dashboard GitHub Nodes (Priority: P3)

A product executive viewing the Prism dashboard currently sees GitHub nodes in the Goal-to-Execution Tree and Project Detail page marked as "inactive" (gray placeholders). After this feature is active, those nodes display real commit counts, PR status, and latest activity timestamps sourced from synced GitHub data.

**Why this priority**: The visible payoff of the entire feature — the Prism dashboard becomes a true live view. Depends on US1 and US2 being complete.

**Independent Test**: After a sync runs, refreshing the Prism dashboard shows GitHub nodes with a green `active` status badge and real commit/PR metrics instead of gray placeholders.

**Acceptance Scenarios**:

1. **Given** GitHub data has been synced, **When** the Org Overview tree is loaded, **Then** GitHub nodes display `active` status with a recent commit count.
2. **Given** a project has linked commits and open PRs, **When** the Project Detail page is loaded, **Then** the activity feed shows real GitHub commits and PRs with timestamps.
3. **Given** no GitHub sync has run yet, **When** the dashboard loads, **Then** GitHub nodes display an `inactive` state with a tooltip explaining sync is pending.
4. **Given** a sync failure occurred, **When** the dashboard loads, **Then** GitHub nodes display a `stale` state indicating data may be outdated.

---

### Edge Cases

- What happens when a repository has no commits in the sync window? — The repo is recorded as synced with zero new items; no error.
- What happens when the GitHub org has 100+ repositories and `GITHUB_REPOS` is empty? — Pagination is handled; all repos are discovered across multiple API pages.
- How does the system handle PRs that are subsequently closed or merged after the initial sync? — Status changes are updated on the next incremental sync.
- What happens when a Jira project key uses a non-standard pattern (e.g., `PROJ123-1`)? — The regex pattern covers standard `[A-Z]+-\d+` keys; non-standard patterns are silently skipped.
- What happens when the same commit appears in multiple branches? — Commits are deduplicated by SHA; only one record is stored.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate all GitHub API requests using the `GITHUB_PAT` environment variable as a Bearer token.
- **FR-002**: System MUST discover all repositories under `GITHUB_ORG` when `GITHUB_REPOS` is empty, handling pagination.
- **FR-003**: System MUST fetch commits (author, timestamp, message, SHA, branch) for each configured repository.
- **FR-004**: System MUST fetch pull requests (title, body, state, author, open/merge timestamp, head branch) for each configured repository.
- **FR-005**: System MUST perform incremental syncs, fetching only activity after the last recorded sync timestamp per repository.
- **FR-006**: System MUST extract Jira ticket keys matching the pattern `[A-Z]+-\d+` from commit messages and PR titles/bodies.
- **FR-007**: System MUST store commit-to-ticket and PR-to-ticket associations in the database.
- **FR-008**: System MUST integrate with the existing sync worker so GitHub sync runs on the same schedule as Jira sync (every 15 minutes).
- **FR-009**: System MUST expose a `/api/v1/github/commits` endpoint returning recent commits, optionally filtered by repo or Jira ticket key.
- **FR-010**: System MUST expose a `/api/v1/github/prs` endpoint returning pull requests, optionally filtered by repo, state, or Jira ticket key.
- **FR-011**: System MUST expose a `/api/v1/github/repos` endpoint listing all synced repositories with last-sync metadata.
- **FR-012**: The Prism dashboard GitHub nodes in the Org Overview tree MUST display `active` status and commit count when synced data exists.
- **FR-013**: The Prism dashboard Project Detail activity feed MUST include GitHub commits and PRs when linked data exists.
- **FR-014**: System MUST log authentication failures, rate limit events, and sync completion with counts.

### Key Entities

- **GitHubRepo**: Represents a synced repository — org, name, full name, default branch, last synced timestamp.
- **GitHubCommit**: A single commit — SHA, repo, author (login + name), timestamp, message, branch.
- **GitHubPullRequest**: A PR — number, repo, title, body, state (open/closed/merged), author, opened at, closed/merged at, head branch.
- **GitHubJiraLink**: Association record — commit SHA or PR number → Jira ticket key.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After initial configuration, the first full sync completes and data is queryable within 5 minutes for an org with up to 50 repositories.
- **SC-002**: Incremental syncs complete within 30 seconds for a typical 15-minute activity window.
- **SC-003**: 100% of commits whose messages contain a standard Jira key pattern are correctly linked to the corresponding ticket.
- **SC-004**: GitHub nodes in the Prism dashboard transition from `inactive` to `active` state within one sync cycle of PAT configuration.
- **SC-005**: The system handles GitHub API rate limiting transparently — no data loss and no unhandled errors during a rate-limited sync.
- **SC-006**: Duplicate commit SHAs across multiple sync runs result in exactly one stored record (idempotent sync).

## Assumptions

- PAT authentication is sufficient for POC; GitHub App authentication is a future upgrade path.
- The PAT has `repo` scope (read access to repositories, commits, and PRs under the configured org).
- Jira ticket keys follow the standard format `[A-Z]+-\d+` (e.g., `SCRUM-42`, `DATA-7`). Non-standard formats are out of scope.
- `GITHUB_REPOS` when empty means "all repos visible to the PAT under the org"; a comma-separated list restricts to named repos.
- The existing sync worker (APScheduler, 15-minute interval) is reused; no new scheduler is introduced.
- The existing SQLite database and Alembic migration infrastructure are used for all new tables.
- Mobile/offline access to the dashboard is out of scope.
- GitHub Enterprise is out of scope; only `api.github.com` is targeted.
- The Prism dashboard frontend is updated in-place (no new files); existing node rendering logic is extended.
