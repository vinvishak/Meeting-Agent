# Contract: Commit Matcher Module

**Module**: `src/analysis/commit_matcher.py`
**Purpose**: Orchestrate semantic matching of a GitHub commit message against active Jira tickets and persist the resulting suggestion.

---

## Public Function: `match_and_suggest_commit`

```
match_and_suggest_commit(
    session: AsyncSession,
    sha: str,
    message: str,
    anthropic_client: AsyncAnthropic | None,
) -> bool
```

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | AsyncSession | Active DB session (caller commits) |
| `sha` | str | 40-char GitHub commit SHA |
| `message` | str | Full commit message |
| `anthropic_client` | AsyncAnthropic or None | Claude client; None disables semantic stage |

### Outputs

| Return | Meaning |
|--------|---------|
| `True` | A suggestion was created |
| `False` | No suggestion created (exact ID found, low confidence, ambiguous, duplicate, or AI unavailable) |

### Behaviour Contract

1. If `message` contains an explicit Jira ID pattern (`[A-Z]+-\d+`) → return `False` immediately (exact ID path handles it)
2. If a suggestion for `sha` already exists → return `False` (idempotent)
3. Fetch all active tickets (status not in Done/Closed/Resolved/Cancelled)
4. If no active tickets → return `False`
5. Call `match_excerpt(message, active_tickets, anthropic_client)`
6. If result is `unresolved` or confidence < 0.75 → return `False`
7. If top two scores within 0.10 of each other → return `False` (ambiguous)
8. Create `UpdateSuggestion` with `source_type='commit'`, `commit_sha=sha`, `approval_state='pending'`
9. Return `True`

### Error Handling

- If the AI service is unavailable: log a warning, return `False` — do NOT raise
- If DB write fails: propagate the exception to the caller

---

## Integration Points

### Called from: `src/api/routes/webhooks.py` — `_ingest_push()`

After storing a commit, call `match_and_suggest_commit` for each commit in the push payload.

### Called from: `src/workers/sync_worker.py` — `_sync_github()`

After upserting each commit, call `match_and_suggest_commit` for each new commit (skip existing ones via the idempotency check inside the function).
