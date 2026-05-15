# Data Model: GitHub Commit to Jira Semantic Matching

## Changed Entity: UpdateSuggestion

**Table**: `update_suggestions`

### New / Changed Columns

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| `transcript_mention_id` | FK → transcript_mentions | **NOW NULLABLE** | NULL | Link to transcript mention (NULL for commit-sourced suggestions) |
| `source_type` | VARCHAR(20) | NOT NULL | `'transcript'` | Discriminator: `transcript` or `commit` |
| `commit_sha` | VARCHAR(40) | NULLABLE | NULL | SHA of the GitHub commit that produced this suggestion |

### Existing Columns (unchanged)

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID PK | Primary key |
| `ticket_id` | FK → tickets | The matched Jira ticket |
| `update_type` | VARCHAR(30) | Type of proposed Jira change |
| `proposed_value` | JSON | The proposed change payload |
| `confidence_score` | FLOAT | Match confidence (0.0–1.0) |
| `confidence_tier` | VARCHAR(10) | `high` / `medium` / `low` |
| `approval_state` | VARCHAR(20) | `pending` / `approved` / `rejected` |
| `reviewed_by_id` | FK → engineers | Who reviewed it |
| `reviewed_at` | TIMESTAMP | When reviewed |
| `created_at` | TIMESTAMP | When created |

### Constraints

- `commit_sha` MUST be set when `source_type = 'commit'`
- `transcript_mention_id` MUST be set when `source_type = 'transcript'`
- One suggestion per `commit_sha` (unique constraint on `commit_sha` where not NULL)

---

## Migration

**File**: `src/storage/migrations/versions/003_commit_suggestion_source.py`

Changes:
1. ALTER `update_suggestions.transcript_mention_id` → nullable
2. ADD COLUMN `update_suggestions.source_type` VARCHAR(20) NOT NULL DEFAULT 'transcript'
3. ADD COLUMN `update_suggestions.commit_sha` VARCHAR(40) NULLABLE
4. ADD UNIQUE INDEX on `commit_sha` (partial — where not NULL)

---

## New Module: CommitMatchResult (internal dataclass, no DB table)

Used internally by `src/analysis/commit_matcher.py` to pass results between functions.

| Field | Type | Purpose |
|-------|------|---------|
| `commit_sha` | str | The commit being matched |
| `commit_message` | str | The message used as input |
| `matched_ticket_id` | str | Internal DB UUID of matched ticket |
| `matched_jira_id` | str | e.g. `SCRUM-3` |
| `confidence` | float | 0.0–1.0 |
| `match_type` | str | `semantic` or `unresolved` |
