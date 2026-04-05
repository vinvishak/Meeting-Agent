# Quickstart: Add Quickstart Option (Feature 002)

**Branch**: `002-add-quickstart-option` | **Date**: 2026-04-01

## How to Test This Feature

### Prerequisites

- Python 3.12+
- Dependencies installed (`uv sync` or `pip install -e ".[dev]"`)
- A `.env.example` file present in the repository root

### Test Scenario 1 — Interactive First-Time Setup

```bash
# Remove any existing .env to simulate a clean environment
rm -f .env

# Run the quickstart in interactive mode
python -m src.quickstart
```

Expected: prompts appear for each required value; after confirming the summary, `.env` is written and `alembic upgrade head` runs automatically.

### Test Scenario 2 — Non-Interactive Mode (CI/scripts)

```bash
python -m src.quickstart --non-interactive \
  --jira-mcp-url http://localhost:3000 \
  --jira-mcp-token test-token \
  --copilot-mcp-url http://localhost:3001 \
  --copilot-mcp-token test-token \
  --anthropic-api-key sk-ant-test
echo "Exit code: $?"
```

Expected: exits 0, `.env` written, migrations run, no prompts.

### Test Scenario 3 — Missing Required Flag (non-interactive)

```bash
python -m src.quickstart --non-interactive \
  --jira-mcp-url http://localhost:3000
echo "Exit code: $?"
```

Expected: exits 1, prints list of missing required flags.

### Test Scenario 4 — Health Check

```bash
python -m src.quickstart --check
```

Expected: reads existing `.env`, probes each service, prints pass/fail per service. No files written, no migrations run.

### Test Scenario 5 — Existing `.env` Detected

```bash
cp .env.example .env
python -m src.quickstart
```

Expected: quickstart detects `.env`, shows existing values masked, asks whether to keep or overwrite.

### Test Scenario 6 — Idempotency

```bash
python -m src.quickstart --non-interactive \
  --jira-mcp-url http://localhost:3000 \
  --jira-mcp-token test-token \
  --copilot-mcp-url http://localhost:3001 \
  --copilot-mcp-token test-token \
  --anthropic-api-key sk-ant-test \
  --force

# Run again
python -m src.quickstart --non-interactive \
  --jira-mcp-url http://localhost:3000 \
  --jira-mcp-token test-token \
  --copilot-mcp-url http://localhost:3001 \
  --copilot-mcp-token test-token \
  --anthropic-api-key sk-ant-test \
  --force

echo "Exit code: $?"
```

Expected: second run also exits 0; no database corruption; migrations are detected as already applied.

## Running Unit Tests

```bash
pytest tests/unit/quickstart/
```
