"""
Entry point for the Copilot MCP server.

Usage:
    python -m src.copilot_mcp               # start SSE server
    python -m src.copilot_mcp --validate    # validate credentials and exit
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys

from src.copilot_mcp.auth import GraphTokenManager
from src.copilot_mcp.config import CopilotMCPSettings, get_settings

log = logging.getLogger(__name__)

_REQUIRED_SCOPES = [
    "CallRecords.Read.All",
    "OnlineMeetings.Read.All",
]


def _decode_token_claims(token: str) -> dict:
    """Decode JWT payload without verification (we already trust the Graph API)."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


async def _validate(settings: CopilotMCPSettings) -> bool:
    """Validate credentials and required Graph permission scopes. Returns True on full pass."""
    print("Validating Copilot MCP server configuration...\n")
    all_pass = True

    # Step 1: token acquisition
    manager = GraphTokenManager(settings)
    try:
        token = await manager.get_token()
        print("[✓] Azure AD authentication: OK")
    except Exception as exc:
        print(f"[✗] Azure AD authentication: FAILED — {exc}")
        return False

    # Step 2: scope check via token claims
    claims = _decode_token_claims(token)
    # Application tokens use 'roles'; delegated tokens use 'scp'
    granted: list[str] = claims.get("roles", []) or claims.get("scp", "").split()

    for scope in _REQUIRED_SCOPES:
        if scope in granted:
            print(f"[✓] Permission scope {scope}: GRANTED")
        else:
            print(f"[✗] Permission scope {scope}: MISSING")
            all_pass = False

    print()
    if all_pass:
        print("All checks passed. Server is ready to start.")
    else:
        print("One or more checks failed. Review Azure app registration permissions.")
    return all_pass


def _start_server(settings: CopilotMCPSettings) -> None:
    import uvicorn

    from src.copilot_mcp.server import build_app

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("Starting Copilot MCP server on %s:%s", settings.mcp_host, settings.mcp_port)
    log.info("MCP SSE endpoint: http://%s:%s/sse", settings.mcp_host, settings.mcp_port)
    log.info("Health endpoint:  http://%s:%s/health", settings.mcp_host, settings.mcp_port)
    if settings.mcp_token:
        log.info("Inbound bearer token auth: ENABLED")
    else:
        log.info("Inbound bearer token auth: DISABLED (MCP_TOKEN not set)")

    app = build_app(settings)
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.copilot_mcp",
        description="Copilot MCP server — wraps Microsoft Graph API for Teams transcripts",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate Azure credentials and permission scopes, then exit",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.validate:
        ok = asyncio.run(_validate(settings))
        sys.exit(0 if ok else 1)
    else:
        _start_server(settings)


if __name__ == "__main__":
    main()
