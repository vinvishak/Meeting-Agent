# MCP Tool Contract: Copilot MCP Wrapper

**Branch**: `003-copilot-mcp-wrapper` | **Date**: 2026-04-05

This document defines the exact MCP tool interface exposed by `src/copilot_mcp/`. The Meeting Agent's `CopilotMCPClient` (`src/ingestion/copilot_client.py`) calls these tools via SSE transport. Any change to tool names, parameter names, or return shapes is a **breaking change** for the ingestion layer.

---

## Transport

| Property | Value |
|----------|-------|
| Transport | SSE (Server-Sent Events) |
| Base URL | `{COPILOT_MCP_URL}/sse` (e.g. `http://localhost:3001/sse`) |
| Auth | `Authorization: Bearer {MCP_TOKEN}` (required if `MCP_TOKEN` env var is set) |
| Health check | `GET {COPILOT_MCP_URL}/health` → `200 {"status": "ok"}` |

---

## Tool: `list_meetings`

Returns recent meeting metadata for all meetings in the tenant within the configured lookback window.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "maxResults": {
      "type": "integer",
      "description": "Maximum number of meetings to return. Clamped to 1–200.",
      "default": 50
    }
  },
  "required": []
}
```

### Output Schema

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "id":           { "type": "string", "description": "Meeting identifier used in other tools" },
      "title":        { "type": ["string", "null"], "description": "Meeting subject/title" },
      "startedAt":    { "type": "string", "format": "date-time", "description": "UTC start time (ISO 8601)" },
      "endedAt":      { "type": ["string", "null"], "format": "date-time", "description": "UTC end time; null if ongoing" },
      "participants": { "type": "array", "items": { "type": "string" }, "description": "Participant display names" }
    },
    "required": ["id", "startedAt", "participants"]
  }
}
```

**On success**: Array of 0–N meeting objects. Empty array when no meetings found in window.
**On Graph API error**: MCP error response (tool execution failure, not null).

---

## Tool: `get_transcript`

Returns the full speaker-attributed transcript for a single meeting.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "meetingId": {
      "type": "string",
      "description": "Meeting identifier as returned by list_meetings"
    }
  },
  "required": ["meetingId"]
}
```

### Output Schema

```json
{
  "oneOf": [
    {
      "type": "object",
      "properties": {
        "id":            { "type": "string" },
        "title":         { "type": ["string", "null"] },
        "startedAt":     { "type": "string", "format": "date-time" },
        "endedAt":       { "type": ["string", "null"], "format": "date-time" },
        "participants":  { "type": "array", "items": { "type": "string" } },
        "rawTranscript": {
          "type": "string",
          "description": "Newline-delimited speaker-attributed text: 'DisplayName: utterance\\n'"
        }
      },
      "required": ["id", "startedAt", "participants", "rawTranscript"]
    },
    { "type": "null" }
  ]
}
```

**Returns `null` when**: transcript not available (not enabled, still processing, or meeting not found).
**Returns error**: only on unexpected Graph API failures after retries exhausted.

**`rawTranscript` format example**:
```
Alice Chen: We should close out the login ticket.
Bob Smith: I finished that yesterday, closing now.
Carol White: Great, I'll update the board.
```

---

## Tool: `get_meeting_summary`

Returns the Copilot-generated summary and action items for a meeting.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "meetingId": {
      "type": "string",
      "description": "Meeting identifier as returned by list_meetings"
    }
  },
  "required": ["meetingId"]
}
```

### Output Schema

```json
{
  "oneOf": [
    {
      "type": "object",
      "properties": {
        "summary":     { "type": "string", "description": "Copilot-generated meeting summary" },
        "actionItems": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Extracted action items as plain strings"
        }
      },
      "required": ["summary", "actionItems"]
    },
    { "type": "null" }
  ]
}
```

**Returns `null` when**: Copilot summarisation was not enabled, summary not yet generated, or meeting not found.
**Returns error**: only on unexpected Graph API failures after retries exhausted.

---

## Error Behaviour

| Condition | Response |
|-----------|----------|
| Missing required parameter (`meetingId`) | MCP structured error: `{"error": "missing_param", "param": "meetingId"}` |
| Invalid `Authorization` header (MCP_TOKEN set) | HTTP 401 before MCP session established |
| Graph API 429 (rate limit), retries exhausted | MCP tool error with message `"Graph API rate limit exceeded after retries"` |
| Graph API 4xx (auth/permission error) | MCP tool error with message `"Graph API error: {status} {reason}"` |
| Transcript/summary not found (404 or empty) | `null` return (not an error) |

---

## Compatibility Contract with `src/ingestion/copilot_client.py`

The ingestion layer parses tool results as follows. Any change here is a **breaking change**:

| Tool | Ingestion field | Maps to |
|------|----------------|---------|
| `list_meetings` | `CopilotMeeting.copilot_meeting_id` | `id` |
| `list_meetings` | `CopilotMeeting.title` | `title` |
| `list_meetings` | `CopilotMeeting.started_at` | `startedAt` |
| `list_meetings` | `CopilotMeeting.ended_at` | `endedAt` |
| `list_meetings` | `CopilotMeeting.participants` | `participants` |
| `get_transcript` | `CopilotTranscript.raw_transcript` | `rawTranscript` |
| `get_transcript` | `CopilotTranscript.copilot_summary` | _(unused by this tool)_ |
| `get_meeting_summary` | `CopilotTranscript.copilot_summary` | `summary` |
| `get_meeting_summary` | `CopilotTranscript.action_items` | `actionItems` |
