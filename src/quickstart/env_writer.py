"""Read, write, and merge .env files for the quickstart wizard."""

from __future__ import annotations

from pathlib import Path

from src.quickstart.config_schema import ConfigField

# ---------------------------------------------------------------------------
# Reader (foundational — used by all modes)
# ---------------------------------------------------------------------------

def load_env(path: str) -> dict[str, str]:
    """Parse a .env file and return a key→value mapping.

    Returns an empty dict if the file does not exist.
    Lines starting with ``#`` (after stripping) and blank lines are skipped.
    """
    p = Path(path)
    if not p.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value  # preserve value as-is (may contain =)
    return result


# ---------------------------------------------------------------------------
# Writer (US1)
# ---------------------------------------------------------------------------

def write_env(path: str, fields: list[ConfigField], values: dict[str, str]) -> None:
    """Write a ``.env`` file from *fields* and *values*.

    For each field, the value is taken from *values*; if absent, the field's
    ``default`` is used.  Fields are written in the order they appear in
    *fields*.
    """
    lines: list[str] = []
    for field in fields:
        value = values.get(field.key, field.default or "")
        lines.append(f"{field.key}={value}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Merge (US1)
# ---------------------------------------------------------------------------

def merge_env(existing: dict[str, str], new_values: dict[str, str]) -> dict[str, str]:
    """Return a merged mapping: *new_values* override *existing*; unrelated keys are kept."""
    return {**existing, **new_values}


# ---------------------------------------------------------------------------
# Summary display (US1 / US2)
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Return ``****<last4>`` for a secret value; shows full value if ≤ 4 chars."""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def print_summary(fields: list[ConfigField], values: dict[str, str]) -> None:
    """Print a human-readable table of configuration values, masking secrets."""
    col_width = max((len(f.key) for f in fields), default=20) + 2
    print("\nConfiguration Summary")
    print("─" * (col_width + 40))
    for field in fields:
        raw = values.get(field.key, field.default or "")
        display = _mask(raw) if field.secret else raw
        print(f"  {field.key:<{col_width}}{display}")
    print("─" * (col_width + 40))
