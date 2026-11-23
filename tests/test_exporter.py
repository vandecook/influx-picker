"""Tests for the exporter core (queue, batching, backoff)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from custom_components.influx_picker.backends import (
    BackendAuthError,
    BackendConnectionError,
    BackendInvalidDataError,
)
from custom_components.influx_picker.exporter import Exporter
from custom_components.influx_picker.point import Point

T = datetime(2026, 11, 17, tzinfo=UTC)


def _point(i: int) -> Point:
    return Point("m", T, {}, {"i": float(i)})


class FakeWriter:
    """Records batches; can be told to fail."""

    def __init__(self) -> None:
        self.batches: list[list[float]] = []
        self.fail_with: list[Exception] = []
        self.calls = 0

    async def __call__(self, points) -> None:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with.pop(0)
        self.batches.append([p.fields["i"] for p in points])


def _exporter(writer, **kwargs) -> Exporter:
    kwargs.setdefault("batch_timeout", 0.05)
    kwargs.setdefault("backoff_start", 0.01)
    kwargs.setdefault("backoff_max", 0.04)
    return Exporter(writer, **kwargs)


async def _until(cond, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not cond():
            await asyncio.sleep(0.005)


async def test_flush_after_quiet_period() -> None:
    """Points are written together after the quiet period."""
    writer = FakeWriter()
    exp = _exporter(writer)
    exp.start()
    for i in range(3):
        exp.add(_point(i))
    await _until(lambda: writer.batches)
    assert writer.batches == [[0, 1, 2]]
    assert exp.stats.written == 3
    await exp.stop(1)


async def test_batch_size_limit() -> None:
    """A full batch is written without waiting, then the rest."""
    writer = FakeWriter()
    exp = _exporter(writer, batch_size=2, batch_timeout=10)
    for i in range(5):
        exp.add(_point(i))
    exp.start()
    await _until(lambda: len(writer.batches) >= 2)
    assert writer.batches[:2] == [[0, 1], [2, 3]]
    await exp.stop(1)
    assert writer.batches[2] == [4]


async def test_queue_bound_drops_oldest() -> None:
    """When the queue is full, the oldest points are dropped."""
    exp = _exporter(FakeWriter(), max_queue=3)
    for i in range(5):
        exp.add(_point(i))
    assert exp.queue_size == 3
    assert exp.stats.dropped_overflow == 2


async def test_retry_keeps_order_and_recovers() -> None:
    """A temporary failure is retried with the same points in the same order."""
    writer = FakeWriter()
    writer.fail_with = [BackendConnectionError("down"), BackendConnectionError("down")]
    exp = _exporter(writer)
    exp.start()
    exp.add(_point(1))
    exp.add(_point(2))
    await _until(lambda: writer.batches)
    assert writer.batches == [[1, 2]]
    assert exp.stats.write_errors == 2
    assert exp.stats.written == 2
    await exp.stop(1)


async def test_invalid_batch_is_dropped() -> None:
    """HTTP 400-like errors drop the batch instead of retrying."""
    writer = FakeWriter()
    writer.fail_with = [BackendInvalidDataError("bad")]
    exp = _exporter(writer)
    exp.start()
    exp.add(_point(1))
    await _until(lambda: exp.stats.dropped_invalid == 1)
    exp.add(_point(2))
    await _until(lambda: writer.batches)
    assert writer.batches == [[2]]
    await exp.stop(1)


async def test_requeue_respects_bound() -> None:
    """Points added while a write fails do not grow the queue past the bound."""
    writer = FakeWriter()
    exp = _exporter(writer, max_queue=3, batch_size=2)
    gate = asyncio.Event()

    async def slow_fail(points) -> None:
        exp.add(_point(10))
        exp.add(_point(11))
        exp.add(_point(12))
        gate.set()
        raise BackendConnectionError("down")

    exp._write = slow_fail
    exp.add(_point(1))
    exp.add(_point(2))
    exp.start()
    await gate.wait()
    await asyncio.sleep(0)
    assert exp.queue_size == 3
    assert exp.stats.dropped_overflow == 2
    await exp.stop(0.01)


async def test_backoff_grows_and_is_capped() -> None:
    """Backoff doubles from the start value up to the maximum."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        await asyncio.sleep(0)

    writer = FakeWriter()
    writer.fail_with = [BackendConnectionError("down")] * 5
    exp = Exporter(writer, batch_timeout=0.001, backoff_start=5, backoff_max=60)
    exp._sleep = fake_sleep
    exp.add(_point(1))
    exp.start()
    await _until(lambda: writer.batches)
    assert sleeps == [5, 10, 20, 40, 60]
    await exp.stop(1)


async def test_stop_flushes_remaining_points() -> None:
    """Stopping writes what is still queued."""
    writer = FakeWriter()
    exp = _exporter(writer, batch_timeout=10)
    exp.start()
    exp.add(_point(1))
    await asyncio.sleep(0.01)
    await exp.stop(1)
    assert writer.batches == [[1]]


async def test_stop_gives_up_when_server_is_down() -> None:
    """A failing flush on stop does not hang."""
    writer = FakeWriter()
    writer.fail_with = [BackendConnectionError("down")] * 10
    exp = _exporter(writer, batch_timeout=10)
    exp.add(_point(1))
    await exp.stop(0.1)
    assert exp.queue_size == 1


async def test_auth_error_reported_once_per_streak() -> None:
    """A rejected token calls on_auth_error once, again only after a success."""
    writer = FakeWriter()
    calls: list[int] = []
    exp = _exporter(writer, on_auth_error=lambda: calls.append(1))
    writer.fail_with = [
        BackendConnectionError("down"),
        BackendAuthError("401"),
        BackendAuthError("401"),
    ]
    exp.add(_point(0))
    for _ in range(3):
        assert not await exp._write_one_batch()
    assert calls == [1]
    assert await exp._write_one_batch()  # works again
    writer.fail_with = [BackendAuthError("401")]
    exp.add(_point(1))
    assert not await exp._write_one_batch()
    assert calls == [1, 1]
    assert exp.take_queue() == [_point(1)]
    assert exp.queue_size == 0
