"""Alembic migration runner for the quickstart wizard."""

from __future__ import annotations

from alembic import command as alembic_command
from alembic import config as alembic_config
from alembic.util import CommandError


def run_migrations(database_url: str) -> None:
    """Run ``alembic upgrade head`` for *database_url*.

    Raises:
        RuntimeError: if Alembic reports a migration failure.
    """
    cfg = alembic_config.Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    try:
        alembic_command.upgrade(cfg, "head")
    except CommandError as exc:
        raise RuntimeError(str(exc)) from exc
