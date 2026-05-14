"""Unit tests for src/api/broadcaster.py."""

import asyncio

import pytest

from src.api.broadcaster import _queues, broadcast, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def clear_queues():
    """Reset the global queue list between tests."""
    _queues.clear()
    yield
    _queues.clear()


def test_subscribe_returns_queue():
    q = subscribe()
    assert isinstance(q, asyncio.Queue)
    assert q in _queues


def test_unsubscribe_removes_queue():
    q = subscribe()
    assert q in _queues
    unsubscribe(q)
    assert q not in _queues


def test_unsubscribe_unknown_queue_does_not_raise():
    q = asyncio.Queue()
    unsubscribe(q)  # should not raise ValueError


@pytest.mark.asyncio
async def test_broadcast_puts_event_on_all_queues():
    q1 = subscribe()
    q2 = subscribe()
    event = {"type": "new_commit", "commit": {"sha": "abc123"}}
    await broadcast(event)
    assert q1.get_nowait() == event
    assert q2.get_nowait() == event


@pytest.mark.asyncio
async def test_broadcast_with_no_subscribers_does_not_raise():
    await broadcast({"type": "new_commit"})  # should complete silently


@pytest.mark.asyncio
async def test_broadcast_does_not_deliver_to_unsubscribed_queue():
    q = subscribe()
    unsubscribe(q)
    await broadcast({"type": "new_commit"})
    assert q.empty()
