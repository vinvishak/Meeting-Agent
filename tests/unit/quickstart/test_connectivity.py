"""Tests for connectivity probes in src/quickstart/connectivity.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.quickstart.connectivity import (
    ConnectionCheckResult,
    check_anthropic,
    check_db,
    check_mcp,
)


class TestConnectionCheckResult:
    def test_ok_result(self) -> None:
        r = ConnectionCheckResult(service="Jira MCP", ok=True)
        assert r.ok is True
        assert r.error is None
        assert r.suggestion is None

    def test_failed_result(self) -> None:
        r = ConnectionCheckResult(service="Jira MCP", ok=False, error="refused", suggestion="Check server")
        assert r.ok is False
        assert r.error == "refused"
        assert r.suggestion == "Check server"


class TestCheckMcp:
    def test_returns_ok_on_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("src.quickstart.connectivity.httpx.get", return_value=mock_resp):
            result = check_mcp("Jira MCP", "http://localhost:3000", "token")
        assert result.ok is True
        assert result.service == "Jira MCP"

    def test_returns_ok_on_401(self) -> None:
        # 401 means server is reachable (auth handled separately)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("src.quickstart.connectivity.httpx.get", return_value=mock_resp):
            result = check_mcp("Jira MCP", "http://localhost:3000", "token")
        assert result.ok is True

    def test_returns_fail_on_connection_error(self) -> None:
        import httpx
        with patch("src.quickstart.connectivity.httpx.get", side_effect=httpx.ConnectError("refused")):
            result = check_mcp("Jira MCP", "http://localhost:3000", "token")
        assert result.ok is False
        assert result.error is not None

    def test_returns_fail_on_timeout(self) -> None:
        import httpx
        with patch("src.quickstart.connectivity.httpx.get", side_effect=httpx.TimeoutException("timed out")):
            result = check_mcp("Jira MCP", "http://localhost:3000", "token")
        assert result.ok is False


class TestCheckAnthropic:
    def test_returns_ok_on_successful_list(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock()
        with patch("src.quickstart.connectivity.anthropic.Anthropic", return_value=mock_client):
            result = check_anthropic("sk-ant-test")
        assert result.ok is True
        assert result.service == "Claude API"

    def test_returns_fail_on_auth_error(self) -> None:
        import anthropic as _anthropic
        mock_client = MagicMock()
        mock_client.models.list.side_effect = _anthropic.AuthenticationError(
            message="invalid key", response=MagicMock(), body={}
        )
        with patch("src.quickstart.connectivity.anthropic.Anthropic", return_value=mock_client):
            result = check_anthropic("bad-key")
        assert result.ok is False
        assert result.error is not None


class TestCheckDb:
    def test_returns_ok_when_alembic_env_runs(self) -> None:
        with patch("src.quickstart.connectivity.alembic_config.Config") as mock_cfg_cls:
            with patch("src.quickstart.connectivity.alembic_command.current"):
                result = check_db("sqlite+aiosqlite:///./data/agent.db")
        assert result.ok is True
        assert result.service == "Database"

    def test_returns_fail_on_exception(self) -> None:
        with patch("src.quickstart.connectivity.alembic_config.Config", side_effect=Exception("no alembic.ini")):
            result = check_db("sqlite+aiosqlite:///./data/agent.db")
        assert result.ok is False
