# Research: Jira-Copilot Engineering Intelligence Agent

**Branch**: `001-jira-copilot-intelligence` | **Date**: 2026-03-31

## 1. MCP Integration Approach

**Decision**: Use the `mcp` Python SDK to connect to both the Jira MCP Server and Copilot MCP Server as MCP clients. Each server exposes a set of tools; the agent calls these tools on a 15-minute poll cycle using APScheduler.

**Rationale**: The MCP Python SDK provides a standardized client interface that abstracts transport details (stdio, SSE, HTTP). Using it ensures that if either MCP server changes transport, the adapter code does not change — only configuration does. This aligns with Constitution Principle IV (Agent Composability).

**Alternatives considered**:
- Direct REST calls to Jira Cloud API: rejected because Jira MCP Server is the specified integration surface; bypassing it would duplicate authentication and mapping logic.
- WebSocket / event-driven ingestion from MCP servers: rejected per YAGNI — polling every 15 minutes meets the freshness requirement (SC-007 is about dashboard load time, not data latency) and avoids streaming infrastructure complexity.

**MCP tool expectations (Jira MCP Server)**:
- `list_issues` / `get_issue`: retrieve ticket fields and transitions
- `list_sprints`: retrieve sprint metadata
- `get_comments`: retrieve issue comments
- `update_issue`: apply approved status, comment, and assignee updates (used only post-approval)

**MCP tool expectations (Copilot MCP Server)**:
- `list_meetings`: retrieve meeting metadata
- `get_transcript`: retrieve full speaker-attributed transcript for a meeting
- `get_meeting_summary`: retrieve Copilot-generated summary and action items

---

## 2. Entity Resolution (Engineer Cross-System Matching)

**Decision**: Two-pass resolution with a canonical `Engineer` store:
1. **Exact match**: email address (preferred — most reliable cross-system identifier)
2. **Fuzzy match**: display name using `rapidfuzz` token sort ratio ≥ 90 threshold

Unresolved identities are flagged at setup as requiring manual mapping. The canonical `Engineer` record stores all known aliases (Jira username, Copilot display name, email).

**Rationale**: Email is the most stable identifier but is not always present in transcript speaker labels. Fuzzy name matching handles the common case (e.g., "Alex Johnson" in Jira vs. "Alex J." in a meeting transcript) without requiring manual mapping for every engineer. A 90% token sort ratio threshold minimizes false positives.

**Alternatives considered**:
- Manual mapping only: too much setup friction; rejected.
- LLM-based disambiguation: high latency and cost for what is a structured matching problem; rejected per YAGNI.

---

## 3. Ticket Reference Matching (Informal Mentions → Jira Tickets)

**Decision**: Two-stage pipeline per transcript segment:

**Stage 1 — Exact ID match**: Regex scan for patterns like `PROJ-123`, `ABC-456`. If matched, confidence = 1.0. Fast and zero-ambiguity.

**Stage 2 — Semantic similarity match** (when Stage 1 fails): Embed the transcript mention and all active ticket titles using the Claude API's embedding capability (or a lightweight local embedding model). Compute cosine similarity. Return best match if similarity ≥ 0.75; assign confidence = similarity score. If below threshold, create an `UnresolvedMention` for manual linking.

**Confidence scoring**:
- Exact ID match: 1.0
- Semantic match ≥ 0.90: high confidence
- Semantic match 0.75–0.89: medium confidence (requires manual approval)
- Below 0.75: unresolved

**Rationale**: The two-stage approach satisfies SC-002 (≥80% match accuracy) without requiring LLM calls for every mention — Stage 1 covers a large fraction of references cheaply.

**Alternatives considered**:
- LLM-only matching with a prompt: accurate but higher latency and cost per transcript; rejected per YAGNI.
- Keyword/BM25 matching: faster than embeddings but less accurate for paraphrased references; may revisit if embedding costs become significant.

---

## 4. Status Inference Logic (Multi-Signal Classification)

**Decision**: Weighted signal scoring that maps each ticket to exactly one of five states.

