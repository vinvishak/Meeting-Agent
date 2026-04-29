"""Quickstart wizard entry point.

Usage::

    # Interactive (default)
    python -m src.quickstart

    # Non-interactive / scripted
    python -m src.quickstart --non-interactive \\
        --jira-mcp-url http://... --jira-mcp-token TOKEN \\
        --copilot-mcp-url http://... --copilot-mcp-token TOKEN \\
        --anthropic-api-key sk-ant-...

    # Health check only (no writes, no migrations)
    python -m src.quickstart --check
"""

from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from pathlib import Path

from src.quickstart.config_schema import QUICKSTART_FIELDS, ConfigField
from src.quickstart.connectivity import (
    ConnectionCheckResult,
    check_anthropic,
    check_db,
    check_mcp,
)
from src.quickstart.db_migrator import run_migrations
from src.quickstart.env_writer import load_env, merge_env, print_summary, write_env
from src.quickstart.prompts import prompt_field, prompt_secret

_ENV_FILE = ".env"
_TICK = "✓"
_CROSS = "✗"


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.quickstart",
        description="Set up the Meeting Agent: configure credentials, validate connectivity, "
                    "and initialise the database.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts; all required values must be supplied as flags.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Health-check mode: probe services and report status without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing .env without prompting for confirmation.",
    )

    for f in QUICKSTART_FIELDS:
        flag = f"--{f.key.lower().replace('_', '-')}"
        kwargs: dict = {
            "dest": f.key,
            "default": None,
            "metavar": f.key,
            "help": f"{f.description} (example: {f.example})",
        }
        if f.key == "AUTO_APPLY_ENABLED":
            kwargs["action"] = "store_true"
            del kwargs["metavar"]
            del kwargs["default"]
        parser.add_argument(flag, **kwargs)

    return parser


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _run_connectivity_checks(values: dict[str, str]) -> list[ConnectionCheckResult]:
    results = [
        check_mcp("Jira MCP", values.get("JIRA_MCP_URL", ""), values.get("JIRA_MCP_TOKEN", "")),
        check_mcp("Copilot MCP", values.get("COPILOT_MCP_URL", ""), values.get("COPILOT_MCP_TOKEN", "")),
        check_anthropic(values.get("ANTHROPIC_API_KEY", "")),
        check_db(values.get("DATABASE_URL", "sqlite+aiosqlite:///./data/agent.db")),
    ]
    return results


def _print_check_report(results: list[ConnectionCheckResult]) -> None:
    col = max(len(r.service) for r in results) + 2
    print("\nConnectivity Check")
    print("─" * (col + 40))
    for r in results:
        icon = _TICK if r.ok else _CROSS
        print(f"  {icon} {r.service:<{col}}")
        if not r.ok and r.suggestion:
            print(f"    → {r.suggestion}")
    print("─" * (col + 40))


def _collect_values(fields: list[ConfigField], existing: dict[str, str]) -> dict[str, str]:
    """Prompt the user for each field, offering existing/default values."""
    values: dict[str, str] = {}
    for field in fields:
        current = existing.get(field.key)
        if field.secret:
            values[field.key] = prompt_secret(field, existing=current)
        else:
            values[field.key] = prompt_field(field, existing=current)
        # Re-prompt on validation failure
        while field.validator and (err := field.validator(values[field.key])):
            print(f"    ✗ {err}")
            if field.secret:
                values[field.key] = prompt_secret(field, existing=current)
            else:
                values[field.key] = prompt_field(field, existing=current)
    return values


# ---------------------------------------------------------------------------
# Interactive flow (US1 — T016)
# ---------------------------------------------------------------------------

