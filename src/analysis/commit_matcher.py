"""
Orchestrate semantic matching of a GitHub commit message against active Jira tickets.

Public API:
    match_and_suggest_commit(session, sha, message, anthropic_client) -> bool

Returns True if a suggestion was created, False otherwise.
See specs/011-commit-jira-semantic-match/contracts/commit-matcher.md for the full contract.
"""

import re

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.analysis.entity_matcher import match_excerpt
from src.logging_config import get_logger
from src.storage.models import Ticket
from src.storage.repository import SuggestionRepository

logger = get_logger(__name__)

_JIRA_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_AMBIGUITY_GAP = 0.10
_DONE_STATUSES = {"done", "closed", "resolved", "cancelled", "won't do", "duplicate"}


async def _fetch_active_tickets(session: AsyncSession) -> list[Ticket]:
    result = await session.execute(select(Ticket))
    tickets = list(result.scalars().all())
    return [t for t in tickets if t.jira_status.lower() not in _DONE_STATUSES]


def _confidence_tier(score: float) -> str:
    if score >= 0.90:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


async def match_and_suggest_commit(
    session: AsyncSession,
    sha: str,
    message: str,
    anthropic_client: AsyncAnthropic | None,
) -> bool:
    # Skip if message already contains an explicit Jira ID (exact path handles it)
    if _JIRA_ID_RE.search(message):
        return False

    # Idempotency check — never create two suggestions for the same commit
    if await SuggestionRepository.has_suggestion_for_commit(session, sha):
        return False

    active_tickets = await _fetch_active_tickets(session)
    if not active_tickets:
        return False

    try:
        results = await match_excerpt(message, active_tickets, anthropic_client)
    except Exception as exc:
        logger.warning("Semantic match failed for commit %s: %s", sha[:8], exc)
        return False

    if not results:
        return False

    best = results[0]
    if best.confidence == 0.0 or not best.ticket_id:
        return False

    # Ambiguity guard — if runner-up is within 0.10 of the best, skip
    if len(results) > 1 and (best.confidence - results[1].confidence) <= _AMBIGUITY_GAP:
        logger.debug("Ambiguous commit match for %s — skipping suggestion", sha[:8])
        return False

    await SuggestionRepository.create_commit_suggestion(
        session=session,
        sha=sha,
        ticket_id=best.ticket_id,
        confidence=best.confidence,
        confidence_tier=_confidence_tier(best.confidence),
    )
    logger.info(
        "Commit %s semantically matched to %s (confidence %.0f%%)",
        sha[:8], best.jira_id, best.confidence * 100,
    )
    return True
