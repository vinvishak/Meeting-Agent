"""Connectivity probes for the quickstart wizard.

Each probe is a pure function that accepts explicit values (not ``get_settings()``)
so the probes are testable without a real ``.env`` file.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic
import httpx
from alembic import command as alembic_command
from alembic import config as alembic_config


@dataclass
class ConnectionCheckResult:
    """Outcome of a single connectivity probe."""

    service: str
    ok: bool
    error: str | None = None
    suggestion: str | None = None


def check_mcp(name: str, url: str, token: str) -> ConnectionCheckResult:
    """Probe an MCP server with a lightweight HTTP GET.

    A 2xx or 4xx response counts as reachable (the server responded).
    Only network-level errors (refused, timeout) count as failures.
    """
    try:
        httpx.get(url, timeout=5.0)
        return ConnectionCheckResult(service=name, ok=True)
    except httpx.ConnectError as exc:
        return ConnectionCheckResult(
            service=name,
            ok=False,
            error=str(exc),
            suggestion=f"Is the {name} server running at {url}?",
        )
    except httpx.TimeoutException:
        return ConnectionCheckResult(
            service=name,
            ok=False,
            error="Connection timed out after 5 s",
            suggestion=f"Check that {url} is reachable from this machine.",
        )
    except Exception as exc:  # noqa: BLE001
        return ConnectionCheckResult(service=name, ok=False, error=str(exc))


def check_anthropic(api_key: str) -> ConnectionCheckResult:
    """Validate an Anthropic API key by calling ``models.list()``."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        client.models.list()
        return ConnectionCheckResult(service="Claude API", ok=True)
    except anthropic.AuthenticationError as exc:
        return ConnectionCheckResult(
            service="Claude API",
            ok=False,
            error=str(exc),
            suggestion="Check that ANTHROPIC_API_KEY is correct and has not expired.",
        )
    except Exception as exc:  # noqa: BLE001
        return ConnectionCheckResult(service="Claude API", ok=False, error=str(exc))


def check_db(database_url: str) -> ConnectionCheckResult:
    """Verify the database is accessible by running ``alembic current``."""
    try:
        cfg = alembic_config.Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        alembic_command.current(cfg)
        return ConnectionCheckResult(service="Database", ok=True)
    except Exception as exc:  # noqa: BLE001
        return ConnectionCheckResult(
            service="Database",
            ok=False,
            error=str(exc),
            suggestion="Ensure DATABASE_URL is correct and the data/ directory is writable.",
        )
