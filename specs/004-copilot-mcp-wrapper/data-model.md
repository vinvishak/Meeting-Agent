# Data Model: Copilot MCP Wrapper — Teams Transcript Bridge

**Branch**: `003-copilot-mcp-wrapper` | **Date**: 2026-04-05

This service is stateless — it holds no persistent storage. The data model describes the **in-memory structures** used within a single tool call lifetime, and the **wire shapes** (JSON) returned by each MCP tool.

---

## In-Memory Types

### `TokenState`

Held in `auth.py` as module-level state within the `msal` token cache.

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | `str` | Bearer token for Graph API requests |
| `expires_on` | `int` | Unix timestamp after which token must be refreshed |

Managed entirely by `msal.ConfidentialClientApplication`. Not exposed externally.

---

### `MeetingRecord`

Internal representation of a meeting, parsed from a Graph API `callRecord` response.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | `str` | No | Graph callRecord ID, used as `meetingId` across all three tools |
| `title` | `str \| None` | Yes | Meeting subject/title from the callRecord |
| `started_at` | `datetime` | No | UTC start time |
| `ended_at` | `datetime \| None` | Yes | UTC end time; null if meeting is ongoing |
| `participants` | `list[str]` | No | Display names of all participants; empty list if unavailable |
| `organizer_id` | `str \| None` | Yes | AAD user ID of the meeting organiser; used to resolve transcript endpoint |

---

### `TranscriptSegment`

One speaker turn parsed from a VTT transcript file.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `speaker` | `str` | No | Display name extracted from VTT `<v>` tag or `NOTE speaker:` block |
| `text` | `str` | No | Utterance text with filler tags stripped |
| `timestamp_seconds` | `int \| None` | Yes | Cue start time in seconds from meeting start; null if VTT timestamp absent |

---

### `MeetingSummaryRecord`

Parsed from Graph API `meetingCaption` beta response.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `summary` | `str` | No | Copilot-generated summary paragraph |
| `action_items` | `list[str]` | No | Extracted action items; empty list if none |

---

## MCP Tool Wire Shapes (JSON)

These are the exact JSON structures returned by each tool to MCP clients.

### `list_meetings` → `list[MeetingOut]`

```json
[
  {
    "id": "callRecord-id-abc123",
    "title": "Sprint Planning — Backend Team",
    "startedAt": "2026-04-04T09:00:00Z",
    "endedAt": "2026-04-04T10:00:00Z",
    "participants": ["Alice Chen", "Bob Smith", "Carol White"]
  }
]
```

Returns `[]` (empty list) when no meetings exist in the lookback window. Never returns `null`.

---

### `get_transcript` → `TranscriptOut | null`

```json
{
  "id": "callRecord-id-abc123",
  "title": "Sprint Planning — Backend Team",
  "startedAt": "2026-04-04T09:00:00Z",
  "endedAt": "2026-04-04T10:00:00Z",
  "participants": ["Alice Chen", "Bob Smith", "Carol White"],
  "rawTranscript": "Alice Chen: We need to close out the login ticket.\nBob Smith: I finished that yesterday, should we mark it done?\n"
}
```

Returns `null` when:
- Meeting has no transcript (transcription not enabled)
- Transcript processing is not yet complete
- Meeting ID not found or not accessible

The `rawTranscript` field is a `\n`-delimited string of `"Speaker: text"` lines, assembled from all VTT cues in chronological order. This matches the format expected by `src/ingestion/copilot_client.py`'s `CopilotTranscript.raw_transcript` field.

---

### `get_meeting_summary` → `SummaryOut | null`

```json
{
  "summary": "The team reviewed sprint progress. The login feature was confirmed complete. A blocker on the payment module was identified.",
  "actionItems": [
    "Bob to close PROJ-123 in Jira",
    "Carol to investigate payment module blocker"
  ]
}
```

Returns `null` when:
- Copilot summarisation was not enabled for this meeting
- Summary generation has not completed
- Meeting ID not found

---

## Validation Rules

| Rule | Applies To | Detail |
|------|-----------|--------|
| `maxResults` range | `list_meetings` input | Integer, 1–200. Default 50. Values outside range are clamped, not rejected. |
| `meetingId` non-empty | `get_transcript`, `get_meeting_summary` input | Empty string or missing → MCP structured error, not null |
| `started_at` required | `MeetingRecord` | If Graph API returns no start time, record is skipped and warning logged |
| `rawTranscript` encoding | `TranscriptOut` | UTF-8 string. Non-UTF-8 characters are replaced with `?` during VTT parsing |

---

## State Transitions

The server is stateless per request. The only stateful element is the `msal` token cache:

```
[cold start] → acquire_token() → [token cached, expires_on set]
                                        ↓
                              [tool call arrives]
                                        ↓
                   [token valid?] ──yes──→ use cached token
                         │
                        no
                         ↓
                   acquire_token() → [token refreshed, new expires_on]
```

Token refresh is synchronous within the async tool call, executed via `asyncio.to_thread` to avoid blocking the event loop.
