# Contract: Quickstart CLI Interface

**Branch**: `002-add-quickstart-option` | **Date**: 2026-04-01

## Entry Point

```
python -m src.quickstart [OPTIONS]
```

---

## Modes

### Interactive Mode (default — no flags)

```
python -m src.quickstart
```

Prompts for each required configuration value. Detects and offers to reuse an existing `.env`.

### Non-Interactive Mode

```
python -m src.quickstart --non-interactive \
  --jira-mcp-url <URL> \
  --jira-mcp-token <TOKEN> \
  --copilot-mcp-url <URL> \
  --copilot-mcp-token <TOKEN> \
  --anthropic-api-key <KEY> \
  [--database-url <URL>] \
  [--sync-interval-minutes <N>] \
  [--stale-threshold-days <N>] \
  [--jira-project-keys <KEYS>] \
  [--high-confidence-threshold <FLOAT>] \
  [--auto-apply-enabled]
```

All required flags must be present; missing flags cause exit code 1 with a message listing which flags are absent.

### Health Check Mode

```
python -m src.quickstart --check
```

Reads existing `.env`, probes each configured service, and prints a pass/fail report. Does not write any files or run migrations. Cannot be combined with `--non-interactive`.

---

## Flags Reference

| Flag                          | Required in `--non-interactive` | Description                                         |
|-------------------------------|----------------------------------|-----------------------------------------------------|
| `--non-interactive`           | —                                | Disable prompts; all values must be supplied as flags |
| `--check`                     | —                                | Health check mode only                              |
| `--jira-mcp-url`              | Yes                              | Jira MCP server base URL                            |
| `--jira-mcp-token`            | Yes                              | Jira MCP server auth token                          |
| `--copilot-mcp-url`           | Yes                              | Copilot MCP server base URL                         |
| `--copilot-mcp-token`         | Yes                              | Copilot MCP server auth token                       |
| `--anthropic-api-key`         | Yes                              | Anthropic API key                                   |
| `--database-url`              | No                               | SQLAlchemy database URL (default: `sqlite+aiosqlite:///./data/agent.db`) |
| `--sync-interval-minutes`     | No                               | Sync interval in minutes (default: 15)              |
| `--stale-threshold-days`      | No                               | Stale ticket threshold in days (default: 10)        |
| `--jira-project-keys`         | No                               | Comma-separated Jira project keys (default: "")     |
| `--high-confidence-threshold` | No                               | Confidence threshold 0–1 (default: 0.90)            |
| `--auto-apply-enabled`        | No                               | Enable auto-apply of suggestions (default: false)   |
| `--force`                     | No                               | Overwrite existing `.env` without prompting          |
| `--help`                      | —                                | Print usage and exit                                |

---

## Exit Codes

| Code | Meaning                                                  |
|------|----------------------------------------------------------|
| `0`  | Setup completed successfully                             |
| `1`  | Setup failed (missing flags, connectivity error, migration error) |
| `2`  | Usage error (invalid flag, conflicting modes)            |

---

## Standard Output Format

### Interactive Summary (before writing `.env`)

```
Configuration Summary
─────────────────────────────────────────
JIRA_MCP_URL         http://jira.example.com
JIRA_MCP_TOKEN       ****ab12
COPILOT_MCP_URL      http://copilot.example.com
COPILOT_MCP_TOKEN    ****cd34
ANTHROPIC_API_KEY    ****ef56
DATABASE_URL         sqlite+aiosqlite:///./data/agent.db
...
─────────────────────────────────────────
Write these values to .env? [Y/n]:
```

### Connectivity Check Report

```
Connectivity Check
──────────────────────────────────────
✓ Jira MCP         http://jira.example.com
✓ Copilot MCP      http://copilot.example.com
✓ Claude API       (key validated)
✓ Database         sqlite+aiosqlite:///./data/agent.db
──────────────────────────────────────
All services reachable.
```

On failure:
```
✗ Jira MCP         http://jira.example.com
  → Connection refused. Is the Jira MCP server running?
```

### Success Message

```
Setup complete. Start the agent with:

    python -m src.main
```
