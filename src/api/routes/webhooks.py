"""
GitHub webhook receiver + Server-Sent Events stream.

Webhook  POST /api/v1/webhooks/github
  - Validates HMAC-SHA256 signature (skipped if GITHUB_WEBHOOK_SECRET is empty)
  - Handles push events: stores commits + Jira links, then broadcasts to SSE clients

SSE stream  GET /api/v1/stream
  - No auth header needed (EventSource API cannot send custom headers)
  - Streams newline-delimited JSON events to the dashboard
  - Sends a keepalive comment every 20 s to prevent proxy timeouts
"""

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.broadcaster import broadcast, subscribe, unsubscribe
from src.config import get_settings
from src.ingestion.github_client import extract_jira_keys
from src.logging_config import get_logger
from src.storage.database import AsyncSessionLocal
from src.storage.repository import GitHubRepository

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(secret: str, body: bytes, sig_header: str) -> bool:
    if not secret:
        return True  # no secret configured — accept all (dev mode)
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


# ---------------------------------------------------------------------------
# Push-event ingestion (runs as a background task)
# ---------------------------------------------------------------------------

async def _ingest_push(payload: dict) -> None:
    repo_data     = payload.get("repository", {})
    full_name     = repo_data.get("full_name", "")
    org           = (repo_data.get("owner") or {}).get("login", "")
    name          = repo_data.get("name", "")
    default_branch = repo_data.get("default_branch", "main")
    ref_branch    = payload.get("ref", "").replace("refs/heads/", "") or None

    broadcasted: list[dict] = []

    async with AsyncSessionLocal() as session:
        repo = await GitHubRepository.upsert_repo(
            session, org=org, name=name, full_name=full_name, default_branch=default_branch
        )

        for raw in payload.get("commits", []):
            author = raw.get("author") or {}
            try:
                committed_at = datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                committed_at = datetime.now(UTC)

            await GitHubRepository.upsert_commit(
                session,
                repo_id=repo.id,
                sha=raw["id"],
                message=raw.get("message", ""),
                author_login=author.get("username"),
                author_name=author.get("name"),
                author_email=author.get("email"),
                committed_at=committed_at,
                branch=ref_branch,
                url=raw.get("url"),
            )

            jira_keys = extract_jira_keys(raw.get("message", ""))
            for key in jira_keys:
                await GitHubRepository.upsert_jira_link(
                    session,
                    source_type="commit",
                    commit_sha=raw["id"],
                    pr_id=None,
                    jira_key=key,
                )

            broadcasted.append({
                "type": "new_commit",
                "commit": {
                    "sha":          raw["id"][:8],
                    "message":      raw.get("message", "").split("\n")[0][:120],
                    "author_login": author.get("username") or author.get("name", "unknown"),
                    "url":          raw.get("url"),
                    "committed_at": raw.get("timestamp"),
                    "jira_keys":    jira_keys,
                    "repo":         full_name,
                },
            })

        await session.commit()

    logger.info("Webhook: stored %d commit(s) from %s", len(broadcasted), full_name)
    for event in broadcasted:
        await broadcast(event)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default="ping"),
) -> dict:
    body = await request.body()
    settings = get_settings()

    if not _verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    if x_github_event == "ping":
        return {"ok": True, "message": "pong"}

    if x_github_event == "push":
        payload = json.loads(body)
        # Skip empty pushes (branch deletions etc.)
        if payload.get("commits"):
            background_tasks.add_task(_ingest_push, payload)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Server-Sent Events stream
# ---------------------------------------------------------------------------

@router.get("/stream")
async def sse_stream(request: Request) -> StreamingResponse:
    """
    Real-time event stream for the dashboard.
    EventSource (browser API) cannot send custom headers, so this endpoint
    is exempt from Bearer-token auth — see auth middleware public prefixes.
    """
    async def generator():
        q = subscribe()
        try:
            # Tell the browser to reconnect after 3 s if the connection drops
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
