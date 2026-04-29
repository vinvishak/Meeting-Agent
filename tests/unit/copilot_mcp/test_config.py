"""Unit tests for src/copilot_mcp/config.py."""

import pytest
from pydantic import ValidationError

from src.copilot_mcp.config import CopilotMCPSettings


def test_missing_azure_tenant_id_raises():
    with pytest.raises(ValidationError):
        CopilotMCPSettings(
            azure_tenant_id="",  # empty string is falsy but pydantic accepts it
            azure_client_id="cid",
            azure_client_secret="secret",
        )


def test_all_required_fields_loads():
    s = CopilotMCPSettings(
        azure_tenant_id="tid",
        azure_client_id="cid",
        azure_client_secret="secret",
    )
    assert s.azure_tenant_id == "tid"
    assert s.azure_client_id == "cid"
    assert s.azure_client_secret == "secret"


def test_defaults():
    s = CopilotMCPSettings(
        azure_tenant_id="tid",
        azure_client_id="cid",
        azure_client_secret="secret",
    )
    assert s.mcp_host == "0.0.0.0"
    assert s.mcp_port == 3001
    assert s.mcp_token == ""
    assert s.transcript_lookback_days == 7
    assert s.log_level == "INFO"


def test_optional_mcp_token_empty_means_no_auth():
    s = CopilotMCPSettings(
        azure_tenant_id="tid",
        azure_client_id="cid",
        azure_client_secret="secret",
        mcp_token="",
    )
    assert s.mcp_token == ""


def test_custom_values_applied():
    s = CopilotMCPSettings(
        azure_tenant_id="my-tenant",
        azure_client_id="my-client",
        azure_client_secret="my-secret",
        mcp_host="127.0.0.1",
        mcp_port=4000,
        mcp_token="tok123",
        transcript_lookback_days=14,
    )
    assert s.mcp_host == "127.0.0.1"
    assert s.mcp_port == 4000
    assert s.mcp_token == "tok123"
    assert s.transcript_lookback_days == 14


def test_missing_azure_client_id_raises():
    with pytest.raises(ValidationError):
        CopilotMCPSettings(
            azure_tenant_id="tid",
            azure_client_secret="secret",
        )


def test_missing_azure_client_secret_raises():
    with pytest.raises(ValidationError):
        CopilotMCPSettings(
            azure_tenant_id="tid",
            azure_client_id="cid",
        )
