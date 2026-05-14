"""Unit tests for src/api/routes/webhooks.py — signature validation, webhook endpoint, SSE stream."""

import hashlib
import hmac
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.broadcaster import _queues  # noqa: PLC2701
from src.api.middleware.auth import _PUBLIC_PREFIXES
from src.api.routes.webhooks import _verify_signature, sse_stream  # noqa: PLC2701

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def clear_queues():
    _queues.clear()
    yield
    _queues.clear()


@pytest.fixture
def app():
    return create_app()


# ---------------------------------------------------------------------------
# T015 — _verify_signature unit tests
# ---------------------------------------------------------------------------

def test_verify_signature_valid():
    body = b'{"test": 1}'
    secret = "mysecret"
    sig = _sign(secret, body)
    assert _verify_signature(secret, body, sig) is True


def test_verify_signature_wrong_sig():
    body = b'{"test": 1}'
    assert _verify_signature("mysecret", body, "sha256=deadbeef") is False


def test_verify_signature_empty_secret_accepts_all():
    body = b'{"test": 1}'
    assert _verify_signature("", body, "") is True
    assert _verify_signature("", body, "sha256=anything") is True


def test_verify_signature_tampered_body():
    body = b'{"test": 1}'
    secret = "mysecret"
    sig = _sign(secret, body)
    tampered = b'{"test": 2}'
    assert _verify_signature(secret, tampered, sig) is False


# ---------------------------------------------------------------------------
# T016 — POST /webhooks/github endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping_event_returns_pong(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/github",
            json={"zen": "Keep it simple"},
            headers={"X-GitHub-Event": "ping"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["message"] == "pong"


@pytest.mark.asyncio
async def test_push_with_empty_commits_returns_ok(app):
    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "name": "demo", "full_name": "acme/demo",
            "default_branch": "main", "owner": {"login": "acme"},
        },
        "commits": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "push"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_push_with_invalid_signature_returns_403(app, monkeypatch):
    import src.api.routes.webhooks as wh_module
    from src.config import Settings
    # Patch get_settings in the webhooks module's namespace (where it is actually called)
    monkeypatch.setattr(wh_module, "get_settings", lambda: Settings(github_webhook_secret="secret"))

    payload = b'{"ref": "refs/heads/main", "commits": [], "repository": {}}'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_push_with_commits_and_no_secret_returns_ok(app):
    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "name": "demo", "full_name": "acme/demo",
            "default_branch": "main", "owner": {"login": "acme"},
        },
        "commits": [
            {
                "id": "a" * 40,
                "message": "ENG-1 test commit",
                "timestamp": "2026-05-03T10:00:00Z",
                "url": "https://github.com/acme/demo/commit/aaaa",
                "author": {"name": "Alice", "email": "alice@acme.com", "username": "alice"},
            }
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "push"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# T009 — GET /stream SSE endpoint tests
# Tested at the generator level to avoid streaming HTTP complexity.
# End-to-end SSE delivery is an integration-test concern (see quickstart.md Scenario 1).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_generator_yields_retry_directive_first():
    """SSE generator's first yield must be the retry directive."""
    mock_request = AsyncMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    response = await sse_stream(mock_request)
    gen = response.body_iterator

    first = await gen.__anext__()
    text = first if isinstance(first, str) else first.decode()
    assert "retry:" in text

    await gen.aclose()  # clean up the infinite generator


def test_sse_stream_is_in_public_prefixes():
    """SSE stream must be public — EventSource API cannot send Authorization headers."""
    assert "/api/v1/stream" in _PUBLIC_PREFIXES
