"""
Copilot MCP Wrapper configuration.

Reads all settings from environment variables. Raises ValidationError at
import time if any required field is missing, so misconfiguration is caught
before any network calls are attempted.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CopilotMCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure AD app registration (required)
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str

    # MCP server transport
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 3001
    mcp_token: str = ""  # Empty string = no inbound auth required

    # Graph API behaviour
    transcript_lookback_days: int = 7

    @field_validator("azure_tenant_id", "azure_client_id", "azure_client_secret")
    @classmethod
    def must_not_be_empty(cls, v: str, info: object) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> CopilotMCPSettings:
    return CopilotMCPSettings()
