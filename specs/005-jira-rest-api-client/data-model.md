# Data Model: Jira Direct REST API Client

**Branch**: `005-jira-rest-api-client` | **Date**: 2026-04-28

## Overview

No database schema changes. All existing SQLAlchemy models and Alembic migrations remain untouched. This feature only changes how Jira data is *fetched* — not how it is stored.

The Pydantic response models below are unchanged from the existing implementation. They are documented here for reference.

---

## Response Models (unchanged)

### JiraIssue

Represents a single Jira ticket returned from the API.

| Field | Type | Source (Jira field) | Notes |
|-------|------|---------------------|-------|
| `jira_id` | `str` | `key` | e.g. `PROJ-123` |
| `summary` | `str` | `fields.summary` | |
| `description` | `str \| None` | `fields.description` | |
| `jira_status` | `str` | `fields.status.name` | |
| `assignee_email` | `str \| None` | `fields.assignee.emailAddress` | |
| `assignee_display_name` | `str \| None` | `fields.assignee.displayName` | |
| `assignee_username` | `str \| None` | `fields.assignee.accountId` | |
| `priority` | `str \| None` | `fields.priority.name` | |
| `story_points` | `float \| None` | `fields.customfield_10016` | |
| `labels` | `list[str]` | `fields.labels` | |
| `linked_issue_ids` | `list[str]` | `fields.issuelinks` | |
| `created_at` | `datetime` | `fields.created` | ISO 8601 |
| `updated_at` | `datetime` | `fields.updated` | ISO 8601 |
| `due_date` | `date \| None` | `fields.duedate` | |
| `is_blocked` | `bool` | `fields.flagged` or status contains "blocked" | |
| `sprint_jira_id` | `str \| None` | `fields.sprint.id` | |
| `board_id` | `str \| None` | `fields.board_id` | |

### JiraSprint

Represents a sprint on a Jira board.

| Field | Type | Source (Jira field) | Notes |
|-------|------|---------------------|-------|
| `jira_sprint_id` | `str` | `id` | |
| `name` | `str` | `name` | |
| `state` | `str` | `state` | `active \| future \| closed` |
| `board_id` | `str` | `originBoardId` | |
| `start_date` | `date \| None` | `startDate` | |
| `end_date` | `date \| None` | `endDate` | |

### JiraComment

Represents a comment on a Jira issue.

| Field | Type | Source (Jira field) | Notes |
|-------|------|---------------------|-------|
| `id` | `str` | `id` | |
| `issue_jira_id` | `str` | (passed in, not in payload) | |
| `author_display_name` | `str` | `author.displayName` | |
| `author_email` | `str \| None` | `author.emailAddress` | |
| `body` | `str` | `body` | |
| `created_at` | `datetime` | `created` | ISO 8601 |

---

## Configuration Changes

### Removed settings

| Setting | Was used for |
|---------|-------------|
| `JIRA_MCP_URL` | MCP server SSE endpoint |
| `JIRA_MCP_TOKEN` | Bearer token for MCP server |

### Added settings

| Setting | Type | Example | Description |
|---------|------|---------|-------------|
| `JIRA_BASE_URL` | `str` | `https://yourcompany.atlassian.net` | Jira Cloud workspace root URL |
| `JIRA_EMAIL` | `str` | `you@yourcompany.com` | Atlassian account email |
| `JIRA_API_TOKEN` | `str` | `ATATT3x...` | Atlassian API token |
