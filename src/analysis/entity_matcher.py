"""
Two-stage ticket entity matcher.

Stage 1 — Exact ID match: regex scan for `[A-Z]+-\d+` patterns in the
excerpt. Confidence = 1.0, match_type = exact_id.

Stage 2 — Semantic similarity (when Stage 1 yields no match): uses the
Claude API to rate how likely the excerpt refers to each active ticket by
title. Returns the best match above the 0.75 threshold; assigns
match_type = semantic and confidence = the rated score.

Excerpts that produce no match above threshold are returned as
match_type = unresolved, confidence = 0.0.

Usage:
    matches = await match_excerpt(excerpt, active_tickets, anthropic_client)
"""

import json
import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from src.logging_config import get_logger
from src.storage.models import MatchType, Ticket

logger = get_logger(__name__)

_JIRA_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

_SEMANTIC_THRESHOLD = 0.75
_SEMANTIC_HIGH = 0.90

# Limit how many tickets we send to Claude per excerpt to control cost
_MAX_CANDIDATES = 20


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    ticket_id: str        # internal DB UUID
    jira_id: str          # e.g. "PROJ-123"
    ticket_title: str
    confidence: float
    match_type: str       # MatchType value


# ---------------------------------------------------------------------------
# Stage 1 — exact ID regex scan
# ---------------------------------------------------------------------------


def _extract_exact_ids(excerpt: str) -> list[str]:
    """Return all Jira-style IDs mentioned in the excerpt (e.g. ['PROJ-123'])."""
    return _JIRA_ID_RE.findall(excerpt)


# ---------------------------------------------------------------------------
# Stage 2 — Claude semantic similarity
# ---------------------------------------------------------------------------

_SIMILARITY_PROMPT = """\
You are a semantic similarity assistant. Given a transcript excerpt and a list of
Jira ticket titles, identify which ticket the excerpt is most likely referring to.

Return JSON with this exact structure:
{{
  "matches": [
    {{"jira_id": "PROJ-123", "similarity": 0.95}},
    {{"jira_id": "PROJ-456", "similarity": 0.12}}
  ]
}}

Only include tickets with similarity > 0.0. Order by similarity descending.
Similarity is a float 0.0–1.0 where 1.0 = definitely referring to this ticket.

Excerpt:
{excerpt}

Tickets:
{tickets_json}"""


async def _semantic_match(
    excerpt: str,
    candidates: list[Ticket],
    client: AsyncAnthropic,
) -> list[tuple[str, float]]:  # list of (jira_id, similarity)
    """Ask Claude to score similarity between excerpt and candidate ticket titles."""
    if not candidates:
        return []

    tickets_json = json.dumps(
        [{"jira_id": t.jira_id, "title": t.title} for t in candidates[:_MAX_CANDIDATES]]
    )

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": _SIMILARITY_PROMPT.format(
                        excerpt=excerpt[:500],  # truncate for cost control
                        tickets_json=tickets_json,
                    ),
                }
            ],
        )
        raw = response.content[0].text  # type: ignore[union-attr]
        # Extract JSON from the response (may have surrounding text)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return []
        data = json.loads(raw[start:end])
        return [(m["jira_id"], float(m["similarity"])) for m in data.get("matches", [])]
    except Exception as exc:
        logger.warning("Semantic matching failed for excerpt: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def match_excerpt(
    excerpt: str,
    active_tickets: list[Ticket],
    anthropic_client: AsyncAnthropic | None,
) -> list[MatchResult]:
    """
    Match an excerpt against active tickets using two stages.

    Returns a list of MatchResults. An unresolved result (no match found)
    has match_type=unresolved and confidence=0.0 with empty ticket fields.
    """
    if not excerpt.strip():
        return []

    # Build a lookup by jira_id for fast access
    ticket_by_jira_id = {t.jira_id: t for t in active_tickets}

    # ------------------------------------------------------------------
    # Stage 1 — exact ID match
    # ------------------------------------------------------------------
    exact_ids = _extract_exact_ids(excerpt)
    stage1_results: list[MatchResult] = []
    for jira_id in exact_ids:
        ticket = ticket_by_jira_id.get(jira_id)
        if ticket:
            stage1_results.append(
                MatchResult(
                    ticket_id=ticket.id,
                    jira_id=jira_id,
                    ticket_title=ticket.title,
                    confidence=1.0,
                    match_type=MatchType.exact_id.value,
                )
            )
        else:
            # Known ID pattern but ticket not in active set — still record it
            stage1_results.append(
                MatchResult(
                    ticket_id="",
                    jira_id=jira_id,
                    ticket_title="",
                    confidence=1.0,
                    match_type=MatchType.exact_id.value,
                )
            )

    if stage1_results:
        return stage1_results

    # ------------------------------------------------------------------
    # Stage 2 — semantic similarity (requires Anthropic client)
    # ------------------------------------------------------------------
    if anthropic_client is None or not active_tickets:
        return [
            MatchResult(ticket_id="", jira_id="", ticket_title="", confidence=0.0, match_type=MatchType.unresolved.value)
        ]

    similarities = await _semantic_match(excerpt, active_tickets, anthropic_client)
    if not similarities:
        return [
            MatchResult(ticket_id="", jira_id="", ticket_title="", confidence=0.0, match_type=MatchType.unresolved.value)
        ]

    # Sort and filter by threshold
    similarities.sort(key=lambda x: x[1], reverse=True)
    best_jira_id, best_score = similarities[0]

    if best_score >= _SEMANTIC_THRESHOLD:
        ticket = ticket_by_jira_id.get(best_jira_id)
        if ticket:
            return [
                MatchResult(
                    ticket_id=ticket.id,
                    jira_id=best_jira_id,
                    ticket_title=ticket.title,
                    confidence=best_score,
                    match_type=MatchType.semantic.value,
                )
            ]

    # Below threshold — unresolved
    return [
        MatchResult(ticket_id="", jira_id="", ticket_title="", confidence=0.0, match_type=MatchType.unresolved.value)
    ]
