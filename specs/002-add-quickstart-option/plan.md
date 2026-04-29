# Implementation Plan: Add Quickstart Option

**Branch**: `002-add-quickstart-option` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-add-quickstart-option/spec.md`

## Summary

Add a `python -m src.quickstart` command that guides users (interactively or via CLI flags) through environment configuration, connectivity validation, and database initialization — replacing the current multi-step manual process described in the existing quickstart guide. The implementation adds a new `src/quickstart/` package using only stdlib (`argparse`, `getpass`) plus the already-present `httpx`, `anthropic`, and `alembic` dependencies.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: `argparse` (stdlib), `getpass` (stdlib), `httpx` (transitive dep via fastapi), `anthropic` (existing), `alembic` (existing), `pydantic-settings` (existing)
**Storage**: No new persistent storage; existing SQLite DB initialized via Alembic
**Testing**: `pytest` + `pytest-asyncio` (existing)
**Target Platform**: macOS and Linux
**Project Type**: CLI command added to existing service
**Performance Goals**: Setup completes in under 5 minutes (SC-001); connectivity probes time out in ≤5 seconds each
**Constraints**: No new runtime dependencies; Windows support out of scope
**Scale/Scope**: Single-user setup tool; no concurrency requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | ✅ PASS | Each module in `src/quickstart/` has a single purpose |
| II. Single Responsibility | ✅ PASS | `config_schema` owns field definitions, `prompts` owns I/O, `env_writer` owns file ops, `connectivity` owns probes, `db_migrator` owns migrations |
| III. Test-First | ✅ PASS | Tests defined per user story in tasks.md; constitution requires test-first |
| IV. Agent Composability | ✅ PASS | Each sub-module is independently importable and testable |
| V. Simplicity First (YAGNI) | ✅ PASS | stdlib `argparse` over `click`/`typer`; no abstraction layers; no config classes beyond what's needed |

**No violations → Complexity Tracking table not required.**

## Project Structure

### Documentation (this feature)

```text
specs/002-add-quickstart-option/
├── plan.md              # This file
├── research.md          # Library/approach decisions
├── data-model.md        # In-memory entities
├── quickstart.md        # Test scenarios
├── contracts/
│   └── cli.md           # CLI interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code

```text
src/
└── quickstart/
    ├── __init__.py          # Entry point: main() called by python -m src.quickstart
    ├── config_schema.py     # ConfigField dataclass + canonical field list from .env.example
    ├── prompts.py           # Interactive prompt helpers (input / getpass wrappers)
    ├── env_writer.py        # .env parse, merge, and write operations
    ├── connectivity.py      # Per-service HTTP/SDK connectivity probes
    └── db_migrator.py       # Alembic programmatic migration runner

tests/
└── unit/
    └── quickstart/
        ├── test_config_schema.py
        ├── test_env_writer.py
        ├── test_connectivity.py
        └── test_db_migrator.py
```

**Structure Decision**: Single `src/quickstart/` package within the existing project. Each file maps to exactly one of the key entities or concerns from the spec. No sub-packages needed at this scale.

## Implementation Strategy

**MVP = User Story 1** (interactive setup). Stories 2 and 3 extend the same entry point with additive logic, so each is independently deliverable.

- **Phase 3 (US1)**: Interactive setup — config schema, prompts, env_writer, connectivity checks, db migration, entry point wiring
- **Phase 4 (US2)**: Non-interactive mode — argparse flags, `--non-interactive` guard, exit code contract
- **Phase 5 (US3)**: Health check mode — `--check` flag, read-only probe path, no file writes

## Complexity Tracking

> No constitution violations found — table not required.
