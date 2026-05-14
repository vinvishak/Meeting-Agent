# Contract: Server-Sent Events Stream

**Endpoint**: `GET /api/v1/stream`  
**Auth**: None required (EventSource API cannot send custom headers; stream is public)  
**Media type**: `text/event-stream`

---

## Connection Lifecycle

1. Client opens `EventSource` to `GET /api/v1/stream`.
2. Server responds with `retry: 3000` — instructs browser to reconnect after 3 s if disconnected.
3. Server sends a `: keepalive` comment every 20 s to prevent proxy/load-balancer timeouts.
4. When a new commit is ingested via webhook, the server sends a `data:` event within 5 s.
5. When the client disconnects, the server removes the client's queue.

---

## Event Format

All events are newline-delimited SSE messages:

```
data: <JSON>\n\n
```

### Event type: `new_commit`

Emitted whenever a push webhook delivers one or more commits.

```json
{
  "type": "new_commit",
  "commit": {
    "sha": "abc123de",
    "message": "ENG-42 fix the thing",
    "author_login": "alice",
    "url": "https://github.com/acme/my-repo/commit/abc123de...",
    "committed_at": "2026-05-03T10:00:00Z",
    "jira_keys": ["ENG-42"],
    "repo": "acme/my-repo"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `"new_commit"` | Discriminator for future event types |
| `commit.sha` | string (8 chars) | Short SHA for display |
| `commit.message` | string (≤ 120 chars) | First line of commit message |
| `commit.author_login` | string | GitHub username; falls back to display name |
| `commit.url` | string \| null | GitHub web URL to the commit |
| `commit.committed_at` | ISO 8601 string | Commit timestamp in UTC |
| `commit.jira_keys` | string[] | Extracted Jira ticket keys (may be `[]`) |
| `commit.repo` | string | `org/repo` canonical name |

### Keepalive

```
: keepalive\n\n
```

SSE comment — browsers ignore this. Sent every 20 s to prevent idle-connection drops.

---

## Client Behaviour Contract

- On `open`: Show "Live" badge (green indicator).
- On `message` with `type === "new_commit"`: Prepend a commit card to the activity feed.
- On `error`: Hide Live badge; browser retries automatically after `retry` ms (3000 ms).
- No explicit close — the stream is kept open for the lifetime of the page session.
