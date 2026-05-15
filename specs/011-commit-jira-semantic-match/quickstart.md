# Quickstart: GitHub Commit to Jira Semantic Matching

## Prerequisites

- Local server running: `uv run uvicorn src.api.app:create_app --factory --port 8000`
- At least one open Jira ticket synced (run a sync cycle first)
- `ANTHROPIC_API_KEY` set in `.env`

---

## Scenario 1 — Semantic match creates a suggestion (happy path)

1. Note the title of one of your open SCRUM tickets (e.g. "Fix mobile login button")
2. Push a commit with a message that describes the same thing without the ticket ID:
   ```bash
   git commit --allow-empty -m "resolved the issue where the login button was not tappable on phone screens"
   git push origin main
   ```
3. Trigger the webhook (or wait for the sync cycle)
4. Check the suggestion queue:
   ```bash
   curl http://localhost:8000/api/v1/suggestions -H "Authorization: Bearer dev"
   ```
5. **Expected**: A suggestion appears linking the commit SHA to the correct SCRUM ticket with `source_type: commit` and `approval_state: pending`

---

## Scenario 2 — Explicit ticket ID skips semantic matching

1. Push a commit that includes the ticket ID explicitly:
   ```bash
   git commit --allow-empty -m "SCRUM-1 updated CI pipeline config"
   git push origin main
   ```
2. Check suggestions after the next sync
3. **Expected**: No new suggestion is created — the explicit ID link goes directly to `github_jira_links`, not the suggestion queue

---

## Scenario 3 — Vague commit message produces no suggestion

1. Push a commit with a generic message:
   ```bash
   git commit --allow-empty -m "minor fix"
   git push origin main
   ```
2. Check suggestions after the next sync
3. **Expected**: No suggestion is created

---

## Scenario 4 — Approve a suggestion

1. Get the suggestion ID from Scenario 1's response
2. Approve it:
   ```bash
   curl -X POST http://localhost:8000/api/v1/suggestions/<id>/approve \
     -H "Authorization: Bearer dev"
   ```
3. **Expected**: `approval_state` changes to `approved`, Jira ticket is updated

---

## Scenario 5 — Duplicate commit delivery is idempotent

1. Repeat Scenario 1 with the same commit SHA (simulate webhook redelivery)
2. **Expected**: Only one suggestion exists for that SHA — no duplicate created
