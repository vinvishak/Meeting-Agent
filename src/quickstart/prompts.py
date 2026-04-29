"""Interactive prompt helpers for the quickstart wizard."""

from __future__ import annotations

import getpass

from src.quickstart.config_schema import ConfigField


def mask_secret(value: str) -> str:
    """Return ``****<last4>`` for a secret value; plain ``****`` if ≤ 4 chars."""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def prompt_field(field: ConfigField, existing: str | None) -> str:
    """Prompt the user for a non-secret field value using ``input()``.

    The prompt shows the field description and, if there is an existing or
    default value, offers it as the default (press Enter to accept).
    """
    fallback = existing if existing is not None else (field.default or "")
    hint = f" [{fallback}]" if fallback else f" (e.g. {field.example})"
    raw = input(f"  {field.description}{hint}: ").strip()
    if not raw:
        return fallback
    return raw


def prompt_secret(field: ConfigField, existing: str | None) -> str:
    """Prompt the user for a secret field value using ``getpass.getpass()``.

    If the user presses Enter without typing, the existing value (or empty
    string) is kept.
    """
    fallback = existing if existing is not None else ""
    masked_hint = f" [{mask_secret(fallback)}]" if fallback else f" (e.g. {field.example})"
    raw = getpass.getpass(f"  {field.description}{masked_hint}: ")
    if not raw:
        return fallback
    return raw
