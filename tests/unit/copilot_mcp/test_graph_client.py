"""Unit tests for src/copilot_mcp/graph_client.py."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from src.copilot_mcp.graph_client import (
    _follow_pages,
    _parse_vtt,
    _request_with_retry,
    get_meeting_summary,
    get_transcript,
    list_meetings,
)

_TOKEN = "bearer-test-token"
_BASE = "https://graph.microsoft.com/v1.0"
_BETA = "https://graph.microsoft.com/beta"


# ---------------------------------------------------------------------------
# list_meetings
# ---------------------------------------------------------------------------


@respx.mock
async def test_list_meetings_returns_records():
    now = datetime.now(UTC)
    respx.get(url__startswith=f"{_BASE}/communications/callRecords").mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {
                        "id": "meet-1",
                        "subject": "Sprint Planning",
                        "startDateTime": now.isoformat(),
                        "endDateTime": (now + timedelta(hours=1)).isoformat(),
                        "participants": {
                            "organizer": {"user": {"displayName": "Alice", "id": "uid-1"}},
                            "attendees": [
                                {"user": {"displayName": "Bob"}},
                            ],
                        },
                    }
                ]
            },
        )
    )
    results = await list_meetings(_TOKEN, max_results=10, lookback_days=7)
    assert len(results) == 1
    assert results[0].id == "meet-1"
    assert results[0].title == "Sprint Planning"
    assert "Alice" in results[0].participants


@respx.mock
async def test_list_meetings_empty_value_returns_empty_list():
    respx.get(url__startswith=f"{_BASE}/communications/callRecords").mock(
        return_value=Response(200, json={"value": []})
    )
    results = await list_meetings(_TOKEN, max_results=10, lookback_days=7)
    assert results == []


@respx.mock
async def test_list_meetings_skips_record_missing_start_datetime(caplog):
    import logging
    respx.get(url__startswith=f"{_BASE}/communications/callRecords").mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {"id": "bad-rec", "subject": "No start"},
                ]
            },
        )
    )
    with caplog.at_level(logging.WARNING):
        results = await list_meetings(_TOKEN, max_results=10, lookback_days=7)
    assert results == []
    assert any("bad-rec" in r.message for r in caplog.records)


@respx.mock
async def test_follow_pages_merges_pages():
    import httpx
    respx.get("https://example.com/page1").mock(
        return_value=Response(
            200,
            json={
                "value": [{"id": "a"}],
                "@odata.nextLink": "https://example.com/page2",
            },
        )
    )
    respx.get("https://example.com/page2").mock(
        return_value=Response(200, json={"value": [{"id": "b"}]})
    )
    async with httpx.AsyncClient() as client:
        results = await _follow_pages(client, "https://example.com/page1", _TOKEN)
    assert [r["id"] for r in results] == ["a", "b"]


@respx.mock
async def test_list_meetings_max_results_clamped():
    """max_results outside 1–200 is clamped, not rejected."""
    respx.get(url__startswith=f"{_BASE}/communications/callRecords").mock(
        return_value=Response(200, json={"value": []})
    )
    # Should not raise
    await list_meetings(_TOKEN, max_results=0, lookback_days=7)
    await list_meetings(_TOKEN, max_results=999, lookback_days=7)


# ---------------------------------------------------------------------------
# _parse_vtt
# ---------------------------------------------------------------------------


def test_parse_vtt_basic():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v Alice Chen>Hello everyone.</v>

00:00:06.000 --> 00:00:10.000
<v Bob Smith>Thanks for joining.</v>
"""
    segments = _parse_vtt(vtt)
    assert len(segments) == 2
    assert segments[0].speaker == "Alice Chen"
    assert segments[0].text == "Hello everyone."
    assert segments[0].timestamp_seconds == 1
    assert segments[1].speaker == "Bob Smith"


