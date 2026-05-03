# Tasks: GitHub PAT Client

**Input**: Design documents from `/specs/008-github-pat-client/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story — each story is independently implementable and testable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[US1/US2/US3]**: Which user story this belongs to

---

## Phase 1: Setup

**Purpose**: Extend existing config and module structure for GitHub integration. No new packages required — all dependencies already present.

- [X] T001 Add `github_pat`, `github_org`, `github_repos` fields to `src/config.py` (str, default `""`)
- [X] T00Create empty module `src/ingestion/github_client.py` with module docstring and imports (`httpx`, `re`, `pydantic`, `src.config`, `src.logging_config`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data layer that ALL three user stories depend on — ORM models + Alembic migration. Must be complete before any story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T00Add `GitHubRepo` ORM model to `src/storage/models.py`: fields `id`, `org`, `name`, `full_name` (UNIQUE), `default_branch`, `is_active`, `last_synced_at` (nullable), `created_at`; relationships to `GitHubCommit` and `GitHubPullRequest`
- [X] T00Add `GitHubCommit` ORM model to `src/storage/models.py`: fields `id`, `repo_id` (FK→github_repos), `sha` (UNIQUE), `message`, `author_login`, `author_name`, `author_email`, `committed_at` (indexed), `branch`, `url`, `created_at`; relationship to `GitHubRepo` and `GitHubJiraLink`
- [X] T00Add `GitHubPullRequest` ORM model to `src/storage/models.py`: fields `id`, `repo_id` (FK→github_repos), `pr_number`, `title`, `body`, `state`, `author_login`, `head_branch`, `base_branch`, `opened_at` (indexed), `closed_at`, `merged_at`, `url`, `last_synced_at`, `created_at`; UNIQUE constraint on `(repo_id, pr_number)`; relationship to `GitHubRepo` and `GitHubJiraLink`
- [X] T00Add `GitHubJiraLink` ORM model to `src/storage/models.py`: fields `id`, `source_type` (`"commit"` or `"pr"`), `commit_sha` (nullable, indexed), `pr_id` (FK→github_pull_requests, nullable, indexed), `jira_key` (indexed), `ticket_id` (FK→tickets, nullable, indexed), `created_at`; relationship to `GitHubPullRequest` and `Ticket`
- [X] T00Create Alembic migration `src/storage/migrations/versions/002_github_schema.py` with `down_revision = "001_initial_schema"`: creates tables `github_repos`, `github_commits`, `github_pull_requests`, `github_jira_links` with all columns, FK constraints, unique constraints, and indexes from data-model.md; implement both `upgrade()` and `downgrade()`
- [X] T00Apply migration by running `uv run alembic upgrade head` and verify all 4 tables exist in `data/agent.db`

**Checkpoint**: Migration applied, all 4 ORM models importable. User story implementation can now begin.

---

## Phase 3: User Story 1 — GitHub Commit & PR Sync (Priority: P1) 🎯 MVP

**Goal**: Fetch commits and PRs from GitHub via PAT, store them locally, expose repos endpoint.

**Independent Test**: After `uv run python -m src.workers.sync_worker --run-once`, `GET /api/v1/github/repos` returns at least one repo with `last_synced_at` set and non-zero `commit_count`.

### Implementation for User Story 1

- [X] T00[US1] Implement Pydantic response models in `src/ingestion/github_client.py`: `GitHubRepoInfo` (full_name, org, name, default_branch), `GitHubCommitInfo` (sha, message, author_login, author_name, author_email, committed_at, branch, url), `GitHubPRInfo` (pr_number, title, body, state, author_login, head_branch, base_branch, opened_at, closed_at, merged_at, url)
- [X] T01[US1] Implement `GitHubClient` async context manager in `src/ingestion/github_client.py`: `__aenter__`/`__aexit__` using `httpx.AsyncClient`; base URL `https://api.github.com`; headers `Authorization: Bearer {pat}`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`; rate limit handling via `X-RateLimit-Remaining` + `X-RateLimit-Reset` headers (sleep until reset if remaining == 0); exponential backoff retry on 429/500/502/503/504 (3 retries, 2^attempt seconds, same pattern as `src/ingestion/jira_client.py`)
- [X] T01[US1] Implement `GitHubClient.list_repos()` in `src/ingestion/github_client.py`: `GET /orgs/{org}/repos?type=all&per_page=100`; handle pagination via `Link: <url>; rel="next"` response header; returns `list[GitHubRepoInfo]`; log count on completion
- [X] T01[US1] Implement `GitHubClient.list_commits()` in `src/ingestion/github_client.py`: `GET /repos/{full_name}/commits?per_page=100&since={iso8601}`; `since` param omitted on first sync (fetches all); handle pagination; returns `list[GitHubCommitInfo]`; log count per repo
- [X] T01[US1] Implement `GitHubClient.list_prs()` in `src/ingestion/github_client.py`: `GET /repos/{full_name}/pulls?state=all&sort=updated&direction=desc&per_page=100`; stop pagination when `updated_at < since` (for incremental sync); returns `list[GitHubPRInfo]`; log count per repo
- [X] T01[US1] Add `GitHubRepository` class to `src/storage/repository.py` with methods: `upsert_repo(session, org, name, full_name, default_branch) -> GitHubRepo`; `upsert_commit(session, repo_id, sha, message, author_login, author_name, author_email, committed_at, branch, url) -> GitHubCommit`; `upsert_pr(session, repo_id, pr_number, title, body, state, author_login, head_branch, base_branch, opened_at, closed_at, merged_at, url) -> GitHubPullRequest`; `update_repo_synced_at(session, repo_id, synced_at)` — all use INSERT OR REPLACE / merge-on-conflict pattern consistent with existing repository methods
- [X] T01[US1] Implement `_sync_github()` async function in `src/workers/sync_worker.py`: skip silently if `settings.github_pat` is empty (log debug); discover repos via `list_repos()` (or use `settings.github_repos` comma-separated list if set); for each repo call `upsert_repo()`, then `list_commits(since=repo.last_synced_at)` + `upsert_commit()` for each, then `list_prs(since=repo.last_synced_at)` + `upsert_pr()` for each; call `update_repo_synced_at()` after each repo succeeds; log per-repo and totals
- [X] T01[US1] Call `_sync_github()` from `run_sync_cycle()` in `src/workers/sync_worker.py`: add `await _sync_github()` after `await _recalculate_velocity(project_keys)` line, wrapped in try/except that logs warning and continues (GitHub failure must not abort Jira sync)
- [X] T01[US1] Create `src/api/routes/github.py` with `router = APIRouter()` and implement `GET /github/repos` endpoint: query all `GitHubRepo` rows; for each compute `commit_count` (COUNT github_commits WHERE repo_id) and `open_pr_count` (COUNT github_pull_requests WHERE repo_id AND state="open"); return response matching `contracts/api-contract.md` shape including `total`, `synced_count`, `never_synced_count`
- [X] T01[US1] Register github route in `src/api/app.py`: add `("src.api.routes.github", "/api/v1", ["github"])` to `_route_modules` list in `_register_routes()`

