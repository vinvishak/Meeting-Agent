# Research: Add Quickstart Option

**Branch**: `002-add-quickstart-option` | **Date**: 2026-04-01

## Decision Log

### CLI Argument Parsing

**Decision**: Use stdlib `argparse` — no new dependency.

**Rationale**: The quickstart command has a small, fixed set of flags. `argparse` covers all requirements (positional args, flags, `--help`) without adding a dependency. `click` provides marginally better UX but would be an unjustified addition under Constitution Principle V (YAGNI).

**Alternatives considered**:
- `click` — nicer API but not justified for a single command
- `typer` — wraps click, same objection

---

### Connectivity Checks for MCP Servers

**Decision**: Use `httpx` (sync) to send a lightweight HTTP `GET /` or `/health` probe to each MCP URL with a 5-second timeout.

**Rationale**: `httpx` is already a transitive dependency (pulled in via `fastapi[standard]` and the `anthropic` SDK). No new dependency. A simple HTTP probe is sufficient to verify reachability; full MCP session negotiation would add complexity without adding confidence.

**Alternatives considered**:
- Full MCP `ClientSession` handshake — overkill for a connectivity check, requires async event loop setup
- `urllib` (stdlib) — more verbose, no timeout context manager convenience

---

### Claude API Key Validation

**Decision**: Instantiate `anthropic.Anthropic(api_key=value)` and call `client.models.list()` (lightweight call) to confirm the key is valid and quota exists.

**Rationale**: The `anthropic` SDK is already a required dependency. `models.list()` is the cheapest call that confirms both key validity and quota availability.

**Alternatives considered**:
- Raw `httpx` to the Anthropic API — duplicates what the SDK already provides
- No API key validation — fails SC-002 (setup must complete without errors given valid credentials)

---

### `.env` File Read/Write/Merge

**Decision**: Read existing `.env.example` as the canonical schema; parse existing `.env` with a simple line-by-line parser (no third-party library); write output with the same format.

**Rationale**: `python-dotenv` is not a current dependency. A 30-line parser for `KEY=VALUE` format is sufficient and avoids adding a dependency. The canonical field list comes from `.env.example`, ensuring the quickstart stays in sync with what the application expects.

**Alternatives considered**:
- `python-dotenv` — would simplify parsing but adds a dependency not otherwise needed; rejected under Principle V

---

### Alembic Migration Invocation

**Decision**: Call Alembic programmatically via its Python API (`alembic.config.Config` + `alembic.command.upgrade`) rather than subprocess.

**Rationale**: `alembic` is already a required dependency. The Python API gives structured error handling (exceptions vs. subprocess return codes) and avoids shell quoting issues.

**Alternatives considered**:
- `subprocess.run(["alembic", "upgrade", "head"])` — works but loses structured error handling; also requires `alembic` to be on `$PATH`

---

### Secret Masking

**Decision**: Use `getpass.getpass()` for secret fields (tokens, API keys) during interactive prompts. Display masked values as `****<last4>` when showing summaries.

**Rationale**: `getpass` is stdlib. The `****<last4>` pattern is familiar and sufficient to let users verify they entered the right secret without exposing it.

**Alternatives considered**:
- Third-party prompt libraries (`prompt_toolkit`) — unjustified under Principle V
