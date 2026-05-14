# Quickstart & Test Scenarios: Real-Time GitHub Activity Stream

**Feature**: `009-github-live-stream` | **Date**: 2026-05-03

---

## Prerequisites

- Server running locally: `uv run uvicorn src.api.app:create_app --factory --port 8000`
- DB migrated: `uv run alembic upgrade head`
- `.env` contains `GITHUB_WEBHOOK_SECRET=testsecret` (optional for local dev — omit to skip HMAC)

---

## Scenario 1: Live commit appears on dashboard (US1 — happy path)

**Goal**: Verify end-to-end flow from webhook to browser in < 5 seconds.

**Steps**:
1. Open `http://localhost:8000/app` in a browser. Confirm the activity feed loads.
2. Observe the "Live" green badge appears in the activity section header (SSE connected).
3. Send a simulated push webhook:
   ```bash
   python tests/fixtures/send_test_webhook.py
   # or with curl:
   curl -s -X POST http://localhost:8000/api/v1/webhooks/github \
     -H "Content-Type: application/json" \
     -H "X-GitHub-Event: push" \
     -d '{
       "ref": "refs/heads/main",
       "repository": {"name": "demo-repo", "full_name": "acme/demo-repo",
                      "default_branch": "main", "owner": {"login": "acme"}},
       "commits": [{
         "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
         "message": "ENG-1 add live stream",
         "timestamp": "2026-05-03T10:00:00Z",
         "url": "https://github.com/acme/demo-repo/commit/aaaa",
         "author": {"name": "Alice", "email": "alice@acme.com", "username": "alice"}
       }]
     }'
   ```
4. **Expected**: Within 5 seconds, a new commit card appears at the top of the activity feed showing `aaaaaaa`, author `alice`, message `ENG-1 add live stream`, and repo `acme/demo-repo`.

---

## Scenario 2: Signature rejected (US2 — security)

**Goal**: Verify HMAC validation rejects tampered payloads.

**Steps**:
1. Set `GITHUB_WEBHOOK_SECRET=testsecret` in `.env`.
2. Send a push webhook with a wrong signature:
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/webhooks/github \
     -H "Content-Type: application/json" \
     -H "X-GitHub-Event: push" \
     -H "X-Hub-Signature-256: sha256=0000000000000000000000000000000000000000000000000000000000000000" \
     -d '{"ref": "refs/heads/main", "repository": {}, "commits": []}'
   ```
3. **Expected**: HTTP 403 response with `{"detail": "Invalid webhook signature"}`. Nothing written to DB.

---

## Scenario 3: Jira key extraction (US2 — cross-linking)

**Goal**: Verify Jira keys in commit messages are stored as links.

**Steps**:
1. Send a webhook with a commit message containing multiple Jira keys:
   ```bash
   # message: "Fixes ENG-12 and ENG-34"
   curl -s -X POST http://localhost:8000/api/v1/webhooks/github \
     -H "Content-Type: application/json" \
     -H "X-GitHub-Event: push" \
     -d '{
       "ref": "refs/heads/main",
       "repository": {"name": "demo", "full_name": "acme/demo",
                      "default_branch": "main", "owner": {"login": "acme"}},
       "commits": [{
         "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
         "message": "Fixes ENG-12 and ENG-34",
         "timestamp": "2026-05-03T11:00:00Z",
         "url": "https://github.com/acme/demo/commit/bbbb",
         "author": {"name": "Bob", "email": "bob@acme.com", "username": "bob"}
       }]
     }'
   ```
2. Query the database:
   ```bash
   sqlite3 data/agent.db "SELECT jira_key FROM github_jira_links WHERE commit_sha LIKE 'bbb%';"
   ```
3. **Expected**: Two rows — `ENG-12` and `ENG-34`.

---

## Scenario 4: Duplicate delivery is idempotent (US2 — robustness)

**Goal**: Verify that resending the same webhook twice creates exactly one commit row.

**Steps**:
1. Send the webhook from Scenario 1 twice (same commit SHA `aaaa...`).
2. Query:
   ```bash
   sqlite3 data/agent.db "SELECT COUNT(*) FROM github_commits WHERE sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';"
   ```
3. **Expected**: Count is `1`.

---

## Scenario 5: Historical feed on page load (US3)

**Goal**: Verify that commits already in the DB appear on first load without a live event.

**Steps**:
1. Ensure commits exist (run Scenario 1 first).
2. Open a new browser tab at `http://localhost:8000/app`.
3. **Expected**: Activity feed shows the commit from Scenario 1 immediately on load, before any new webhook fires.

---

## Scenario 6: SSE reconnects after connection drop (US1 — resilience)

**Goal**: Verify the browser reconnects automatically.

**Steps**:
1. Open dashboard — observe "Live" badge.
2. Stop the server (`Ctrl+C`).
3. Observe: "Live" badge disappears or dims.
4. Restart the server.
5. **Expected**: Within 3 seconds (retry interval), the "Live" badge reappears without a page refresh.
