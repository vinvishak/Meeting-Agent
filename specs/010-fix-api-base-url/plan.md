# Implementation Plan: Fix Dashboard API Base URL

**Branch**: `010-fix-api-base-url` | **Date**: 2026-05-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-fix-api-base-url/spec.md`

## Summary

The dashboard hardcodes `http://localhost:8000` as the API base URL, causing every API call to fail when the app is deployed to any remote host. The fix is to replace the hardcoded value with an empty string so the browser resolves all API paths relative to the page's own origin — which works identically in local development and production without any configuration.

## Technical Context

**Language/Version**: HTML5 / JavaScript ES2022 (vanilla, no bundler)
**Primary Dependencies**: None — browser `fetch` API only
**Storage**: N/A
**Testing**: Manual browser verification (no JS unit test framework in this project)
**Target Platform**: Any browser, any deployment host
**Project Type**: Frontend single-file dashboard
**Performance Goals**: No impact — this is a URL string change
**Constraints**: Must not break local development; no build step available to inject env vars
**Scale/Scope**: Single file — `frontend/index.html`

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | ✅ PASS | Single-purpose change, no side effects |
| II. Single Responsibility | ✅ PASS | One constant changed, one concern fixed |
| III. Test-First | ⚠️ WARN | No JS unit test framework exists in the project; manual browser verification is the only available test method. Documented in Complexity Tracking. |
| IV. Agent Composability | ✅ PASS | Not applicable to frontend constants |
| V. Simplicity First | ✅ PASS | Empty string is the simplest correct solution — zero new abstractions |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Principle III (Test-First) skipped | No JS unit test framework exists in this project; adding one is out of scope for a one-line fix | Setting up a test framework would be disproportionate complexity for a single constant change; manual browser verification against both local and Railway environments provides sufficient coverage |

## Project Structure

### Documentation (this feature)

```text
specs/010-fix-api-base-url/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (affected file only)

```text
frontend/
└── index.html           # Line: const API_BASE = 'http://localhost:8000'  →  ''
```

No backend changes. No new files.
