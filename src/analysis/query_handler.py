"""
Natural language query handler (T043).

Accepts a plain-language question, passes it to Claude with the six
read-only tool schemas, executes any tool calls against the database,
and assembles a plain-language answer + structured supporting_data.

Uses claude-sonnet-4-6 as specified in the task plan.
"""

import json
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.query_tools import TOOL_SCHEMAS, dispatch_tool
from src.config import get_settings
from src.logging_config import get_logger
from src.storage.repository import AuditRepository

logger = get_logger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024
_MAX_TOOL_ROUNDS = 5  # prevent runaway loops

_SYSTEM_PROMPT = """\
You are an engineering intelligence assistant. You help engineering managers
understand team status, ticket progress, sprint health, and velocity.

Answer questions using only the provided tools — do not guess data.
Be concise and factual. When returning lists, keep them brief (top 5 max).
Always cite the data source (e.g., which sprint, how many tickets).
"""


async def handle_query(
    question: str,
    session: AsyncSession,
    context: dict | None = None,
    authorized_project_keys: list[str] | None = None,
) -> dict[str, Any]:
    """
    Handle a natural language question.

    Returns:
        {
          "answer": str,
          "supporting_data": dict,
          "data_freshness": str | None
        }

    Raises ValueError if the question cannot be answered from available data.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build initial user message with optional context
    user_content = question
    if context:
        ctx_str = ", ".join(f"{k}={v}" for k, v in context.items() if v)
        if ctx_str:
            user_content = f"{question}\n\nContext: {ctx_str}"

    messages: list[dict] = [{"role": "user", "content": user_content}]
    supporting_data: dict[str, Any] = {}

    # Claude tool-use loop
    for _round in range(_MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Collect text and tool_use blocks
        text_blocks = [b for b in response.content if b.type == "text"]
        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_blocks:
            # No more tool calls — extract final answer
            answer = " ".join(b.text for b in text_blocks).strip()
            if not answer:
                raise ValueError("Claude returned an empty answer for this question.")
            break

        # Execute tool calls
        tool_results = []
        for tb in tool_blocks:
            result = await dispatch_tool(tb.name, tb.input, session)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(result, default=str),
                }
            )
            # Accumulate supporting data keyed by tool name
            supporting_data[tb.name] = result

        # Append assistant turn and tool results to conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    else:
        answer = "I was unable to fully answer your question within the allowed number of steps."

    # Data freshness from last sync
    last_sync = await AuditRepository.get_last_sync_event(session)
    data_freshness = last_sync.created_at.isoformat() if last_sync else None

    return {
        "answer": answer,
        "supporting_data": supporting_data,
        "data_freshness": data_freshness,
    }
