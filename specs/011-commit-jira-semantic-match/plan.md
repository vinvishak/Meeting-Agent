# Implementation Plan: GitHub Commit to Jira Semantic Matching

**Branch**: `011-commit-jira-semantic-match` | **Date**: 2026-05-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-commit-jira-semantic-match/spec.md`

## Summary

When a GitHub commit arrives (via webhook or periodic sync) and its message contains no explicit Jira ticket ID, the system uses Claude to semantically compare the message against all open Jira tickets and, if a confident match is found, queues a suggestion for the engineer to approve before anything in Jira changes. The core matching logic already exists in `entity_matcher.py` — this feature wires it into the commit ingestion pipeline and extends the `UpdateSuggestion` model to support commit-sourced suggestions.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: `anthropic` (Claude API — already present), `sqlalchemy` 2.x async (existing), `alembic` (existing), `fastapi` (existing)
**Storage**: SQLite — one new Alembic migration (`003_commit_suggestion_source.py`) to extend `update_suggestions`
**Testing**: `pytest` + `pytest-asyncio` — unit tests for the new `commit_matcher.py` module
**Target Platform**: Same single-process uvicorn server on Railway
**Project Type**: Backend feature addition — no frontend changes needed (suggestion queue already exists in dashboard)
**Performance Goals**: Matching adds one Claude API call per untagged commit — acceptable latency for a background task
**Constraints**: Must be idempotent (same commit processed twice = one suggestion); must not raise on AI failure; must not touch Jira without explicit approval
**Scale/Scope**: One new module, one migration, two call sites wired in

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | ✅ PASS | New `commit_matcher.py` has single purpose; existing modules untouched in their core logic |
| II. Single Responsibility | ✅ PASS | `commit_matcher.py` owns commit→suggestion orchestration; `entity_matcher.py` owns the two-stage match; `update_suggester.py` owns transcript suggestions |
| III. Test-First | ✅ PASS | Unit tests for `commit_matcher.py` written before implementation |
| IV. Agent Composability | ✅ PASS | `match_and_suggest_commit` is independently invocable with well-defined inputs/outputs |
| V. Simplicity First | ✅ PASS | Reuse existing matcher and suggestion model; no new abstractions beyond what's needed |

## Project Structure

### Documentation (this feature)

```text
specs/011-commit-jira-semantic-match/
├── plan.md              # This file
├── research.md          # Decision log
├── data-model.md        # Schema changes
├── quickstart.md        # Validation scenarios
├── contracts/
│   └── commit-matcher.md  # commit_matcher module contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (affected files)

```text
src/
├── analysis/
│   └── commit_matcher.py          # NEW — orchestrates match + suggestion creation
├── storage/
│   ├── models.py                  # MODIFY — make transcript_mention_id nullable, add source_type + commit_sha
│   ├── repository.py              # MODIFY — add has_suggestion_for_commit() + create_commit_suggestion()
│   └── migrations/versions/
│       └── 003_commit_suggestion_source.py   # NEW — Alembic migration
├── api/routes/
│   └── webhooks.py                # MODIFY — call match_and_suggest_commit() in _ingest_push()
└── workers/
    └── sync_worker.py             # MODIFY — call match_and_suggest_commit() in _sync_github()

tests/
└── unit/
    └── analysis/
        ├── __init__.py            # NEW
        └── test_commit_matcher.py # NEW — unit tests
```
