"""Unit tests for src/copilot_mcp/auth.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.copilot_mcp.auth import GraphTokenManager
from src.copilot_mcp.config import CopilotMCPSettings

_SETTINGS = CopilotMCPSettings(
    azure_tenant_id="test-tenant",
    azure_client_id="test-client",
    azure_client_secret="test-secret",
)


def _make_manager(app_mock: MagicMock) -> GraphTokenManager:
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=app_mock):
        return GraphTokenManager(_SETTINGS)


async def test_successful_token_acquisition():
    app = MagicMock()
    app.acquire_token_silent.return_value = None  # cache miss
    app.acquire_token_for_client.return_value = {"access_token": "tok-abc"}

    mgr = _make_manager(app)
    token = await mgr.get_token()

    assert token == "tok-abc"
    app.acquire_token_for_client.assert_called_once()


async def test_cached_token_no_second_msal_call():
    app = MagicMock()
    app.acquire_token_silent.return_value = {"access_token": "cached-tok"}

    mgr = _make_manager(app)
    token = await mgr.get_token()

    assert token == "cached-tok"
    app.acquire_token_for_client.assert_not_called()


async def test_expired_token_triggers_reacquisition():
    app = MagicMock()
    mgr = _make_manager(app)

    # First acquisition — cache miss, fresh token fetched
    app.acquire_token_silent.return_value = None
    app.acquire_token_for_client.return_value = {"access_token": "tok-1"}
    t1 = await mgr.get_token()
    assert t1 == "tok-1"

    # Second acquisition — cache miss again (simulates expiry), new token fetched
    app.acquire_token_for_client.return_value = {"access_token": "tok-2"}
    t2 = await mgr.get_token()
    assert t2 == "tok-2"
    assert app.acquire_token_for_client.call_count == 2


async def test_msal_error_raises_runtime_error():
    app = MagicMock()
    app.acquire_token_silent.return_value = None
    app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Wrong secret",
    }

    mgr = _make_manager(app)

    with pytest.raises(RuntimeError, match="Graph API authentication failed"):
        await mgr.get_token()


async def test_runtime_error_message_contains_error_code():
    app = MagicMock()
    app.acquire_token_silent.return_value = None
    app.acquire_token_for_client.return_value = {
        "error": "AADSTS70011",
        "error_description": "Invalid scope",
    }

    mgr = _make_manager(app)

    with pytest.raises(RuntimeError, match="AADSTS70011"):
        await mgr.get_token()