**Checkpoint**: Run `uv run python -m src.workers.sync_worker --run-once` → `GET /api/v1/github/repos` returns real repos. US1 complete.

---

## Phase 4: User Story 2 — Jira Ticket Linking (Priority: P2)

**Goal**: Extract Jira ticket keys from commit messages and PR titles/bodies; store links; expose filtered commits and PRs endpoints.

**Independent Test**: After sync, `GET /api/v1/github/commits?jira_key=SCRUM-42` returns commits whose messages contain `SCRUM-42`.

### Implementation for User Story 2

- [X] T01[US2] Add `extract_jira_keys(text: str) -> list[str]` function to `src/ingestion/github_client.py`: regex `r'\b[A-Z][A-Z0-9]+-\d+\b'`; apply to text, return deduplicated list; handles empty/None input (return `[]`)
- [X] T02[US2] Add `upsert_jira_link(session, source_type, commit_sha, pr_id, jira_key) -> GitHubJiraLink` method to `GitHubRepository` in `src/storage/repository.py`: upsert on `(source_type, commit_sha or pr_id, jira_key)`; look up `ticket_id` by matching `jira_key` against `tickets.jira_id` (forward reference set to null if not found)
- [X] T02[US2] Add `resolve_forward_jira_links(session)` method to `GitHubRepository` in `src/storage/repository.py`: query `GitHubJiraLink` rows where `ticket_id IS NULL`; for each, look up `Ticket` by `jira_id = jira_key`; update `ticket_id` if found; log count of resolved links
- [X] T02[US2] Extend `_sync_github()` in `src/workers/sync_worker.py` to call `extract_jira_keys()` on each commit's message and each PR's title + body[:2000]; call `upsert_jira_link()` for each extracted key; call `resolve_forward_jira_links()` after all repos synced
- [X] T02[US2] Implement `GET /github/commits` endpoint in `src/api/routes/github.py`: query params `repo` (optional `full_name` filter), `jira_key` (optional, joins through `github_jira_links`), `limit` (default 50, max 200), `offset` (default 0); return commits with `jira_keys` list field (aggregated from links); response shape matches `contracts/api-contract.md`
- [X] T02[US2] Implement `GET /github/prs` endpoint in `src/api/routes/github.py`: query params `repo`, `state`, `jira_key`, `limit`, `offset`; return PRs with `jira_keys` list; response shape matches `contracts/api-contract.md`

**Checkpoint**: `GET /api/v1/github/commits?jira_key=SCRUM-42` filters correctly. `GET /api/v1/github/prs?state=open` returns open PRs. US2 complete.

---

## Phase 5: User Story 3 — Prism Dashboard GitHub Nodes (Priority: P3)

**Goal**: Replace inactive gray GitHub nodes in the Prism dashboard with live status derived from synced data.

**Independent Test**: After sync, GitHub tree nodes in the Org Overview tab show green `active` badge with a commit count; before sync they show gray `inactive`.

