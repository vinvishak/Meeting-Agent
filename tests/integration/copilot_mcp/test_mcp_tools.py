"""
Integration tests for the Copilot MCP tools.

These tests exercise the full stack against real Microsoft Graph API endpoints.
They are SKIPPED by default and only run when COPILOT_MCP_INTEGRATION=1 is set,
which requires valid Azure credentials in the environment.

Usage:
    COPILOT_MCP_INTEGRATION=1 uv run pytest tests/integration/copilot_mcp/ -v
"""

from __future__ import annotations

import os

import pytest

# Skip all tests unless the integration flag is explicitly set
pytestmark = pytest.mark.skipif(
    os.getenv("COPILOT_MCP_INTEGRATION") != "1",
    reason="Set COPILOT_MCP_INTEGRATION=1 to run integration tests (requires Azure credentials)",
)


@pytest.fixture(scope="module")
def token() -> str:
    """Acquire a real Graph API token for integration tests."""
    import asyncio

    from src.copilot_mcp.auth import GraphTokenManager
    from src.copilot_mcp.config import get_settings

    settings = get_settings()
    manager = GraphTokenManager(settings)
    return asyncio.run(manager.get_token())


async def test_list_meetings_returns_list(token):
    from src.copilot_mcp.graph_client import MeetingRecord, list_meetings

    results = await list_meetings(token, max_results=5, lookback_days=30)
    assert isinstance(results, list)
    for rec in results:
        assert isinstance(rec, MeetingRecord)
        assert rec.id
        assert rec.started_at is not None
        assert isinstance(rec.participants, list)


async def test_full_pipeline(token):
    """Full pipeline: list_meetings → get_transcript → get_meeting_summary."""
    from src.copilot_mcp.graph_client import (
        MeetingSummaryRecord,
        TranscriptSegment,
        get_meeting_summary,
        get_transcript,
        list_meetings,
    )

    meetings = await list_meetings(token, max_results=5, lookback_days=30)
    if not meetings:
        pytest.skip("No meetings found in lookback window — skipping pipeline test")

    meeting_id = meetings[0].id

    # get_transcript: returns (record, segments) or (None, [])
    record, segments = await get_transcript(token, meeting_id)
    if record is not None:
        assert record.id == meeting_id
        assert isinstance(segments, list)
        for seg in segments:
            assert isinstance(seg, TranscriptSegment)
            assert seg.speaker
            assert seg.text
        if segments:
            # rawTranscript format check
            raw = "".join(f"{s.speaker}: {s.text}\n" for s in segments)
            assert ": " in raw

    # get_meeting_summary: returns MeetingSummaryRecord or None
    summary = await get_meeting_summary(token, meeting_id)
    if summary is not None:
        assert isinstance(summary, MeetingSummaryRecord)
        assert summary.summary
        assert isinstance(summary.action_items, list)
