# Research: Engineering Intelligence Web Dashboard

**Branch**: `006-web-dashboard` | **Date**: 2026-04-28

## Decision 1: Frontend Approach — Single HTML File vs Framework

**Decision**: Single `frontend/index.html` file with embedded CSS and vanilla JavaScript.

**Rationale**: The spec explicitly requires no build step. Vanilla JS with the Fetch API covers all requirements — data fetching, DOM manipulation, event handling. A single file is trivially served by FastAPI's `StaticFiles` and can be opened directly in a browser. No npm, no bundler, no framework installation.

**Alternatives considered**:
- React/Vue/Svelte: Require a build step (violates constraint) or a CDN import (adds network dependency and complexity).
- Alpine.js via CDN: Lightweight but adds an external dependency and learning curve for no benefit here.
- Multiple .js files: Slightly cleaner code organisation but adds complexity for a single-developer internal tool.

---

## Decision 2: Styling — CSS Framework vs Custom

**Decision**: Custom CSS with CSS custom properties (variables) for theming. No external CSS framework.

**Rationale**: Tailwind and Bootstrap require either a CDN (network dependency) or a build step. A small custom stylesheet fits in under 200 lines for this dashboard scope and avoids all external dependencies. CSS Grid and Flexbox handle the layout requirements natively.

**Alternatives considered**:
- Tailwind CSS CDN: Works without build step but is 3MB+ and encourages class-heavy HTML that's hard to read.
- Bootstrap CDN: Well-known but heavy for this simple layout; adds network dependency.

---

## Decision 3: API Integration — How the Frontend Calls the Backend

**Decision**: A shared `api(path, options)` helper function wraps `fetch()`, injects `Authorization: Bearer dev`, handles JSON parsing, and throws on non-2xx responses. All five sections call this helper.

**Rationale**: Centralising auth and error handling in one place means the token and base URL are configured once. Each section function stays focused on rendering.

**Backend endpoints used**:

| Section | Method | Endpoint |
|---------|--------|----------|
| Tickets | GET | `/api/v1/tickets` |
| Sprint Health | GET | `/api/v1/reports/sprint-health` |
| Org Metrics | GET | `/api/v1/reports/executive-summary` |
| Suggestions | GET | `/api/v1/suggestions` |
| Approve suggestion | POST | `/api/v1/suggestions/{id}/approve` |
| Reject suggestion | POST | `/api/v1/suggestions/{id}/reject` |
| NL Query | POST | `/api/v1/query` |

---

## Decision 4: Serving the Frontend — FastAPI StaticFiles

**Decision**: Mount `frontend/` as a `StaticFiles` directory in `src/api/app.py` at path `/app`. The dashboard is then accessible at `http://localhost:8000/app/index.html`.

**Rationale**: FastAPI has built-in `StaticFiles` support via `starlette`. Adding one line to `app.py` serves the entire `frontend/` directory with no additional server setup.

**Alternatives considered**:
- Serve as a separate static file server (e.g. `python -m http.server`): Works but requires a second terminal and CORS configuration.
- Inline the dashboard into a FastAPI route: Mixes concerns; harder to edit the HTML.

---

## Decision 5: Status Badge Colours

**Decision**: Colour-coded pill badges for inferred status values:

| Status | Colour |
|--------|--------|
| `likely_in_progress` | Blue |
| `stale` | Orange |
| `blocked` | Red |
| `done` / `completed` | Green |
| `open` / `to_do` | Grey |

**Rationale**: Traffic-light convention (red = problem, orange = warning, green = good, blue = active) is universally understood without a legend. Grey for neutral/open states avoids false urgency.
