"""Unit tests for src/copilot_mcp/server.py — US1 surface."""

from unittest.mock import MagicMock, patch

from httpx import ASGITransport, AsyncClient

from src.copilot_mcp.config import CopilotMCPSettings
from src.copilot_mcp.server import build_app

_SETTINGS_NO_TOKEN = CopilotMCPSettings(
    azure_tenant_id="test-tenant",
    azure_client_id="test-client",
    azure_client_secret="test-secret",
    mcp_token="",
)

_SETTINGS_WITH_TOKEN = CopilotMCPSettings(
    azure_tenant_id="test-tenant",
    azure_client_id="test-client",
    azure_client_secret="test-secret",
    mcp_token="super-secret",
)


def _mock_msal_app() -> MagicMock:
    app = MagicMock()
    app.acquire_token_silent.return_value = None
    app.acquire_token_for_client.return_value = {"access_token": "test-tok"}
    return app


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def test_health_returns_200_ok():
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=_mock_msal_app()):
        app = build_app(_SETTINGS_NO_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_does_not_call_graph_api():
    """Health endpoint must not trigger any Graph API authentication."""
    msal_mock = _mock_msal_app()
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=msal_mock):
        app = build_app(_SETTINGS_NO_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")
    # No token acquisition should have happened
    msal_mock.acquire_token_for_client.assert_not_called()
    msal_mock.acquire_token_silent.assert_not_called()


# ---------------------------------------------------------------------------
# Bearer token auth middleware
# ---------------------------------------------------------------------------


async def test_missing_bearer_token_returns_401_when_token_configured():
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=_mock_msal_app()):
        app = build_app(_SETTINGS_WITH_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # /sse is the MCP endpoint — no auth header
        resp = await client.get("/sse")
    assert resp.status_code == 401


async def test_wrong_bearer_token_returns_401():
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=_mock_msal_app()):
        app = build_app(_SETTINGS_WITH_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/sse", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


async def test_correct_bearer_token_passes_health():
    """Correct token header should not block the health endpoint."""
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=_mock_msal_app()):
        app = build_app(_SETTINGS_WITH_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # /health is excluded from auth checks; but supplying the right token should still work
        resp = await client.get("/health", headers={"Authorization": "Bearer super-secret"})
    assert resp.status_code == 200


async def test_no_auth_middleware_when_token_not_configured():
    """When MCP_TOKEN is empty, health check should not be blocked."""
    with patch("src.copilot_mcp.auth.msal.ConfidentialClientApplication", return_value=_mock_msal_app()):
        app = build_app(_SETTINGS_NO_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
