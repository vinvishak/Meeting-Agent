# Research: Fix Dashboard API Base URL

## Decision: Use empty string as API_BASE

**Decision**: Set `API_BASE = ''` (empty string)

**Rationale**: When `API_BASE` is an empty string, every `fetch(API_BASE + path)` call becomes `fetch('/api/v1/...')` — a relative URL. The browser resolves relative URLs against the page's own origin automatically. This works on `http://localhost:8000`, `https://meeting-agent-production-d7e6.up.railway.app`, or any other host, with zero configuration.

**Alternatives considered**:

- `window.location.origin` — explicit but redundant; the browser already does this for relative URLs
- Environment variable injection at build time — requires a build pipeline; this project has no bundler
- Server-side template rendering to inject the URL — unnecessary complexity; same result as empty string
