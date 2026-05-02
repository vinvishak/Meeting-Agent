# Contract: Jira REST API Interface

**Branch**: `005-jira-rest-api-client` | **Date**: 2026-04-28

This document defines the contract between `JiraClient` (the new direct REST client) and the rest of the application. The public interface is identical to the previous `JiraMCPClient` — only the internal transport changes.

---

## Client Interface

### Instantiation

```
JiraClient()
  Reads: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN from settings
  Auth:  HTTP Basic Auth (email:token)
  Usage: async with JiraClient() as client:
```

### Methods

#### `list_issues(project_key: str, max_results: int = 500) -> list[JiraIssue]`

Fetch all issues for a Jira project using JQL.

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_key` | `str` | Jira project key, e.g. `PROJ` |
| `max_results` | `int` | Maximum issues to fetch (default 500, fetched in pages of 100) |

**Returns**: List of `JiraIssue` objects. Empty list if project has no issues.
**Errors**: Raises `RuntimeError` after 3 failed attempts with backoff.

---

#### `get_issue(jira_id: str) -> JiraIssue | None`

Fetch a single issue by key.

| Parameter | Type | Description |
|-----------|------|-------------|
| `jira_id` | `str` | Issue key, e.g. `PROJ-123` |

**Returns**: `JiraIssue` or `None` if not found / not accessible.

---

#### `list_sprints(board_id: str) -> list[JiraSprint]`

Fetch all sprints for a board.

| Parameter | Type | Description |
|-----------|------|-------------|
| `board_id` | `str` | Jira board ID |

**Returns**: List of `JiraSprint` objects. Empty list if no sprints exist.

---

#### `get_comments(jira_id: str, max_results: int = 50) -> list[JiraComment]`

Fetch comments for an issue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `jira_id` | `str` | Issue key |
| `max_results` | `int` | Maximum comments to return (default 50) |

**Returns**: List of `JiraComment` objects in ascending chronological order.

---

#### `update_issue(jira_id: str, fields: dict) -> bool`

Apply field updates to a Jira issue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `jira_id` | `str` | Issue key |
| `fields` | `dict` | Jira field payload, e.g. `{"status": {"name": "Done"}}` |

**Returns**: `True` on success, `False` on failure (error is logged, no exception raised).

---

## Jira REST API Endpoints Called

| Method | Endpoint | Used by |
|--------|----------|---------|
| `GET` | `/rest/api/3/search` | `list_issues` |
| `GET` | `/rest/api/3/issue/{key}` | `get_issue` |
| `GET` | `/rest/agile/1.0/board/{id}/sprint` | `list_sprints` |
| `GET` | `/rest/api/3/issue/{key}/comment` | `get_comments` |
| `PUT` | `/rest/api/3/issue/{key}` | `update_issue` |

---

## Error Behaviour

| Condition | Behaviour |
|-----------|-----------|
| HTTP 401 (bad credentials) | Logged as ERROR, raises `RuntimeError` immediately (no retry) |
| HTTP 403 (no permission) | Logged as WARNING, returns `None` or `False` |
| HTTP 404 (not found) | Returns `None` or empty list (no error raised) |
| HTTP 429 (rate limited) | Retried up to 3 times with exponential backoff |
| HTTP 5xx (server error) | Retried up to 3 times with exponential backoff |
| Network timeout | Retried up to 3 times with exponential backoff |
