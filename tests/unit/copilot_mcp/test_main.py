"""Unit tests for src/copilot_mcp/__main__.py — US4 surface."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.copilot_mcp.config import CopilotMCPSettings

_SETTINGS_OK = CopilotMCPSettings(
    azure_tenant_id="test-tenant",
    azure_client_id="test-client",
    azure_client_secret="test-secret",
)


def _run_validate(settings: CopilotMCPSettings, token_result=None, token_error=None):
    """Helper: run _validate() with mocked token manager."""
    import asyncio

    from src.copilot_mcp.__main__ import _validate

    mock_mgr = MagicMock()
    if token_error:
        mock_mgr.get_token = AsyncMock(side_effect=token_error)
    else:
        mock_mgr.get_token = AsyncMock(return_value=token_result or "")

    with patch("src.copilot_mcp.__main__.GraphTokenManager", return_value=mock_mgr):
        return asyncio.run(_validate(settings))


# ---------------------------------------------------------------------------
# --validate: missing env vars (settings validation)
# ---------------------------------------------------------------------------


def test_validate_missing_azure_tenant_id_exits_nonzero():
    """get_settings() failure due to missing AZURE_TENANT_ID causes non-zero exit or exception."""
    with patch("sys.argv", ["prog", "--validate"]), patch(
        "src.copilot_mcp.__main__.get_settings",
        side_effect=Exception("AZURE_TENANT_ID is required"),
    ):
        from src.copilot_mcp.__main__ import main
        with pytest.raises((SystemExit, Exception)):
            main()


def test_validate_missing_azure_tenant_id_message(capsys):
    """main() with missing tenant should propagate error."""
    with patch("sys.argv", ["prog", "--validate"]), patch(
        "src.copilot_mcp.__main__.get_settings",
        side_effect=ValueError("AZURE_TENANT_ID is required"),
    ):
        from src.copilot_mcp.__main__ import main
        with pytest.raises((SystemExit, ValueError)):
            main()


# ---------------------------------------------------------------------------
# --validate: MSAL auth failure
# ---------------------------------------------------------------------------


def test_validate_msal_auth_failure_returns_false(capsys):
    ok = _run_validate(
        _SETTINGS_OK,
        token_error=RuntimeError("Graph API authentication failed: invalid_client — bad secret"),
    )
    captured = capsys.readouterr()
    assert not ok
    assert "FAILED" in captured.out
    assert "invalid_client" in captured.out or "authentication" in captured.out.lower()


def test_validate_auth_failure_exits_nonzero():
    from src.copilot_mcp.__main__ import main

    mock_mgr = MagicMock()
    mock_mgr.get_token = AsyncMock(
        side_effect=RuntimeError("Graph API authentication failed: bad_secret")
    )
    with (
        patch("sys.argv", ["prog", "--validate"]),
        patch("src.copilot_mcp.__main__.get_settings", return_value=_SETTINGS_OK),
        patch("src.copilot_mcp.__main__.GraphTokenManager", return_value=mock_mgr),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code != 0


# ---------------------------------------------------------------------------
# --validate: scope checks
# ---------------------------------------------------------------------------


def _make_jwt_with_roles(roles: list[str]) -> str:
    """Create a fake JWT with roles in the payload (no real signing)."""
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload_data = {"roles": roles}
    payload = (
        base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    )
    return f"{header}.{payload}.fakesig"


def test_validate_missing_scope_prints_missing_and_exits_nonzero(capsys):
    # Token has only one of the two required scopes
    token = _make_jwt_with_roles(["CallRecords.Read.All"])
    ok = _run_validate(_SETTINGS_OK, token_result=token)
    captured = capsys.readouterr()
    assert not ok
    assert "MISSING" in captured.out
    assert "OnlineMeetings.Read.All" in captured.out


def test_validate_all_scopes_present_returns_true(capsys):
    token = _make_jwt_with_roles(["CallRecords.Read.All", "OnlineMeetings.Read.All"])
    ok = _run_validate(_SETTINGS_OK, token_result=token)
    captured = capsys.readouterr()
    assert ok
    assert "MISSING" not in captured.out
    # Both scopes should show [✓]
    assert captured.out.count("[✓]") >= 2


def test_validate_all_pass_exits_zero():
    from src.copilot_mcp.__main__ import main

    token = _make_jwt_with_roles(["CallRecords.Read.All", "OnlineMeetings.Read.All"])
    mock_mgr = MagicMock()
    mock_mgr.get_token = AsyncMock(return_value=token)
    with (
        patch("sys.argv", ["prog", "--validate"]),
        patch("src.copilot_mcp.__main__.get_settings", return_value=_SETTINGS_OK),
        patch("src.copilot_mcp.__main__.GraphTokenManager", return_value=mock_mgr),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 0
