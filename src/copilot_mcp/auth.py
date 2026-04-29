"""
Graph API token manager.

Wraps msal.ConfidentialClientApplication with an in-memory token cache.
get_token() is async (via asyncio.to_thread) so it does not block the
event loop during token acquisition or refresh.
"""

import asyncio
from typing import Any

import msal

from src.copilot_mcp.config import CopilotMCPSettings

_GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


class GraphTokenManager:
    """Acquires and caches OAuth 2.0 access tokens for the Microsoft Graph API."""

    def __init__(self, settings: CopilotMCPSettings) -> None:
        self._cache = msal.SerializableTokenCache()
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
            token_cache=self._cache,
        )

    def _acquire(self) -> str:
        """Synchronous token acquisition — run via asyncio.to_thread."""
        # Try cache first
        result: dict[str, Any] = self._app.acquire_token_silent(_GRAPH_SCOPE, account=None)
        if not result:
            result = self._app.acquire_token_for_client(scopes=_GRAPH_SCOPE)

        if "access_token" not in result:
            error = result.get("error", "unknown_error")
            description = result.get("error_description", "")
            raise RuntimeError(f"Graph API authentication failed: {error} — {description}")

        return result["access_token"]

    async def get_token(self) -> str:
        """Return a valid bearer token, refreshing if necessary."""
        return await asyncio.to_thread(self._acquire)
