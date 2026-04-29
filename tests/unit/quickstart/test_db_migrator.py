"""Tests for the Alembic migration runner in src/quickstart/db_migrator.py."""

from unittest.mock import MagicMock, call, patch

import pytest

from src.quickstart.db_migrator import run_migrations


class TestRunMigrations:
    def test_calls_alembic_upgrade_head(self) -> None:
        with patch("src.quickstart.db_migrator.alembic_config.Config") as mock_cfg_cls:
            with patch("src.quickstart.db_migrator.alembic_command.upgrade") as mock_upgrade:
                mock_cfg = MagicMock()
                mock_cfg_cls.return_value = mock_cfg
                run_migrations("sqlite+aiosqlite:///./data/agent.db")
        mock_upgrade.assert_called_once_with(mock_cfg, "head")

    def test_sets_sqlalchemy_url(self) -> None:
        db_url = "sqlite+aiosqlite:///./data/agent.db"
        with patch("src.quickstart.db_migrator.alembic_config.Config") as mock_cfg_cls:
            with patch("src.quickstart.db_migrator.alembic_command.upgrade"):
                mock_cfg = MagicMock()
                mock_cfg_cls.return_value = mock_cfg
                run_migrations(db_url)
        mock_cfg.set_main_option.assert_called_with("sqlalchemy.url", db_url)

    def test_raises_runtime_error_on_command_error(self) -> None:
        from alembic.util import CommandError

        with patch("src.quickstart.db_migrator.alembic_config.Config"):
            with patch(
                "src.quickstart.db_migrator.alembic_command.upgrade",
                side_effect=CommandError("migration failed"),
            ):
                with pytest.raises(RuntimeError, match="migration failed"):
                    run_migrations("sqlite+aiosqlite:///./data/agent.db")

    def test_idempotent_already_migrated(self) -> None:
        """Running upgrade head when already at head should not raise."""
        with patch("src.quickstart.db_migrator.alembic_config.Config"):
            with patch("src.quickstart.db_migrator.alembic_command.upgrade"):
                # No exception → idempotent
                run_migrations("sqlite+aiosqlite:///./data/agent.db")
                run_migrations("sqlite+aiosqlite:///./data/agent.db")
