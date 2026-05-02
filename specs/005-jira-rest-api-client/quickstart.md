# Quickstart: Jira Direct REST API Client

**Branch**: `005-jira-rest-api-client` | **Date**: 2026-04-28

## What Changed

The application no longer requires a Jira MCP server. It connects directly to your Jira Cloud workspace using an API token.

## 1. Get Your Jira Credentials

You need three things:

| Setting | Where to get it |
|---------|----------------|
| `JIRA_BASE_URL` | Your Jira URL in the browser, e.g. `https://yourcompany.atlassian.net` |
| `JIRA_EMAIL` | Your Atlassian account email address |
| `JIRA_API_TOKEN` | Create one at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |

## 2. Configure `.env`

Copy the example and fill in your Jira details:

```bash
cp .env.example .env
```

Update the Jira section in `.env`:

```
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-api-token-here
JIRA_PROJECT_KEYS=PROJ,INFRA
```

Remove or ignore any old `JIRA_MCP_URL` / `JIRA_MCP_TOKEN` entries — they are no longer used.

## 3. Install Dependencies

```bash
uv sync
```

The `respx` package is added as a dev dependency for testing. No new runtime dependencies are introduced.

## 4. Verify the Connection

Run the sync worker once to confirm it can reach your Jira workspace:

```bash
python -m src.workers.sync_worker --run-once
```

Expected output on success:
```
INFO  Sync cycle started
INFO  Fetched N issues from project PROJ
INFO  Sync cycle completed in X.Xs
```

If you see an authentication error, double-check `JIRA_EMAIL` and `JIRA_API_TOKEN`.

## 5. Start the Application

```bash
python -m src.main
```

The FastAPI server starts on `http://localhost:8000` with the background sync worker running in the same process.

## 6. Run Tests

```bash
pytest tests/unit/
```

All 108 existing tests plus the new Jira client unit tests should pass.

## Troubleshooting

**401 Unauthorized**: Your `JIRA_API_TOKEN` is invalid or expired. Generate a new one at id.atlassian.com.

**404 on sprints**: The board ID in `JIRA_PROJECT_KEYS` may be incorrect. Board IDs are numeric and found in the Jira board URL: `.../jira/software/projects/PROJ/boards/123` — the board ID is `123`.

**Empty ticket list**: Confirm the project key in `JIRA_PROJECT_KEYS` exactly matches what appears in Jira (e.g. `PROJ`, not `proj`).
