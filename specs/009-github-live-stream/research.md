# Research: Real-Time GitHub Activity Stream

**Feature**: `009-github-live-stream` | **Date**: 2026-05-03

## Decision 1: Real-time delivery mechanism — SSE vs WebSocket

**Decision**: Server-Sent Events (SSE) via the browser `EventSource` API.

**Rationale**: The dashboard only needs server-to-client push (one direction). SSE is simpler to implement, natively supported in all modern browsers, and auto-reconnects without custom code. WebSocket is bidirectional and requires a handshake upgrade — unnecessary complexity for this use case.

**Alternatives considered**:
- WebSocket: Bidirectional, but adds complexity (upgrade protocol, connection management library) with no benefit here since clients never send data over the stream.
- Long-polling: High overhead; creates bursty load and does not deliver sub-second latency.

---

## Decision 2: In-process broadcaster vs Redis pub/sub

**Decision**: In-process `asyncio.Queue` list maintained in `src/api/broadcaster.py`.

**Rationale**: The deployment target is a single-process uvicorn server (Railway free tier). An in-process broadcaster has zero infrastructure dependency, zero network latency, and is trivially testable. Horizontal scaling is not a requirement for MVP.

**Alternatives considered**:
- Redis pub/sub: Required for multi-process or multi-instance deployments. Adds an external dependency, operational complexity, and cost. Not justified at current scale.
- Database polling: Clients poll `/api/v1/github/commits` on a timer. Adds latency (polling interval), backend load, and does not deliver the "appears within seconds" UX.

---

## Decision 3: Webhook authentication — HMAC-SHA256

**Decision**: Validate `X-Hub-Signature-256` header using HMAC-SHA256 with a shared secret (`GITHUB_WEBHOOK_SECRET` env var). Accept all requests (dev mode) if the secret is not configured.

**Rationale**: GitHub signs every webhook delivery with HMAC-SHA256. Validating this prevents spoofed payloads from arbitrary sources. The shared-secret model is the GitHub-native approach and requires no OAuth or PKI infrastructure.

**Alternatives considered**:
- IP allowlist: GitHub publishes its webhook IP ranges, but they change and require maintenance. HMAC is simpler and more robust.
- Unsigned (no validation): Acceptable only in local development. Production deployments must set the secret.

---

## Decision 4: Webhook endpoint auth exemption

**Decision**: `/api/v1/webhooks/` is exempt from Bearer-token authentication. Webhook authenticity is established by HMAC validation instead.

**Rationale**: GitHub cannot send Bearer tokens. The HMAC signature is equivalent — it proves the sender is a GitHub entity with access to the shared secret.

---

## Decision 5: SSE stream auth exemption

**Decision**: `/api/v1/stream` is exempt from Bearer-token authentication.

**Rationale**: The browser `EventSource` API does not support custom request headers. The stream endpoint delivers commit metadata that is already visible in the dashboard — no sensitive data is exposed. Tightening auth would require a custom EventSource polyfill or a cookie-based session, both of which add complexity with negligible security benefit for an internal engineering tool.

---

## Decision 6: Jira key extraction pattern

**Decision**: Reuse `extract_jira_keys()` from `src/ingestion/github_client.py`. This function applies the regex `[A-Z][A-Z0-9]+-\d+` to commit messages and returns all matches.

**Rationale**: The pattern already exists, is tested as part of the GitHub sync feature, and captures the standard Jira key format. Duplicating or replacing it would violate the DRY principle.

---

## Decision 7: Commit upsert semantics

**Decision**: Use `INSERT OR REPLACE` semantics (SQLAlchemy `merge` / `on_conflict_do_update`) keyed on the commit SHA. Duplicate webhook deliveries (GitHub guarantees at-least-once) produce no duplicate rows.

**Rationale**: SHA is a content-addressed identifier — the same SHA always represents the same commit. Upserting on SHA is idempotent and safe.

---

## Decision 8: Background task for ingestion

**Decision**: Ingestion (`_ingest_push`) runs as a FastAPI `BackgroundTask`, not inline in the webhook handler.

**Rationale**: The webhook handler must return a 200 within GitHub's 10-second timeout. Database writes and broadcast may take longer under load. Offloading to a background task decouples latency from response time.