def interactive_flow(args: Namespace, fields: list[ConfigField]) -> int:
    existing: dict[str, str] = {}
    env_exists = Path(_ENV_FILE).exists()

    if env_exists:
        existing = load_env(_ENV_FILE)
        if not args.force:
            ans = input(f"\nExisting {_ENV_FILE} detected. Re-use existing values as defaults? [Y/n]: ").strip().lower()
            if ans in ("n", "no"):
                existing = {}

    print("\n── Configuring credentials ──────────────────────────────────────")
    values = _collect_values(fields, existing)

    print_summary(fields, values)

    if not args.force:
        ans = input(f"\nWrite these values to {_ENV_FILE}? [Y/n]: ").strip().lower()
        if ans in ("n", "no"):
            print("Aborted — no files written.")
            return 1

    merged = merge_env(existing, values)
    write_env(_ENV_FILE, fields, merged)
    print(f"\n{_TICK} Written to {_ENV_FILE}")

    print()
    results = _run_connectivity_checks(merged)
    _print_check_report(results)
    all_ok = all(r.ok for r in results)
    if not all_ok:
        print("\n⚠  One or more connectivity checks failed. Fix the issues above and re-run.")
        return 1

    print("\n── Running database migrations ──────────────────────────────────")
    try:
        run_migrations(merged.get("DATABASE_URL", "sqlite+aiosqlite:///./data/agent.db"))
        print(f"{_TICK} Migrations applied.")
    except RuntimeError as exc:
        print(f"{_CROSS} Migration failed: {exc}")
        return 1

    print("""
Setup complete. Start the agent with:

    python -m src.main
""")
    return 0


# ---------------------------------------------------------------------------
# Non-interactive flow (US2 — T018)
# ---------------------------------------------------------------------------

def noninteractive_flow(args: Namespace, fields: list[ConfigField]) -> int:
    # Collect values from CLI flags; fall back to field defaults
    values: dict[str, str] = {}
    for field in fields:
        raw = getattr(args, field.key, None)
        if raw is None:
            values[field.key] = field.default or ""
        elif isinstance(raw, bool):
            values[field.key] = "true" if raw else "false"
        else:
            values[field.key] = raw

    # Validate required fields
    missing = [f.key for f in fields if f.required and not values.get(f.key)]
    if missing:
        print("Error: the following required flags are missing:")
        for key in missing:
            flag = f"--{key.lower().replace('_', '-')}"
            print(f"  {flag}")
        sys.exit(1)

    existing = load_env(_ENV_FILE) if Path(_ENV_FILE).exists() else {}
    merged = merge_env(existing, values)

    write_env(_ENV_FILE, fields, merged)
    print(f"{_TICK} Written to {_ENV_FILE}")

    results = _run_connectivity_checks(merged)
    _print_check_report(results)
    all_ok = all(r.ok for r in results)
    if not all_ok:
        sys.exit(1)

    try:
        run_migrations(merged.get("DATABASE_URL", "sqlite+aiosqlite:///./data/agent.db"))
        print(f"{_TICK} Migrations applied.")
    except RuntimeError as exc:
        print(f"{_CROSS} Migration failed: {exc}")
        sys.exit(1)

    print("\nSetup complete. Start the agent with:\n\n    python -m src.main\n")
    return 0


# ---------------------------------------------------------------------------
# Health check flow (US3 — T020)
# ---------------------------------------------------------------------------

def check_flow(args: Namespace, fields: list[ConfigField]) -> int:
    if not Path(_ENV_FILE).exists():
        print(f"Error: {_ENV_FILE} not found. Run the quickstart first.")
        sys.exit(1)

    values = load_env(_ENV_FILE)
    results = _run_connectivity_checks(values)
    _print_check_report(results)

    all_ok = all(r.ok for r in results)
    if all_ok:
        print("All services reachable.")
        return 0
    else:
        print("One or more services are unreachable.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.check:
        return check_flow(args, QUICKSTART_FIELDS)
    if args.non_interactive:
        return noninteractive_flow(args, QUICKSTART_FIELDS)
    return interactive_flow(args, QUICKSTART_FIELDS)


if __name__ == "__main__":
    sys.exit(main())
