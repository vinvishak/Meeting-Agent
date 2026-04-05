# Data Model: Add Quickstart Option

**Branch**: `002-add-quickstart-option` | **Date**: 2026-04-01

No persistent storage is introduced by this feature. All entities below are in-memory runtime structures used within a single quickstart invocation.

---

## ConfigField

Represents a single configurable environment variable.

| Field            | Type      | Description                                                    |
|------------------|-----------|----------------------------------------------------------------|
| `key`            | str       | Environment variable name (e.g. `JIRA_MCP_URL`)               |
| `description`    | str       | Human-readable description shown during interactive prompt     |
| `example`        | str       | Example value shown as hint                                    |
| `default`        | str\|None  | Default value; None means required (no default)                |
| `secret`         | bool      | If True, input is hidden and value is masked in summaries      |
| `required`       | bool      | If True, non-interactive mode fails if this field is absent    |
| `validator`      | callable\|None | Optional single-argument function that returns None on pass or an error string |

**State transitions**: Created at startup from `.env.example`; value populated by interactive prompts, CLI flags, or existing `.env` values.

---

## ConnectionCheckResult

Represents the outcome of a single connectivity probe.

| Field         | Type       | Description                                      |
|---------------|------------|--------------------------------------------------|
| `service`     | str        | Human-readable service name (e.g. `Jira MCP`)   |
| `ok`          | bool       | True if probe succeeded                          |
| `error`       | str\|None  | Error message if `ok` is False                   |
| `suggestion`  | str\|None  | Actionable fix hint shown when `ok` is False     |

---

## QuickstartSession

In-memory state for a single quickstart run.

| Field           | Type                          | Description                                             |
|-----------------|-------------------------------|---------------------------------------------------------|
| `interactive`   | bool                          | True if running in interactive (prompt-driven) mode     |
| `fields`        | list[ConfigField]             | Ordered list of all config fields                       |
| `values`        | dict[str, str]                | Collected values keyed by `ConfigField.key`             |
| `check_results` | list[ConnectionCheckResult]   | Results from the connectivity check phase               |
| `db_migrated`   | bool                          | True after database migrations succeed                  |
| `env_written`   | bool                          | True after `.env` file is successfully written          |

**Lifecycle**: Created at process start → fields populated → connectivity checked → `.env` written → migrations run → session complete.
