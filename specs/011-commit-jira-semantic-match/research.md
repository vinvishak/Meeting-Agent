# Research: GitHub Commit to Jira Semantic Matching

## Decision 1: How to store commit-sourced suggestions

**Decision**: Make `UpdateSuggestion.transcript_mention_id` nullable and add two new columns: `source_type` (enum: `transcript` | `commit`) and `commit_sha` (nullable string).

**Rationale**: The existing `UpdateSuggestion` model has `transcript_mention_id` as NOT NULL, assuming suggestions always come from meeting transcripts. Commit-sourced suggestions have no transcript mention. The simplest fix (Principle V) is to relax the constraint and add a source discriminator column rather than creating a parallel model.

**Alternatives considered**:
- Create a new `CommitSuggestion` model — adds a second table with duplicate approval/audit logic; rejected (violates Principle I)
- Polymorphic FK using SQLAlchemy — complex, speculative abstraction; rejected (violates Principle V)
- Reuse `TranscriptMention` with a fake/sentinel row — fragile hack; rejected

**Migration required**: New Alembic migration `003_commit_suggestion_source.py` — alter `transcript_mention_id` to nullable, add `source_type` and `commit_sha` columns to `update_suggestions`.

---

## Decision 2: Where to call the semantic matcher

**Decision**: Extract a shared `_match_and_suggest_commit(session, sha, message, active_tickets, anthropic_client)` coroutine and call it from both integration points:
1. `_ingest_push` in `webhooks.py` (real-time webhook path)
2. `_sync_github` in `sync_worker.py` (periodic sync path)

**Rationale**: Both paths process commits and need identical matching logic. A shared function satisfies Principles I and II and avoids duplication.

**Alternatives considered**:
- Only match in the webhook path — misses commits pulled via PAT sync; rejected
- Only match in the sync worker — introduces latency for webhook-delivered commits; rejected

---

## Decision 3: Where to put the shared matching function

**Decision**: Add `match_and_suggest_commit()` to a new module `src/analysis/commit_matcher.py`.

**Rationale**: `entity_matcher.py` already owns the two-stage match logic. The new module owns the commit-specific orchestration (fetch active tickets, call matcher, create suggestion). This respects Principle II (single responsibility) and keeps the existing matcher untouched.

---

## Decision 4: Ambiguous match handling

**Decision**: If the top two similarity scores are within 0.10 of each other, treat the result as ambiguous and create no suggestion (same behaviour as below-threshold).

**Rationale**: Matches FR-008 from spec (low-confidence commits silently skipped) and SC-002 (fewer than 10% false positives). A confident match should be clearly better than the runner-up.

---

## Decision 5: Active ticket query

**Decision**: Fetch all tickets with status NOT IN (`Done`, `Closed`, `Resolved`, `Cancelled`) from the existing `tickets` table via `TicketRepository`.

**Rationale**: The tickets table is already synced by the Jira sync worker. No new API calls to Jira are needed at match time.

---

## Decision 6: Duplicate prevention

**Decision**: Before creating a suggestion, check `update_suggestions` for an existing row where `commit_sha = <sha>`. If one exists, skip.

**Rationale**: Satisfies FR-007 (no duplicate suggestions). Webhook redelivery and periodic sync running on the same commit must not create two suggestions.