### Implementation for User Story 3

- [X] T02[US3] Add `fetchGitHubStatus()` async function to `frontend/index.html` inline `<script>`: `GET /api/v1/github/repos`; if fetch fails → set all `[data-type="github"]` nodes to `status="stale"`; if `synced_count > 0` → set to `status="active"`, populate `data-commit-count` attribute with total `commit_count` sum across repos; if `synced_count === 0` → leave `status="inactive"` with tooltip text "GitHub sync pending"
- [X] T02[US3] Update GitHub node rendering in `frontend/index.html`: extend the existing tree node render logic to read `data-status` and `data-commit-count`; `status="active"` → green dot + `"{count} commits"` label; `status="stale"` → orange dot + `"Data may be outdated"` label; `status="inactive"` → gray dot + `"Sync pending"` label (update CSS classes as needed to match existing node style patterns)
- [X] T02[US3] Call `fetchGitHubStatus()` from `frontend/index.html`: invoke on page load (after DOM ready) and on navigation to the "Org Overview" tab; do not block page render — call asynchronously
- [X] T02[US3] Update Project Detail activity feed in `frontend/index.html`: when a project detail panel opens, call `GET /api/v1/github/commits?limit=10` (filtered by `jira_key` if the project has a known Jira key); prepend fetched commits to the activity feed list as GitHub entries with author, timestamp, message snippet, and link; show "No GitHub activity" if empty list

**Checkpoint**: Open `http://localhost:8000/app`, navigate to Org Overview — GitHub nodes show live status. US3 complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Unit tests for deterministic logic, code validation, quickstart walkthrough.

- [X] T02[P] Create `tests/unit/ingestion/test_github_client.py` with unit tests for `extract_jira_keys()`: test standard key extraction (`SCRUM-42`, `DATA-7`), multiple keys in one string, no keys, empty input, non-standard patterns that should NOT match (`v1.2-3`), PR body truncation at 2000 chars
- [X] T03[P] Add unit tests for pagination termination logic in `tests/unit/ingestion/test_github_client.py`: verify `list_prs()` stops when `updated_at < since` (mock `httpx` responses)
- [X] T03Run `uv run ruff check .` and fix any linting errors introduced in new files
- [X] T03Walk through all 7 scenarios in `specs/008-github-pat-client/quickstart.md` and confirm expected outputs

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — core sync pipeline
- **Phase 4 (US2)**: Depends on Phase 3 being complete (needs stored commits/PRs to link)
- **Phase 5 (US3)**: Depends on Phase 3 being complete (needs `/github/repos` endpoint)
- **Phase 6 (Polish)**: Depends on all stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no story dependencies
- **US2 (P2)**: After US1 — extends stored commit/PR data with link extraction
- **US3 (P3)**: After US1 — reads repos endpoint; can overlap with US2

### Within Each User Story

- T009–T013 (client models + methods): T009 first (Pydantic models), then T010–T013 can be written in sequence
- T014 (repository): After T009 (needs Pydantic types for type hints)
- T015 (sync function): After T010–T014
- T016 (wire to run_sync_cycle): After T015
- T017 (route): After Phase 2 (needs ORM models)
- T018 (register route): After T017

---

## Parallel Opportunities

```bash
# Phase 2 — all 4 model additions are to the same file, do sequentially:
T003 → T004 → T005 → T006 → T007 → T008

# Phase 3 — client methods can be written in sequence after context manager:
T009 → T010 → T011 → T012 → T013 (sequential, same file)
T014 can be written in parallel with T011-T013 (different file: repository.py)

# Phase 4 — after US1 complete:
T019+T020 can run in parallel (extract_jira_keys in github_client.py + upsert in repository.py)
T023+T024 can run in parallel (different endpoints, same file, no dependency between them)

# Phase 5 — all 4 tasks are in the same file (index.html), run sequentially:
T025 → T026 → T027 → T028

# Phase 6 — T029 and T030 can run in parallel (same file, but independent test functions):
T029 [P] T030 [P]
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1: Config + module skeleton (T001–T002)
2. Phase 2: ORM models + migration (T003–T008)
3. Phase 3: GitHubClient + sync + repos endpoint (T009–T018)
4. **VALIDATE**: `uv run python -m src.workers.sync_worker --run-once` → repos populated → API returns data
5. **STOP** here for demo if needed — GitHub data is live in the system

### Incremental Delivery

1. US1 complete → data flows from GitHub into DB, repos endpoint live
2. US2 complete → Jira keys linked, commits/PRs endpoints live
3. US3 complete → Prism dashboard shows live GitHub activity
4. Polish → tests green, linting clean

---

## Notes

- No new Python packages needed — all dependencies already in `pyproject.toml`
- `github_client.py` mirrors `jira_client.py` exactly — use it as a reference
- Alembic migration must have `down_revision = "001_initial_schema"` — do not change existing migration
- Frontend changes are all inline in `frontend/index.html` — no new JS files
- If `GITHUB_PAT` is empty, sync silently skips GitHub — Jira sync is unaffected