**Signal weights**:

| Signal | Weight | Notes |
|--------|--------|-------|
| Jira status = "In Progress" (or normalized equivalent) | 3 | Official source of truth |
| Transcript mention within last 2 days | 2 | Strong recency signal |
| Comment added in Jira within last 5 days | 1 | Activity signal |
| Status transition within last 5 days | 1 | Activity signal |
| Jira blocker flag set OR "blocked" in transcript | Override | Always → Blocked |
| No activity across all signals for N days (configurable) | Threshold | → Stale |

**Classification rules** (evaluated in order):
1. If any blocker signal present → **Blocked**
2. If official Jira status = Done → **Completed** (unless transcript suggests otherwise → flag as "Completed but not updated")
3. If total weighted score ≥ 4 → **Officially in progress**
4. If total weighted score 2–3 → **Likely being worked on**
5. If total score < 2 AND last activity > N days ago → **Stale**
6. Else → **Likely being worked on** (low confidence)

Each classification records the contributing signals for FR-007 transparency.

**Rationale**: A weighted scoring model is simple to implement, auditable (each signal is explicit), and configurable (weights can be tuned). Pure rule-based classification without weights was too brittle for edge cases where a ticket has mixed signals.

---

## 5. Update Suggestion Confidence Thresholds

**Decision**: Three confidence tiers derived from transcript analysis:

| Tier | Score Range | Behavior |
|------|-------------|----------|
| High | ≥ 0.90 | Auto-apply if admin has enabled auto-apply; otherwise queued for review |
| Medium | 0.70–0.89 | Always queued for manual review |
| Low | < 0.70 | Surfaced as an observation, not an actionable suggestion |

Conflict detection (multiple participants contradicting on same ticket) overrides all tiers and requires manual resolution regardless of individual statement confidence.

**Rationale**: The 90% threshold for auto-apply is the conservative default specified in Assumptions. Medium-tier suggestions cover the majority of useful updates that can be reviewed and approved with one click. Low-tier are informational only to avoid alert fatigue.

---

## 6. Data Storage: SQLite for MVP

**Decision**: SQLite with SQLAlchemy 2.x ORM and Alembic for schema migrations.

**Rationale**: Internal tooling with best-effort availability and a target of 10 teams / 2,000 active tickets. SQLite handles this volume comfortably and requires no server process, making local development and deployment trivial. The 12-month rolling retention window keeps data volume bounded.

**Migration path**: If the system scales beyond a single host or requires concurrent write throughput beyond SQLite's limits, the SQLAlchemy abstraction layer allows migration to PostgreSQL by changing the connection string and running Alembic migrations — no application logic changes required.

**Alternatives considered**:
- PostgreSQL from the start: unnecessary for MVP scale; adds setup complexity for an internal tool; rejected per YAGNI.
- JSON file storage: not query-friendly for velocity calculations and historical snapshots; rejected.

---

## 7. Natural Language Query Interface

**Decision**: Route natural language queries to the Claude API with a structured tool-use prompt. The system provides Claude with the current data context (filtered, summarized ticket and sprint state) and allows it to call read-only query tools that return structured results. The final answer is rendered as plain language.

**Tool set available to Claude for NL queries** (read-only):
- `get_active_tickets(filters)` — returns filtered ticket list with statuses
- `get_blocked_tickets()` — returns blocked tickets with reasons
- `get_velocity(team, sprint_range)` — returns velocity metrics
- `get_sprint_risk()` — returns at-risk sprint items
- `get_overloaded_engineers()` — returns engineers above load threshold
- `get_transcript_jira_gaps()` — returns tickets discussed but not updated

**Rationale**: Using Claude with tool use keeps the NL interface flexible and maintainable without building a bespoke query parser. The tool set is small and bounded, ensuring read-only safety.

**Alternatives considered**:
- Text-to-SQL approach: fragile for complex joined queries across the entity model; rejected.
- Hardcoded intent classification + query dispatch: inflexible and brittle for open-ended queries; rejected.
