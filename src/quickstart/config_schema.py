"""ConfigField dataclass and canonical list of quickstart fields.

The field list is the single source of truth for what variables the quickstart
wizard collects. It mirrors the variables in ``.env.example``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ConfigField:
    """Describes one environment variable collected by the quickstart wizard."""

    key: str
    description: str
    example: str
    default: str | None = None
    secret: bool = False
    required: bool = True
    validator: Callable[[str], str | None] | None = None


def _url_validator(value: str) -> str | None:
    if not value.startswith(("http://", "https://")):
        return "Must be a URL starting with http:// or https://"
    return None


def _float_validator(value: str) -> str | None:
    try:
        v = float(value)
    except ValueError:
        return "Must be a number between 0 and 1"
    if not (0.0 <= v <= 1.0):
        return "Must be between 0.0 and 1.0"
    return None


def _int_validator(value: str) -> str | None:
    try:
        int(value)
    except ValueError:
        return "Must be a positive integer"
    return None


#: Ordered list of all fields the quickstart wizard collects, matching .env.example.
QUICKSTART_FIELDS: list[ConfigField] = [
    ConfigField(
        key="JIRA_MCP_URL",
        description="Jira MCP server base URL",
        example="http://localhost:3000",
        validator=_url_validator,
    ),
    ConfigField(
        key="JIRA_MCP_TOKEN",
        description="Jira MCP server authentication token",
        example="your-jira-mcp-token",
        secret=True,
    ),
    ConfigField(
        key="COPILOT_MCP_URL",
        description="Copilot MCP server base URL",
        example="http://localhost:3001",
        validator=_url_validator,
    ),
    ConfigField(
        key="COPILOT_MCP_TOKEN",
        description="Copilot MCP server authentication token",
        example="your-copilot-mcp-token",
        secret=True,
    ),
    ConfigField(
        key="ANTHROPIC_API_KEY",
        description="Anthropic API key (used for NL queries and semantic matching)",
        example="sk-ant-...",
        secret=True,
    ),
    ConfigField(
        key="DATABASE_URL",
        description="SQLAlchemy database URL",
        example="sqlite+aiosqlite:///./data/agent.db",
        default="sqlite+aiosqlite:///./data/agent.db",
        required=False,
    ),
    ConfigField(
        key="SYNC_INTERVAL_MINUTES",
        description="How often (in minutes) to sync Jira and Copilot data",
        example="15",
        default="15",
        required=False,
        validator=_int_validator,
    ),
    ConfigField(
        key="STALE_THRESHOLD_DAYS",
        description="Number of days before a ticket is considered stale",
        example="10",
        default="10",
        required=False,
        validator=_int_validator,
    ),
    ConfigField(
        key="JIRA_PROJECT_KEYS",
        description="Comma-separated Jira project keys to sync (e.g. PROJ,INFRA)",
        example="PROJ,INFRA",
        default="",
        required=False,
    ),
    ConfigField(
        key="HIGH_CONFIDENCE_THRESHOLD",
        description="Confidence threshold (0–1) above which suggestions are auto-flagged",
        example="0.90",
        default="0.90",
        required=False,
        validator=_float_validator,
    ),
    ConfigField(
        key="AUTO_APPLY_ENABLED",
        description="Whether to auto-apply high-confidence suggestions (true/false)",
        example="false",
        default="false",
        required=False,
    ),
    ConfigField(
        key="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
        example="INFO",
        default="INFO",
        required=False,
    ),
]
