"""Tests for non-interactive mode in src/quickstart/__init__.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.quickstart import main, noninteractive_flow
from src.quickstart.config_schema import QUICKSTART_FIELDS

_REQUIRED_ARGS = [
    "--non-interactive",
    "--jira-mcp-url", "http://jira.example.com",
    "--jira-mcp-token", "jira-token",
    "--copilot-mcp-url", "http://copilot.example.com",
    "--copilot-mcp-token", "copilot-token",
    "--anthropic-api-key", "sk-ant-test",
]


def _ok_connectivity():
    """Patch _run_connectivity_checks to return all-ok."""
    from src.quickstart.connectivity import ConnectionCheckResult
    ok = [ConnectionCheckResult(service=s, ok=True) for s in ["Jira MCP", "Copilot MCP", "Claude API", "Database"]]
    return patch("src.quickstart._run_connectivity_checks", return_value=ok)


class TestNonInteractiveMode:
    def test_all_required_flags_present_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        # create a minimal alembic.ini so write_env and migrator don't fail on path
        (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n")
        with _ok_connectivity():
            with patch("src.quickstart.run_migrations"):
                result = main(_REQUIRED_ARGS)
        assert result == 0

    def test_writes_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n")
        with _ok_connectivity():
            with patch("src.quickstart.run_migrations"):
                main(_REQUIRED_ARGS)
        assert (tmp_path / ".env").exists()
        content = (tmp_path / ".env").read_text()
        assert "JIRA_MCP_URL=http://jira.example.com" in content

    def test_missing_required_flag_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        # Omit --anthropic-api-key
        args = [
            "--non-interactive",
            "--jira-mcp-url", "http://jira.example.com",
            "--jira-mcp-token", "jira-token",
            "--copilot-mcp-url", "http://copilot.example.com",
            "--copilot-mcp-token", "copilot-token",
        ]
        with pytest.raises(SystemExit) as exc_info:
            main(args)
        assert exc_info.value.code == 1

    def test_missing_required_flag_lists_missing_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.chdir(tmp_path)
        args = ["--non-interactive", "--jira-mcp-url", "http://x"]
        with pytest.raises(SystemExit):
            main(args)
        out = capsys.readouterr().out
        assert "--jira-mcp-token" in out or "--copilot-mcp-url" in out

    def test_optional_flags_use_defaults_when_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n")
        with _ok_connectivity():
            with patch("src.quickstart.run_migrations"):
                main(_REQUIRED_ARGS)
        content = (tmp_path / ".env").read_text()
        assert "LOG_LEVEL=INFO" in content
        assert "SYNC_INTERVAL_MINUTES=15" in content

    def test_connectivity_failure_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n")
        from src.quickstart.connectivity import ConnectionCheckResult
        bad = [ConnectionCheckResult(service="Jira MCP", ok=False, error="refused")]
        with patch("src.quickstart._run_connectivity_checks", return_value=bad):
            with pytest.raises(SystemExit) as exc_info:
                main(_REQUIRED_ARGS)
        assert exc_info.value.code == 1
