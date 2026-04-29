"""
Microsoft Graph API client for Teams meeting data.

Provides list_meetings, get_transcript, and get_meeting_summary functions.
All functions are async and accept a bearer token string.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

_BASE = "https://graph.microsoft.com/v1.0"
_BETA = "https://graph.microsoft.com/beta"
_MAX_RESULTS_MIN = 1
_MAX_RESULTS_MAX = 200

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory types
# ---------------------------------------------------------------------------


@dataclass
class MeetingRecord:
    id: str
    title: str | None
    started_at: datetime
    ended_at: datetime | None
    participants: list[str]
    organizer_id: str | None = None


@dataclass
class TranscriptSegment:
    speaker: str
    text: str
    timestamp_seconds: int | None


@dataclass
class MeetingSummaryRecord:
    summary: str
    action_items: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_RETRY_DEFAULT_WAIT = 30.0
_RETRY_MAX_ATTEMPTS = 3


async def _request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    token: str,
) -> httpx.Response:
    """GET *url* with automatic 429 retry (up to _RETRY_MAX_ATTEMPTS total attempts).

    On HTTP 429, waits Retry-After seconds (default 30) then retries.
    Raises RuntimeError after exhausting all attempts.
    """
    for attempt in range(_RETRY_MAX_ATTEMPTS):
        resp = await client.get(url, headers=_auth_headers(token))
        if resp.status_code != 429:
            return resp
        wait = float(resp.headers.get("Retry-After", _RETRY_DEFAULT_WAIT))
        log.warning("HTTP 429 on %s — retrying after %.0fs (attempt %d/%d)", url, wait, attempt + 1, _RETRY_MAX_ATTEMPTS)
        await asyncio.sleep(wait)

    raise RuntimeError(f"Graph API rate limit exceeded after retries: {url}")


async def _follow_pages(client: httpx.AsyncClient, url: str, token: str) -> list[dict[str, Any]]:
    """Fetch all items from a paged Graph API response, following @odata.nextLink."""
    items: list[dict[str, Any]] = []
    next_url: str | None = url
    while next_url:
        resp = await _request_with_retry(client, next_url, token)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        next_url = data.get("@odata.nextLink")
    return items


def _parse_participants(raw: dict[str, Any]) -> tuple[list[str], str | None]:
    """Extract participant display names and organiser ID from a callRecord participants block."""
    names: list[str] = []
    organizer_id: str | None = None

    organizer_block = raw.get("organizer", {})
    org_user = organizer_block.get("user", {})
    if org_user.get("displayName"):
        names.append(org_user["displayName"])
    if org_user.get("id"):
        organizer_id = org_user["id"]

    for attendee in raw.get("attendees", []):
        user = attendee.get("user", {})
        name = user.get("displayName")
        if name and name not in names:
            names.append(name)

    return names, organizer_id


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime string, ensuring UTC timezone."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


# ---------------------------------------------------------------------------
# VTT parsing
# ---------------------------------------------------------------------------

_VTT_VOICE_TAG = re.compile(r"<v ([^>]+)>(.*?)</v>", re.DOTALL)
_VTT_NOTE_SPEAKER = re.compile(r"NOTE\s+speaker:\s*(.+)")
_VTT_TIMESTAMP = re.compile(r"^(\d{2}):(\d{2}):(\d{2})[\.,](\d{3})\s+-->")


def _parse_vtt(vtt_text: str) -> list[TranscriptSegment]:
    """Parse a WebVTT transcript string into TranscriptSegment objects."""
    if not vtt_text.strip():
        return []

    segments: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_ts: int | None = None
    pending_lines: list[str] = []

    def _flush() -> None:
        if pending_lines and current_speaker is not None:
            text = " ".join(pending_lines).strip()
            if text:
                segments.append(
                    TranscriptSegment(
                        speaker=current_speaker,
                        text=text,
                        timestamp_seconds=current_ts,
                    )
                )
        pending_lines.clear()

    lines = vtt_text.splitlines()
    i = 0
    # Skip WEBVTT header line
    if lines and lines[0].startswith("WEBVTT"):
        i = 1

    while i < len(lines):
        line = lines[i]

        # NOTE speaker: block
        note_match = _VTT_NOTE_SPEAKER.match(line.strip())
        if note_match:
            _flush()
            current_speaker = note_match.group(1).strip()
            i += 1
            continue

        # Timestamp cue line
        ts_match = _VTT_TIMESTAMP.match(line)
        if ts_match:
            _flush()
            h, m, s = int(ts_match.group(1)), int(ts_match.group(2)), int(ts_match.group(3))
            current_ts = h * 3600 + m * 60 + s
            i += 1
            # Read cue payload lines until blank line
            while i < len(lines) and lines[i].strip():
                cue_line = lines[i]
                voice_match = _VTT_VOICE_TAG.search(cue_line)
                if voice_match:
                    _flush()
                    current_speaker = voice_match.group(1).strip()
                    pending_lines.append(voice_match.group(2).strip())
                elif current_speaker is not None:
                    pending_lines.append(cue_line.strip())
                i += 1
            _flush()
            continue

        i += 1

    _flush()
    return segments


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------


async def list_meetings(
    token: str,
    *,
    max_results: int = 50,
    lookback_days: int = 7,
) -> list[MeetingRecord]:
    """Return recent meeting records from the Graph callRecords API."""
    max_results = max(
        _MAX_RESULTS_MIN, min(_MAX_RESULTS_MAX, max_results)
    )
    since = (datetime.now(UTC) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        f"{_BASE}/communications/callRecords"
        f"?$filter=startDateTime ge {since}"
        f"&$top={max_results}"
        f"&$expand=participants"
    )

    async with httpx.AsyncClient() as client:
        raw_records = await _follow_pages(client, url, token)

    records: list[MeetingRecord] = []
    for raw in raw_records:
        start_raw = raw.get("startDateTime")
        if not start_raw:
            log.warning("Skipping callRecord %s: missing startDateTime", raw.get("id"))
            continue

        end_raw = raw.get("endDateTime")
        participants_block = raw.get("participants", {})
        names, organizer_id = _parse_participants(participants_block)

        records.append(
            MeetingRecord(
                id=raw["id"],
                title=raw.get("subject"),
                started_at=_parse_datetime(start_raw),
                ended_at=_parse_datetime(end_raw) if end_raw else None,
                participants=names,
                organizer_id=organizer_id,
            )
        )

    return records


async def get_transcript(
    token: str,
    meeting_id: str,
) -> tuple[MeetingRecord | None, list[TranscriptSegment]]:
    """Fetch and parse the VTT transcript for a meeting.

    Returns (meeting_record, segments). Returns (None, []) if no transcript exists.
    """
    async with httpx.AsyncClient() as client:
        # Fetch the callRecord to get meeting metadata
        rec_resp = await client.get(
            f"{_BASE}/communications/callRecords/{meeting_id}?$expand=participants",
            headers=_auth_headers(token),
        )
        if rec_resp.status_code == 404:
            return None, []
        rec_resp.raise_for_status()
        raw = rec_resp.json()

        start_raw = raw.get("startDateTime")
        if not start_raw:
            return None, []

        participants_block = raw.get("participants", {})
        names, organizer_id = _parse_participants(participants_block)
        end_raw = raw.get("endDateTime")

        record = MeetingRecord(
            id=raw["id"],
            title=raw.get("subject"),
            started_at=_parse_datetime(start_raw),
            ended_at=_parse_datetime(end_raw) if end_raw else None,
            participants=names,
            organizer_id=organizer_id,
        )

        # Fetch transcript list
        transcripts_resp = await client.get(
            f"{_BASE}/communications/callRecords/{meeting_id}/transcripts",
            headers=_auth_headers(token),
        )
        if transcripts_resp.status_code in (404, 403):
            return record, []
        transcripts_resp.raise_for_status()
        transcripts_data = transcripts_resp.json()
        transcript_list = transcripts_data.get("value", [])
        if not transcript_list:
            return record, []

        # Fetch first (most recent) transcript content as VTT
        transcript_id = transcript_list[0].get("id")
        vtt_resp = await client.get(
            f"{_BASE}/communications/callRecords/{meeting_id}/transcripts/{transcript_id}/content?$format=text/vtt",
            headers=_auth_headers(token),
        )
        if vtt_resp.status_code == 404:
            return record, []
        vtt_resp.raise_for_status()
        vtt_text = vtt_resp.text

    segments = _parse_vtt(vtt_text)
    return record, segments


async def get_meeting_summary(
    token: str,
    meeting_id: str,
) -> MeetingSummaryRecord | None:
    """Fetch Copilot-generated summary and action items for a meeting (beta API)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_BETA}/communications/callRecords/{meeting_id}/meetingCaption",
            headers=_auth_headers(token),
        )
        if resp.status_code in (404, 403):
            return None
        resp.raise_for_status()
        data = resp.json()

    caption = data.get("caption", data)
    summary = caption.get("summary") or data.get("summary", "")
    if not summary:
        return None

    raw_actions = caption.get("actionItems") or data.get("actionItems", [])
    action_items = [a.get("text", a) if isinstance(a, dict) else str(a) for a in raw_actions]

    return MeetingSummaryRecord(summary=summary, action_items=action_items)
