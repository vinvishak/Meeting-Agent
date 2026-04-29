"""Tests for health check mode (--check) in src/quickstart/__init__.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.quickstart import main
from src.quickstart.connectivity import ConnectionCheckResult


def _all_ok() -> list[ConnectionCheckResult]:
    return [
        ConnectionCheckResult(service=s, ok=True)
        for s in ["Jira MCP", "Copilot MCP", "Claude API", "Database"]
    ]


def _one_failing() -> list[ConnectionCheckResult]:
    return [
        ConnectionCheckResult(service="Jira MCP", ok=False, error="Connection refused", suggestion="Is it running?"),
        ConnectionCheckResult(service="Copilot MCP", ok=True),
        ConnectionCheckResult(service="Claude API", ok=True),
        ConnectionCheckResult(service="Database", ok=True),
    ]


class TestHealthCheckMode:
    def test_exits_0_when_all_services_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://x\n")
        with patch("src.quickstart._run_connectivity_checks", return_value=_all_ok()):
            result = main(["--check"])
        assert result == 0

    def test_exits_1_when_any_service_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://x\n")
        with patch("src.quickstart._run_connectivity_checks", return_value=_one_failing()):
            with pytest.raises(SystemExit) as exc_info:
                main(["--check"])
        assert exc_info.value.code == 1

    def test_prints_pass_fail_per_service(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://x\n")
        with patch("src.quickstart._run_connectivity_checks", return_value=_one_failing()):
            with pytest.raises(SystemExit):
                main(["--check"])
        out = capsys.readouterr().out
        assert "Jira MCP" in out
        assert "Copilot MCP" in out

    def test_does_not_write_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://x\n")
        original_mtime = (tmp_path / ".env").stat().st_mtime
        with patch("src.quickstart._run_connectivity_checks", return_value=_all_ok()):
            main(["--check"])
        assert (tmp_path / ".env").stat().st_mtime == original_mtime

    def test_does_not_run_migrations(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://x\n")
        with patch("src.quickstart._run_connectivity_checks", return_value=_all_ok()):
            with patch("src.quickstart.run_migrations") as mock_migrate:
                main(["--check"])
        mock_migrate.assert_not_called()

    def test_exits_1_when_env_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        # No .env file
        with pytest.raises(SystemExit) as exc_info:
            main(["--check"])
        assert exc_info.value.code == 1

    def test_reads_values_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("JIRA_MCP_URL=http://jira.local\nJIRA_MCP_TOKEN=tok\n")
        captured_values: dict = {}

        def capture(values: dict) -> list[ConnectionCheckResult]:
            captured_values.update(values)
            return _all_ok()

        with patch("src.quickstart._run_connectivity_checks", side_effect=capture):
            main(["--check"])
        assert captured_values.get("JIRA_MCP_URL") == "http://jira.local"
