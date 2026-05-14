# Contract: GitHub Push Webhook

**Endpoint**: `POST /api/v1/webhooks/github`  
**Auth**: HMAC-SHA256 signature in `X-Hub-Signature-256` header (exempt from Bearer auth)

---

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Hub-Signature-256` | Yes (prod) | `sha256=<hex>` HMAC of request body using `GITHUB_WEBHOOK_SECRET` |
| `X-GitHub-Event` | Yes | Event type — this contract handles `push` and `ping` |
| `Content-Type` | Yes | Must be `application/json` |

### Body — Push Event (abbreviated)

```json
{
  "ref": "refs/heads/main",
  "repository": {
    "name": "my-repo",
    "full_name": "acme/my-repo",
    "default_branch": "main",
    "owner": { "login": "acme" }
  },
  "commits": [
    {
      "id": "abc123def456abc123def456abc123def456abc1",
      "message": "ENG-42 fix the thing",
      "timestamp": "2026-05-03T10:00:00Z",
      "url": "https://github.com/acme/my-repo/commit/abc123def456abc123def456abc123def456abc1",
      "author": {
        "name": "Alice",
        "email": "alice@acme.com",
        "username": "alice"
      }
    }
  ]
}
```

### Body — Ping Event

```json
{ "zen": "Keep it logically awesome.", "hook_id": 12345 }
```

---

## Response

### 200 OK — Accepted

```json
{ "ok": true }
```

Returned for: valid push events (ingestion runs in background), ping events.

```json
{ "ok": true, "message": "pong" }
```

Returned specifically for ping events.

### 403 Forbidden — Invalid signature

```json
{ "detail": "Invalid webhook signature" }
```

### Business rules

1. If `GITHUB_WEBHOOK_SECRET` is empty, signature validation is skipped (dev mode only).
2. Push events with an empty `commits` array (e.g. branch deletion) are acknowledged but not ingested.
3. Duplicate commit SHAs are upserted — no error, no duplicate rows.
4. Jira keys are extracted from `commit.message` using the pattern `[A-Z][A-Z0-9]+-\d+`.
