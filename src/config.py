from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Jira MCP Server
    jira_mcp_url: str = "http://localhost:3000"
    jira_mcp_token: str = ""

    # Copilot MCP Server
    copilot_mcp_url: str = "http://localhost:3001"
    copilot_mcp_token: str = ""

    # Claude API (semantic matching + NL queries)
    anthropic_api_key: str = ""

    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/agent.db"

    # Sync settings
    sync_interval_minutes: int = 15
    stale_threshold_days: int = 10
    # Comma-separated Jira project/board keys to poll (e.g. "PROJ,INFRA,PLAT")
    jira_project_keys: str = ""

    # Update suggestion thresholds
    high_confidence_threshold: float = 0.90
    auto_apply_enabled: bool = False

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
