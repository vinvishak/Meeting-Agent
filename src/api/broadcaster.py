"""
In-process Server-Sent Events broadcaster.

Any coroutine can call `broadcast(event)` to push a JSON-serialisable dict to
all connected SSE clients.  Works for a single-process uvicorn deployment;
swap for Redis pub/sub if you scale to multiple workers.
"""

import asyncio
import contextlib

_queues: list[asyncio.Queue] = []


async def broadcast(event: dict) -> None:
    """Push an event to every connected SSE client."""
    for q in _queues:
        await q.put(event)


def subscribe() -> asyncio.Queue:
    """Register a new SSE listener and return its queue."""
    q: asyncio.Queue = asyncio.Queue()
    _queues.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove the queue when the client disconnects."""
    with contextlib.suppress(ValueError):
        _queues.remove(q)
