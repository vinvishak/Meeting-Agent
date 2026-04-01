"""
Transcript analyzer.

Segments a speaker-attributed transcript into candidate mentions, matches
each mention to Jira tickets (entity_matcher), classifies the speaker's
intent via Claude API, and resolves the speaker to a canonical Engineer.

The output is a list of MentionCandidate records ready for update_suggester
to convert into UpdateSuggestion objects.
"""

import json
import re
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.entity_matcher import MatchResult, match_excerpt
from src.ingestion.normalizer import JiraIdentity, resolve_engineer
from src.logging_config import get_logger
from src.storage.models import MentionIntent, Ticket, Transcript
from src.storage.repository import EngineerRepository

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Transcript segmentation
# ---------------------------------------------------------------------------

# Patterns handled:
#   "Speaker Name: text..."
#   "[00:01:23] Speaker Name: text..."
#   "[00:01:23] text..." (no speaker label)

_SEGMENT_RE = re.compile(
    r"(?:^\[(?P<ts>[\d:]+)\]\s*)?(?P<speaker>[^:\n]{1,80}):\s*(?P<text>.+)",
    re.MULTILINE,
)
_TIMESTAMP_RE = re.compile(r"^(\d+):(\d+)(?::(\d+))?$")


def _parse_timestamp(ts: str) -> int | None:
    """Convert 'HH:MM:SS' or 'MM:SS' to total seconds."""
    m = _TIMESTAMP_RE.match(ts)
    if not m:
        return None
    parts = [int(x) for x in m.groups() if x is not None]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


@dataclass
class TranscriptSegment:
    speaker: str
    text: str
    timestamp_seconds: int | None = None


def segment_transcript(raw: str) -> list[TranscriptSegment]:
    """Split a raw transcript string into speaker-attributed segments."""
    segments: list[TranscriptSegment] = []
    for m in _SEGMENT_RE.finditer(raw):
        ts_str = m.group("ts")
        ts = _parse_timestamp(ts_str) if ts_str else None
        speaker = m.group("speaker").strip()
        text = m.group("text").strip()
        if text:
            segments.append(TranscriptSegment(speaker=speaker, text=text, timestamp_seconds=ts))
    return segments


# ---------------------------------------------------------------------------
# Intent classification via Claude
# ---------------------------------------------------------------------------

_VALID_INTENTS = {i.value for i in MentionIntent}

_INTENT_PROMPT = """\
Classify the primary intent of this meeting excerpt that references a Jira ticket.

Return JSON: {{"intent": "<intent>", "confidence": <0.0-1.0>}}

Valid intents (pick exactly one):
- progress_update: speaker is reporting current progress
- blocker: speaker is mentioning something is blocked
- completion: speaker is saying the work is done
- ownership_change: speaker is reassigning the ticket
- eta_change: speaker mentions a new deadline or timeline
- dependency: speaker mentions a dependency on another issue
- future_intent: speaker says they will work on it (not yet started)
- ambiguous: unclear intent

Excerpt: "{excerpt}"
Ticket: "{ticket_title}" ({jira_id})"""


async def _classify_intent(
    excerpt: str,
    jira_id: str,
    ticket_title: str,
    client: AsyncAnthropic,
) -> tuple[str, float]:
    """Return (mention_intent_value, confidence)."""
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": _INTENT_PROMPT.format(
                        excerpt=excerpt[:300],
                        ticket_title=ticket_title[:100],
                        jira_id=jira_id,
                    ),
                }
            ],
        )
        raw = response.content[0].text  # type: ignore[union-attr]
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return MentionIntent.ambiguous.value, 0.5
        data = json.loads(raw[start:end])
        intent = data.get("intent", "ambiguous")
        if intent not in _VALID_INTENTS:
            intent = MentionIntent.ambiguous.value
        confidence = float(data.get("confidence", 0.5))
        return intent, min(max(confidence, 0.0), 1.0)
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        return MentionIntent.ambiguous.value, 0.5


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------


@dataclass
class MentionCandidate:
    """A resolved + classified reference to a Jira ticket found in a transcript."""

    speaker_name: str
    excerpt: str
    excerpt_timestamp_seconds: int | None
    ticket_id: str | None        # internal DB UUID (None if unresolved)
    jira_id: str                  # empty string if unresolved
    ticket_title: str
    match_type: str               # MatchType value
    match_confidence: float
    mention_intent: str           # MentionIntent value
    intent_confidence: float
    speaker_engineer_id: str | None = None
    extra_matches: list[MatchResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


async def analyze_transcript(
    transcript: Transcript,
    active_tickets: list[Ticket],
    session: AsyncSession,
    anthropic_client: AsyncAnthropic | None,
) -> list[MentionCandidate]:
    """
    Analyze a transcript and return classified ticket mention candidates.

    Only segments that successfully match a ticket (exact or semantic) are
    returned as actionable candidates. Unresolved segments are skipped —
    they are tracked via `match_type=unresolved` in MentionRepository by
    the caller if desired.
    """
    segments = segment_transcript(transcript.raw_transcript)
    if not segments:
        logger.info("No segments found in transcript %s", transcript.id)
        return []

    # Pre-load all engineers for speaker resolution
    all_engineers = await EngineerRepository.list_all(session)

    candidates: list[MentionCandidate] = []

    for seg in segments:
        # 1. Match excerpt against active tickets
        matches = await match_excerpt(seg.text, active_tickets, anthropic_client)
        if not matches:
            continue

        best = matches[0]

        # Skip genuinely unresolved segments
        if best.match_type == "unresolved" or not best.ticket_id:
            # Still add as unresolved if we want to surface them
            candidates.append(
                MentionCandidate(
                    speaker_name=seg.speaker,
                    excerpt=seg.text,
                    excerpt_timestamp_seconds=seg.timestamp_seconds,
                    ticket_id=None,
                    jira_id=best.jira_id,
                    ticket_title=best.ticket_title,
                    match_type=best.match_type,
                    match_confidence=best.confidence,
                    mention_intent=MentionIntent.ambiguous.value,
                    intent_confidence=0.0,
                    extra_matches=matches[1:],
                )
            )
            continue

        # 2. Classify intent
        intent, intent_conf = (MentionIntent.ambiguous.value, 0.5)
        if anthropic_client is not None and best.ticket_title:
            intent, intent_conf = await _classify_intent(
                seg.text, best.jira_id, best.ticket_title, anthropic_client
            )

        # 3. Resolve speaker to Engineer
        engineer_id: str | None = None
        identity = JiraIdentity(
            username=f"__speaker__{seg.speaker}",
            display_name=seg.speaker,
        )
        try:
            eng = await resolve_engineer(session, identity, all_engineers)
            engineer_id = eng.id
        except Exception as exc:
            logger.debug("Could not resolve speaker %r to engineer: %s", seg.speaker, exc)

        candidates.append(
            MentionCandidate(
                speaker_name=seg.speaker,
                excerpt=seg.text,
                excerpt_timestamp_seconds=seg.timestamp_seconds,
                ticket_id=best.ticket_id,
                jira_id=best.jira_id,
                ticket_title=best.ticket_title,
                match_type=best.match_type,
                match_confidence=best.confidence,
                mention_intent=intent,
                intent_confidence=intent_conf,
                speaker_engineer_id=engineer_id,
                extra_matches=matches[1:],
            )
        )

    return candidates
