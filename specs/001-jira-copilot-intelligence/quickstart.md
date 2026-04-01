# Quickstart: Jira-Copilot Engineering Intelligence Agent

**Branch**: `001-jira-copilot-intelligence` | **Date**: 2026-03-31

## Prerequisites

- Python 3.12+
- Access to a Jira MCP Server instance (URL + credentials)
- Access to a Copilot MCP Server instance (URL + credentials)
- `uv` or `pip` for dependency management

## 1. Install Dependencies

```bash
pip install -r requirements.txt
# or with uv:
uv sync
```

Core dependencies: `anthropic`, `mcp`, `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic`, `rapidfuzz`, `apscheduler`, `pytest`, `pytest-asyncio`

## 2. Configure Environment

Copy the example config and fill in your MCP server details:

```bash
cp .env.example .env
```

Required environment variables:

```
# Jira MCP Server
JIRA_MCP_URL=...
JIRA_MCP_TOKEN=...

# Copilot MCP Server
COPILOT_MCP_URL=...
COPILOT_MCP_TOKEN=...

# Claude API (for NL queries and semantic matching)
ANTHROPIC_API_KEY=...

# Storage
DATABASE_URL=sqlite:///./data/agent.db

# Sync settings
SYNC_INTERVAL_MINUTES=15
STALE_THRESHOLD_DAYS=10

# Update suggestion thresholds
HIGH_CONFIDENCE_THRESHOLD=0.90
AUTO_APPLY_ENABLED=false
```

## 3. Initialize the Database

```bash
alembic upgrade head
```

## 4. Configure Status Mappings (Optional)

If your Jira boards use non-standard status names, add mappings before the first sync:

```bash
python -m src.storage.seed_status_mappings --board-id BOARD-1 \
  --mapping "Awaiting Review=review" \
  --mapping "Waiting on QA=review" \
  --mapping "Shipped=done"
```

## 5. Run Entity Resolution Setup

Before the first sync, resolve engineer identities across Jira and Copilot:

```bash
python -m src.ingestion.normalizer --resolve-engineers
```

Review any unresolved identities printed to stdout and add manual mappings as prompted.

## 6. Start the Service

**Option A — Development (API + worker together)**:

```bash
python -m src.main
```

This starts the FastAPI server on `http://localhost:8000` and the background sync worker in the same process.

**Option B — Production (separate processes)**:

```bash
# Terminal 1: API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Background sync worker
python -m src.workers.sync_worker
```

## 7. Trigger a Manual Sync

To verify connectivity before the first scheduled sync:

```bash
python -m src.workers.sync_worker --run-once
```

Check the output for any MCP connection errors or entity resolution warnings.

## 8. Open the Dashboard

Navigate to `http://localhost:8000` in your browser. Log in with your organization credentials. You should see the team work status dashboard populated after the first sync completes.

## 9. Run Tests

```bash
# Unit tests only (no MCP server required)
pytest tests/unit/

# Integration tests (requires MCP server access or recorded fixtures)
pytest tests/integration/

# Full suite
pytest
```

## Troubleshooting

**Sync not running**: Check `SYNC_INTERVAL_MINUTES` is set and the worker process is running. Check the sync status endpoint at `GET /api/v1/sync/status`.

**Low ticket match rate**: After a sync, check unresolved transcript mentions at `GET /api/v1/suggestions?approval_state=pending` and look for entries with `match_type=unresolved`. Add additional status mappings or adjust entity resolution.

**Dashboard data stale**: The `data_freshness` field on every API response shows when data was last synced. If it exceeds 20 minutes, check the worker process logs for MCP server errors.
