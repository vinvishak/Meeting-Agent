# API Contract: GitHub PAT Client

**Feature**: 008-github-pat-client  
**Phase**: 1 — Design  
**Date**: 2026-05-02

All endpoints are registered under the existing `_register_routes()` function in `src/api/app.py` and prefixed with `/api/v1`. The existing `AuthMiddleware` applies.

---

## GET /api/v1/github/repos

**Purpose**: List all synced GitHub repositories with sync status.

**Auth**: Required (existing `AuthMiddleware`)

**Query parameters**: None

**Response 200**:
```json
{
  "repos": [
    {
      "id": "uuid-string",
      "full_name": "myorg/backend-service",
      "org": "myorg",
      "name": "backend-service",
      "default_branch": "main",
      "is_active": true,
      "last_synced_at": "2026-05-02T14:30:00Z",
      "commit_count": 142,
      "open_pr_count": 3
    }
  ],
  "total": 1,
  "synced_count": 1,
  "never_synced_count": 0
}
```

**Response fields**:
- `last_synced_at`: ISO8601 UTC or `null` if never synced
- `commit_count`: total commits stored for this repo
- `open_pr_count`: PRs with `state = "open"`
- `synced_count`: repos where `last_synced_at` is not null
- `never_synced_count`: repos where `last_synced_at` is null

---

## GET /api/v1/github/commits

**Purpose**: List recent commits, with optional filtering.

**Auth**: Required

**Query parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo` | string | `null` | Filter by `full_name` (e.g., `myorg/backend`) |
| `jira_key` | string | `null` | Filter by linked Jira ticket key (e.g., `SCRUM-42`) |
| `limit` | int | 50 | Max results (1–200) |
| `offset` | int | 0 | Pagination offset |

**Response 200**:
```json
{
  "commits": [
    {
      "sha": "abc123def456",
      "repo": "myorg/backend-service",
      "author_login": "jsmith",
      "author_name": "Jane Smith",
      "message": "Fix SCRUM-42: resolve null pointer in auth middleware",
      "committed_at": "2026-05-02T12:00:00Z",
      "url": "https://github.com/myorg/backend-service/commit/abc123",
      "jira_keys": ["SCRUM-42"]
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Response fields**:
- `jira_keys`: list of extracted Jira ticket keys linked to this commit (empty list if none)

---

## GET /api/v1/github/prs

**Purpose**: List pull requests, with optional filtering.

**Auth**: Required

**Query parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo` | string | `null` | Filter by `full_name` |
| `state` | string | `null` | Filter by state: `"open"`, `"closed"`, `"merged"` |
| `jira_key` | string | `null` | Filter by linked Jira ticket key |
| `limit` | int | 50 | Max results (1–200) |
| `offset` | int | 0 | Pagination offset |

**Response 200**:
```json
{
  "prs": [
    {
      "id": "uuid-string",
      "repo": "myorg/backend-service",
      "pr_number": 47,
      "title": "[SCRUM-42] Fix null pointer in auth middleware",
      "state": "merged",
      "author_login": "jsmith",
      "head_branch": "fix/scrum-42-auth",
      "opened_at": "2026-05-01T10:00:00Z",
      "merged_at": "2026-05-02T14:00:00Z",
      "closed_at": "2026-05-02T14:00:00Z",
      "url": "https://github.com/myorg/backend-service/pull/47",
      "jira_keys": ["SCRUM-42"]
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

## Route Registration

The three endpoints are served by `src/api/routes/github.py` and registered in `src/api/app.py`:

```python
("src.api.routes.github", "/api/v1", ["github"]),
```

Added to `_route_modules` list in `_register_routes()`, after the existing route entries.

---

## Frontend Integration

The frontend (`frontend/index.html`) uses the `/api/v1/github/repos` endpoint to determine GitHub sync status:

- If `total > 0` and `synced_count > 0`: GitHub nodes in the Org Overview tree switch from `status="inactive"` → `status="active"`. The `commit_count` aggregated across repos is displayed.
- If `total === 0` or `never_synced_count === total`: Nodes remain `inactive` with tooltip "GitHub sync pending".
- On fetch error: Nodes show `status="stale"`.

The Project Detail page uses `/api/v1/github/commits?limit=10` (filtered by Jira key if available) to populate the activity feed GitHub entries.
