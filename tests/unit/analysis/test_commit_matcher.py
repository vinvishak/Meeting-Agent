"""Unit tests for src/analysis/commit_matcher.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.commit_matcher import match_and_suggest_commit
from src.analysis.entity_matcher import MatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(has_suggestion: bool = False, active_tickets: list | None = None):
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _make_ticket(jira_id: str = "SCRUM-1", title: str = "Fix login bug", ticket_id: str = "uuid-1"):
    ticket = MagicMock()
    ticket.id = ticket_id
    ticket.jira_id = jira_id
    ticket.title = title
    ticket.status = "In Progress"
    return ticket


# ---------------------------------------------------------------------------
# T005 — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explicit_jira_id_skips_matching():
    """Commit with explicit Jira ID should return False without calling AI."""
    session = AsyncMock()
    with patch("src.analysis.commit_matcher.match_excerpt") as mock_match:
        result = await match_and_suggest_commit(
            session=session,
            sha="a" * 40,
            message="SCRUM-3 fixed the login bug",
            anthropic_client=AsyncMock(),
        )
    assert result is False
    mock_match.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_sha_returns_false():
    """Commit already in suggestion table should return False."""
    session = AsyncMock()
    with (
        patch("src.analysis.commit_matcher.SuggestionRepository.has_suggestion_for_commit", new=AsyncMock(return_value=True)),
        patch("src.analysis.commit_matcher.match_excerpt") as mock_match,
    ):
        result = await match_and_suggest_commit(
            session=session,
            sha="b" * 40,
            message="fixed the login button not tappable on mobile",
            anthropic_client=AsyncMock(),
        )
    assert result is False
    mock_match.assert_not_called()


@pytest.mark.asyncio
async def test_no_active_tickets_returns_false():
    """No open tickets means nothing to match against."""
    session = AsyncMock()
    with (
        patch("src.analysis.commit_matcher.SuggestionRepository.has_suggestion_for_commit", new=AsyncMock(return_value=False)),
        patch("src.analysis.commit_matcher._fetch_active_tickets", new=AsyncMock(return_value=[])),
    ):
        result = await match_and_suggest_commit(
            session=session,
            sha="c" * 40,
            message="fixed the login button",
            anthropic_client=AsyncMock(),
        )
    assert result is False


@pytest.mark.asyncio
async def test_low_confidence_match_returns_false():
    """Match below 0.75 threshold should not create a suggestion."""
    session = AsyncMock()
    ticket = _make_ticket()
    unresolved = MatchResult(ticket_id="", jira_id="", ticket_title="", confidence=0.0, match_type="unresolved")

    with (
        patch("src.analysis.commit_matcher.SuggestionRepository.has_suggestion_for_commit", new=AsyncMock(return_value=False)),
        patch("src.analysis.commit_matcher._fetch_active_tickets", new=AsyncMock(return_value=[ticket])),
        patch("src.analysis.commit_matcher.match_excerpt", new=AsyncMock(return_value=[unresolved])),
        patch("src.analysis.commit_matcher.SuggestionRepository.create_commit_suggestion") as mock_create,
    ):
        result = await match_and_suggest_commit(
            session=session,
            sha="d" * 40,
            message="minor fix",
            anthropic_client=AsyncMock(),
        )
    assert result is False
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_confident_match_creates_suggestion_and_returns_true():
    """High-confidence semantic match should create a suggestion."""
    session = AsyncMock()
    ticket = _make_ticket()
    match = MatchResult(ticket_id="uuid-1", jira_id="SCRUM-1", ticket_title="Fix login bug", confidence=0.92, match_type="semantic")

    with (
        patch("src.analysis.commit_matcher.SuggestionRepository.has_suggestion_for_commit", new=AsyncMock(return_value=False)),
        patch("src.analysis.commit_matcher._fetch_active_tickets", new=AsyncMock(return_value=[ticket])),
        patch("src.analysis.commit_matcher.match_excerpt", new=AsyncMock(return_value=[match])),
        patch("src.analysis.commit_matcher.SuggestionRepository.create_commit_suggestion", new=AsyncMock()) as mock_create,
    ):
        result = await match_and_suggest_commit(
            session=session,
            sha="e" * 40,
            message="fixed the login button not tappable on mobile",
            anthropic_client=AsyncMock(),
        )
    assert result is True


@pytest.mark.asyncio
async def test_ai_unavailable_returns_false_without_raising():
    """AI client unavailable should not raise — just return False."""
    session = AsyncMock()
    ticket = _make_ticket()

    with (
        patch("src.analysis.commit_matcher.SuggestionRepository.has_suggestion_for_commit", new=AsyncMock(return_value=False)),
        patch("src.analysis.commit_matcher._fetch_active_tickets", new=AsyncMock(return_value=[ticket])),
        patch("src.analysis.commit_matcher.match_excerpt", new=AsyncMock(side_effect=Exception("AI unavailable"))),
    ):
        result = await match_and_suggest_commit(
            session=session,
            sha="f" * 40,
            message="fixed the login button",
            anthropic_client=None,
        )
    assert result is False