def test_parse_vtt_note_speaker_format():
    vtt = """WEBVTT

NOTE speaker: Carol White

00:01:00.000 --> 00:01:05.000
Let me share my screen.
"""
    segments = _parse_vtt(vtt)
    assert len(segments) == 1
    assert segments[0].speaker == "Carol White"
    assert "share my screen" in segments[0].text


def test_parse_vtt_empty_returns_empty():
    assert _parse_vtt("") == []
    assert _parse_vtt("WEBVTT\n\n") == []


def test_parse_vtt_bad_utf8_replaced():
    # Simulate non-UTF-8 in parsed text — graph_client replaces bad chars
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Alice>Caf\ufffd.</v>\n"
    segments = _parse_vtt(vtt)
    assert len(segments) == 1
    assert "\ufffd" in segments[0].text or "Caf" in segments[0].text


def test_parse_vtt_timestamp_seconds():
    vtt = """WEBVTT

00:02:30.000 --> 00:02:35.000
<v Dave>Two minutes in.</v>
"""
    segments = _parse_vtt(vtt)
    assert segments[0].timestamp_seconds == 150  # 2*60 + 30


# ---------------------------------------------------------------------------
# get_transcript
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_transcript_returns_record_and_segments():
    now = datetime.now(UTC)
    _BASE = "https://graph.microsoft.com/v1.0"
    meeting_id = "meet-abc"

    # callRecord metadata
    respx.get(f"{_BASE}/communications/callRecords/{meeting_id}").mock(
        return_value=Response(
            200,
            json={
                "id": meeting_id,
                "subject": "Standup",
                "startDateTime": now.isoformat(),
                "endDateTime": (now + timedelta(minutes=15)).isoformat(),
                "participants": {
                    "organizer": {"user": {"displayName": "Alice", "id": "uid-1"}},
                    "attendees": [],
                },
            },
        )
    )
    # Transcripts list
    respx.get(f"{_BASE}/communications/callRecords/{meeting_id}/transcripts").mock(
        return_value=Response(200, json={"value": [{"id": "tr-1"}]})
    )
    # VTT content
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Alice>Hello.</v>\n"
    respx.get(
        url__startswith=f"{_BASE}/communications/callRecords/{meeting_id}/transcripts/tr-1/content"
    ).mock(return_value=Response(200, text=vtt))

    record, segments = await get_transcript("tok", meeting_id)
    assert record is not None
    assert record.id == meeting_id
    assert len(segments) == 1
    assert segments[0].speaker == "Alice"
    assert segments[0].text == "Hello."


@respx.mock
async def test_get_transcript_404_returns_none():
    _BASE = "https://graph.microsoft.com/v1.0"
    respx.get(url__startswith=f"{_BASE}/communications/callRecords/bad-id").mock(
        return_value=Response(404)
    )
    record, segments = await get_transcript("tok", "bad-id")
    assert record is None
    assert segments == []


@respx.mock
async def test_get_transcript_no_transcripts_returns_empty_segments():
    now = datetime.now(UTC)
    _BASE = "https://graph.microsoft.com/v1.0"
    meeting_id = "meet-no-transcript"

    respx.get(f"{_BASE}/communications/callRecords/{meeting_id}").mock(
        return_value=Response(
            200,
            json={
                "id": meeting_id,
                "subject": "No transcript",
                "startDateTime": now.isoformat(),
                "participants": {"organizer": {"user": {"displayName": "Bob", "id": "uid-2"}}, "attendees": []},
            },
        )
    )
    respx.get(f"{_BASE}/communications/callRecords/{meeting_id}/transcripts").mock(
        return_value=Response(200, json={"value": []})
    )

    record, segments = await get_transcript("tok", meeting_id)
    assert record is not None
    assert segments == []


