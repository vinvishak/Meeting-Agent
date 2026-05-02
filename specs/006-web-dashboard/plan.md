# Implementation Plan: Engineering Intelligence Web Dashboard

**Branch**: `006-web-dashboard` | **Date**: 2026-04-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-web-dashboard/spec.md`

## Summary

Build a single-file HTML/CSS/JS dashboard (`frontend/index.html`) that connects to the existing FastAPI backend on `localhost:8000`. The dashboard has five sections — tickets, sprint health, org metrics, AI suggestions, and NL query — each fetching from a dedicated backend endpoint. No build step, no framework, no dependencies beyond the browser.

## Technical Context

**Language/Version**: HTML5, CSS3, vanilla JavaScript (ES2022)
**Primary Dependencies**: None — no npm, no bundler, no framework. Fetch API for HTTP, CSS custom properties for theming.
**Storage**: None — all data comes from the backend API; no client-side persistence needed
**Testing**: Manual browser testing against live backend; no automated frontend test suite for v1
**Target Platform**: Desktop browser (Chrome, Firefox, Safari) at 1280×800+
**Project Type**: Single-page web application served as a static file by the existing FastAPI server
**Performance Goals**: Initial render under 2 seconds; each section's data loads under 2 seconds
**Constraints**: No build step; must work as a static file served by FastAPI at `/app`
**Scale/Scope**: Single internal user; ~100 tickets in initial deployment

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular & Clean Code | PASS | Each dashboard section is a self-contained function with its own fetch, render, and error handler |
| II. Single Responsibility | PASS | Each section owns one concern; shared utilities (api(), badge()) used in 3+ places |
| III. Test-First | PASS (relaxed) | Manual testing against live backend is sufficient for a single-file internal UI in v1 |
| IV. Agent Composability | PASS | Dashboard is a pure consumer; no composability requirements |
| V. Simplicity First | PASS | Vanilla JS + single HTML file is the simplest viable approach |

**Post-design re-check**: No violations. No Complexity Tracking entry required.

## Project Structure

### Documentation (this feature)

```text
specs/006-web-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-sections.md
└── tasks.md
```

### Source Code

```text
frontend/
└── index.html        # Single file: HTML + embedded CSS + embedded JS

src/api/
└── app.py            # Add StaticFiles mount to serve frontend/ at /app
```
