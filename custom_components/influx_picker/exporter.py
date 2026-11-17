"""Exporter core: bounded queue, batching and retry with backoff.

Independent of the backend and of Home Assistant. Points are put into a queue
bounded by count; a single writer task sends batches of up to `batch_size`
points after `batch_timeout` seconds without a new point. Temporary failures
are retried with exponential backoff, invalid batches are dropped.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
import contextlib
from dataclasses import dataclass
import logging
import time

from .backends.base import BackendError, BackendInvalidDataError
from .const import (
    BACKOFF_MAX,
    BACKOFF_START,
    BATCH_SIZE,
    BATCH_TIMEOUT,
    MAX_QUEUE,
)
from .point import Point

_LOGGER = logging.getLogger(__name__)

WriteFunc = Callable[[Sequence[Point]], Awaitable[None]]


@dataclass(slots=True)
class ExporterStats:
    """Counters for diagnostics."""

    written: int = 0
    dropped_overflow: int = 0
    dropped_invalid: int = 0
    write_errors: int = 0
    last_success: float | None = None  # time.time()


class Exporter:
    """Queue points and write them in batches."""

    _sleep = staticmethod(asyncio.sleep)  # replaced in tests

    def __init__(
        self,
        write: WriteFunc,
        *,
        batch_size: int = BATCH_SIZE,
        batch_timeout: float = BATCH_TIMEOUT,
        max_queue: int = MAX_QUEUE,
        backoff_start: float = BACKOFF_START,
        backoff_max: float = BACKOFF_MAX,
        name: str = "",
    ) -> None:
        """Set up an idle exporter. Call `start()` to begin writing."""
        self._write = write
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._max_queue = max_queue
        self._backoff_start = backoff_start
        self._backoff_max = backoff_max
        self._name = name
        self._queue: deque[Point] = deque()
        self._new_point = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._failing = False
        self.stats = ExporterStats()

    @property
    def queue_size(self) -> int:
        """Number of points waiting to be written."""
        return len(self._queue)

    def add(self, point: Point) -> None:
        """Queue one point. Drops the oldest point when the queue is full."""
        if len(self._queue) >= self._max_queue:
            self._queue.popleft()
            self.stats.dropped_overflow += 1
        self._queue.append(point)
        self._new_point.set()

    def start(self) -> None:
        """Start the writer task."""
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(
                self._run(), name=f"influx_picker exporter {self._name}"
            )

    async def stop(self, flush_timeout: float) -> None:
        """Stop the writer task, then try to write what is left (once, bounded)."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if not self._queue:
            return
        try:
            async with asyncio.timeout(flush_timeout):
                while self._queue:
                    if not await self._write_one_batch():
                        break
        except TimeoutError:
            pass
        if self._queue:
            _LOGGER.warning(
                "%s: %d points could not be written before shutdown",
                self._name,
                len(self._queue),
            )

    async def _wait_for_batch(self) -> None:
        """Wait for the first point, then for a full batch or a quiet period."""
        while not self._queue:
            self._new_point.clear()
            await self._new_point.wait()
        while len(self._queue) < self._batch_size:
            self._new_point.clear()
            try:
                async with asyncio.timeout(self._batch_timeout):
                    await self._new_point.wait()
            except TimeoutError:
                return

    async def _write_one_batch(self) -> bool:
        """Write the oldest batch. Return False on a temporary failure."""
        count = min(self._batch_size, len(self._queue))
        batch = [self._queue.popleft() for _ in range(count)]
        try:
            await self._write(batch)
        except BackendInvalidDataError as err:
            self.stats.dropped_invalid += len(batch)
            _LOGGER.error("%s: dropped %d invalid points: %s", self._name, count, err)
            return True
        except BackendError as err:
            self._requeue(batch)
            self.stats.write_errors += 1
            if not self._failing:
                _LOGGER.error("%s: write failed, will retry: %s", self._name, err)
            else:
                _LOGGER.debug("%s: write failed again: %s", self._name, err)
            self._failing = True
            return False
        except Exception:
            # A bug, not a server problem: do not retry forever.
            self.stats.dropped_invalid += len(batch)
            _LOGGER.exception(
                "%s: unexpected error, dropped %d points", self._name, count
            )
            return True
        self.stats.written += len(batch)
        self.stats.last_success = time.time()
        if self._failing:
            _LOGGER.info("%s: writing works again", self._name)
            self._failing = False
        return True

    def _requeue(self, batch: list[Point]) -> None:
        """Put a failed batch back in front, keeping the queue bound (oldest dropped)."""
        self._queue.extendleft(reversed(batch))
        while len(self._queue) > self._max_queue:
            self._queue.popleft()
            self.stats.dropped_overflow += 1

    async def _run(self) -> None:
        backoff = self._backoff_start
        while True:
            await self._wait_for_batch()
            if await self._write_one_batch():
                backoff = self._backoff_start
            else:
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._backoff_max)