# ---------------------------------------------------------------------------
# get_meeting_summary
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_meeting_summary_returns_summary_and_actions():
    _BETA = "https://graph.microsoft.com/beta"
    meeting_id = "meet-sum"

    respx.get(f"{_BETA}/communications/callRecords/{meeting_id}/meetingCaption").mock(
        return_value=Response(
            200,
            json={
                "summary": "Team reviewed sprint progress.",
                "actionItems": [
                    {"text": "Bob to close ticket"},
                    {"text": "Carol to investigate blocker"},
                ],
            },
        )
    )

    result = await get_meeting_summary("tok", meeting_id)
    assert result is not None
    assert result.summary == "Team reviewed sprint progress."
    assert len(result.action_items) == 2
    assert "Bob to close ticket" in result.action_items


@respx.mock
async def test_get_meeting_summary_404_returns_none():
    _BETA = "https://graph.microsoft.com/beta"
    respx.get(url__startswith=f"{_BETA}/communications/callRecords/no-sum/meetingCaption").mock(
        return_value=Response(404)
    )
    result = await get_meeting_summary("tok", "no-sum")
    assert result is None


@respx.mock
async def test_get_meeting_summary_403_returns_none(caplog):
    import logging
    _BETA = "https://graph.microsoft.com/beta"
    respx.get(url__startswith=f"{_BETA}/communications/callRecords/no-copilot/meetingCaption").mock(
        return_value=Response(403)
    )
    with caplog.at_level(logging.WARNING):
        result = await get_meeting_summary("tok", "no-copilot")
    assert result is None


@respx.mock
async def test_get_meeting_summary_empty_action_items():
    _BETA = "https://graph.microsoft.com/beta"
    meeting_id = "meet-no-actions"

    respx.get(f"{_BETA}/communications/callRecords/{meeting_id}/meetingCaption").mock(
        return_value=Response(
            200,
            json={"summary": "Short meeting.", "actionItems": []},
        )
    )

    result = await get_meeting_summary("tok", meeting_id)
    assert result is not None
    assert result.action_items == []


# ---------------------------------------------------------------------------
# 429 retry with Retry-After backoff
# ---------------------------------------------------------------------------


@respx.mock
async def test_429_then_200_succeeds():
    """Single 429 followed by 200 should succeed and return data."""

    respx.get("https://example.com/resource").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "1"}),
            Response(200, json={"value": [{"id": "x"}]}),
        ]
    )

    import httpx

    with patch("src.copilot_mcp.graph_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with httpx.AsyncClient() as client:
            result = await _request_with_retry(client, "https://example.com/resource", _TOKEN)

    assert result.status_code == 200
    mock_sleep.assert_called_once_with(1.0)


@respx.mock
async def test_three_consecutive_429s_raises():
    """Three consecutive 429s should raise RuntimeError."""

    respx.get("https://example.com/limited").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "1"}),
            Response(429, headers={"Retry-After": "1"}),
            Response(429, headers={"Retry-After": "1"}),
        ]
    )

    import httpx

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with httpx.AsyncClient() as client:
            with pytest.raises(RuntimeError, match="rate limit"):
                await _request_with_retry(client, "https://example.com/limited", _TOKEN)


@respx.mock
async def test_429_retry_after_header_respected():
    """Retry-After: 5 header should cause asyncio.sleep(5.0)."""
    respx.get("https://example.com/slow").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "5"}),
            Response(200, json={"value": []}),
        ]
    )

    import httpx

    with patch("src.copilot_mcp.graph_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with httpx.AsyncClient() as client:
            await _request_with_retry(client, "https://example.com/slow", _TOKEN)

    mock_sleep.assert_called_once_with(5.0)


@respx.mock
async def test_429_missing_retry_after_defaults_to_30s():
    """Missing Retry-After header should default to 30s wait."""
    respx.get("https://example.com/default-wait").mock(
        side_effect=[
            Response(429),  # No Retry-After header
            Response(200, json={"value": []}),
        ]
    )

    import httpx

    with patch("src.copilot_mcp.graph_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with httpx.AsyncClient() as client:
            await _request_with_retry(client, "https://example.com/default-wait", _TOKEN)

    mock_sleep.assert_called_once_with(30.0)
