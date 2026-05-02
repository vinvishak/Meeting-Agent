# Research: Jira Direct REST API Client

**Branch**: `005-jira-rest-api-client` | **Date**: 2026-04-28

## Decision 1: Authentication Method

**Decision**: HTTP Basic Auth with email address + API token, Base64-encoded as `email:token`.

**Rationale**: Jira Cloud REST API v3 requires Basic Auth for personal API tokens. The `Authorization` header takes the form `Basic <base64(email:token)>`. `httpx` handles this natively via `httpx.BasicAuth(email, token)` — no manual encoding needed.

**Alternatives considered**:
- OAuth 2.0 (3-legged): Requires a browser redirect flow — not suitable for a background service.
- OAuth 2.0 (client credentials): Not supported by Jira Cloud for user-scoped data access.

---

## Decision 2: HTTP Client

**Decision**: `httpx.AsyncClient` with `BasicAuth`, reused across all calls within a sync cycle via async context manager.

**Rationale**: `httpx` is already a transitive dependency (via `fastapi`/`starlette`). Using its async client matches the existing async architecture. A single client instance per sync cycle reuses TCP connections efficiently.

**Alternatives considered**:
- `aiohttp`: Would add a new dependency with no benefit over `httpx`.
- `requests` (sync): Incompatible with the async worker architecture.

---

## Decision 3: Pagination

**Decision**: Jira's offset-based pagination via `startAt` + `maxResults` query parameters, fetched in pages of 100 until `total` is reached.

**Rationale**: The Jira Cloud REST API `/rest/api/3/search` endpoint returns `{ issues, startAt, maxResults, total }`. Iterating with `startAt += len(issues)` until `startAt >= total` is the standard pattern and handles all project sizes correctly.

**Alternatives considered**:
- Page size of 50: Unnecessarily slow for large projects; Jira supports up to 100.
- Cursor-based: Not available in Jira Cloud REST API v3.

---

## Decision 4: Retry Strategy

**Decision**: Exponential backoff with up to 3 attempts: waits of 2s, 4s, 8s + up to 30% jitter. Retry on HTTP 429 (rate limit) and 5xx errors only. 401/403/404 are not retried.

**Rationale**: Matches the existing MCP client's retry logic (`_MAX_RETRIES = 3`, `_RETRY_BASE_SECONDS = 2.0`) — preserving identical resilience behaviour while swapping the transport.

**Alternatives considered**:
- Retry on all errors: Would mask auth failures and mask missing resources.
- No retry: Would make the sync worker fragile against transient Jira API blips.

---

## Decision 5: Jira REST API Endpoints Used

| Operation | Endpoint |
|-----------|----------|
| List issues (JQL) | `GET /rest/api/3/search?jql=project={key}&startAt={n}&maxResults=100` |
| Get single issue | `GET /rest/api/3/issue/{issueIdOrKey}` |
| List sprints for board | `GET /rest/agile/1.0/board/{boardId}/sprint` |
| Get comments | `GET /rest/api/3/issue/{issueIdOrKey}/comment` |
| Update issue fields | `PUT /rest/api/3/issue/{issueIdOrKey}` with JSON body |

**Rationale**: These are the same operations the MCP client performed. The Agile REST API (`/rest/agile/1.0/`) is required for sprint data as it is not part of the core v3 API.

---

## Decision 6: Test Mocking Strategy

**Decision**: `respx` library to mock `httpx` at the transport level in unit tests.

**Rationale**: `respx` integrates directly with `httpx.AsyncClient`, allowing precise per-endpoint mocking without patching internals. It produces clear assertion errors when unexpected requests are made, enforcing the test contract.

**Alternatives considered**:
- `unittest.mock.patch`: Too low-level for async HTTP; fragile against implementation changes.
- `pytest-httpx`: Also viable, but `respx` has broader adoption and cleaner API for route-level assertions.
