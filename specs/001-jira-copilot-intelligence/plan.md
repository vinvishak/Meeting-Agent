# Implementation Plan: Jira-Copilot Engineering Intelligence Agent

**Branch**: `001-jira-copilot-intelligence` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/001-jira-copilot-intelligence/spec.md`

## Summary

Build an AI agent that ingests data every 15 minutes from a Jira MCP Server and a Copilot MCP Server, normalizes it into a unified data store, classifies ticket work status using multi-signal inference, analyzes meeting transcripts to produce auditable Jira update suggestions, and exposes team and executive dashboards plus a natural language query interface.

The system is internal tooling with no formal compliance requirements, best-effort availability, and a target scale of 10 teams with 200+ active tickets each. The MVP is a single deployable Python service with a background sync worker, a REST API, and a minimal web dashboard. All architectural decisions follow the YAGNI principle — SQLite first, polling over streaming, no microservices.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: `anthropic` (Claude API), `mcp` (MCP Python SDK), `fastapi`, `pydantic` v2, `sqlalchemy` 2.x, `rapidfuzz` (entity matching), `apscheduler` (15-min sync scheduler), `pytest` + `pytest-asyncio`  
**Storage**: SQLite (MVP); schema managed with Alembic migrations  
**Testing**: pytest with pytest-asyncio; integration tests against real MCP servers using recorded fixtures  
**Target Platform**: Linux server (internal deployment, single host)  
**Project Type**: Web service + background scheduler (single deployable unit)  
**Performance Goals**: Dashboard standard views load in <5 seconds (SC-007); MCP sync completes within 15-minute window under normal load  
**Constraints**: Internal tooling; best-effort availability (no SLA); 12-month rolling data retention; no external compliance requirements  
**Scale/Scope**: 10 concurrent teams, 200+ active tickets per team, 12-month history

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment | Notes |
|-----------|------------|-------|
| I. Modular & Clean Code | **PASS** | Five top-level concern packages: `ingestion`, `classification`, `analysis`, `velocity`, `api`. No cross-package imports except through well-defined interfaces. |
| II. Single Responsibility | **PASS** | Each package owns exactly one concern. `ingestion` fetches and normalizes only. `classification` infers status only. `analysis` processes transcripts only. `velocity` calculates metrics only. `api` serves HTTP only. |
| III. Test-First | **PASS** | Tasks template enforces red-green-refactor. Integration tests required for all MCP adapter calls and external write operations (Jira updates). |
| IV. Agent Composability | **PASS** | Each MCP adapter is independently invocable. Background workers are runnable as standalone CLI commands. All inter-component I/O uses structured JSON + Pydantic models — no implicit shared state. |
| V. Simplicity First (YAGNI) | **PASS** | SQLite over PostgreSQL; polling over streaming; single-process deployment; no caching layer in MVP. See Complexity Tracking for the one justified deviation. |

**Complexity Tracking**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two-stage ticket reference matching (exact ID + semantic similarity) | Informal references ("the login bug") cannot be resolved by ID match alone; semantic matching is required for the core transcript analysis feature (FR-011) | Single-stage ID-only matching would fail the 80% match accuracy target (SC-002); deferring semantic matching to a later phase would make transcript analysis unshippable as an MVP |

## Project Structure

### Documentation (this feature)

```text
specs/001-jira-copilot-intelligence/
├── plan.md              # This file
├── research.md          # Phase 0: technology decisions and rationale
├── data-model.md        # Phase 1: entity definitions and relationships
├── quickstart.md        # Phase 1: local setup guide
├── contracts/           # Phase 1: API contracts
│   └── rest-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── ingestion/               # MCP data fetching and normalization
│   ├── jira_client.py       # Jira MCP Server adapter (single responsibility: fetch)
│   ├── copilot_client.py    # Copilot MCP Server adapter (single responsibility: fetch)
│   └── normalizer.py        # Entity normalization: cross-system name/email resolution
│
├── classification/          # Work status inference from multi-signal inputs
│   ├── classifier.py        # Assigns one of 5 ticket statuses using weighted signals
│   └── signals.py           # Signal extraction: Jira fields, activity timestamps, mentions
│
├── analysis/                # Transcript processing and Jira update generation
│   ├── transcript_analyzer.py  # Identifies update-relevant passages (progress, blockers, etc.)
│   ├── entity_matcher.py       # Two-stage: exact ID match → semantic similarity match
│   └── update_suggester.py     # Produces UpdateSuggestion records with confidence scores
│
├── velocity/                # Sprint metrics and delivery forecasting
│   ├── calculator.py        # Story points, cycle time, lead time, throughput
│   └── forecaster.py        # Sprint completion forecast + bottleneck detection
│
├── storage/                 # Persistence layer
│   ├── models.py            # SQLAlchemy ORM models (all entities)
│   ├── repository.py        # Data access methods — no business logic
│   └── migrations/          # Alembic migration scripts
│
├── api/                     # FastAPI HTTP layer
│   ├── routes/
│   │   ├── tickets.py       # Work visibility endpoints
│   │   ├── velocity.py      # Metrics and forecast endpoints
│   │   ├── suggestions.py   # Update suggestion review queue endpoints
│   │   ├── reports.py       # Dashboard and portfolio report endpoints
│   │   └── query.py         # Natural language query endpoint
│   └── middleware/
│       └── auth.py          # Permission-aware access enforcement
│
└── workers/                 # Background scheduler
    ├── sync_worker.py       # Orchestrates 15-minute MCP sync cycle
    └── scheduler.py        # APScheduler configuration and job registration

tests/
├── unit/                    # Isolated unit tests per module
├── integration/             # Tests against real or recorded MCP fixtures
└── contract/                # REST API contract conformance tests
```

**Structure Decision**: Single-project layout (Option 1). The feature is a unified backend service with no frontend separation required at MVP stage. Dashboard views are served from the same FastAPI application as static HTML + JSON endpoints. No separate frontend project is warranted until user feedback warrants a richer UI.
