"""Background execution of run work (ADR-030).

Each job runs in a worker thread with its own event loop, so CPU-heavy Methods
(unit-level matching, regression) never block the API's event loop. The caller
waits up to `wait` seconds; if the job is still running the API answers 202 and
the client polls the run. Job state lives in the run store, so any process can
serve the poll.

This is an in-process executor: jobs die with the process (they are marked
INTERRUPTED on the next start). A shared queue is the step up for multi-process
deployments.
"""
from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class JobRunner:
    def __init__(self, max_workers: int = 4) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="decision-layer-job")

    def submit(self, fn: Callable[[], Awaitable[T]]) -> asyncio.Future[T]:
        # the job sees the request's context (e.g. its locale) in its own thread and event loop
        ctx = contextvars.copy_context()
        fut = asyncio.get_running_loop().run_in_executor(self._pool, lambda: ctx.run(asyncio.run, fn()))
        # an error raised after the caller stopped waiting is already recorded on the run
        fut.add_done_callback(lambda f: f.cancelled() or f.exception())
        return fut

    @staticmethod
    async def settle(fut: asyncio.Future[T], wait: float | None) -> tuple[bool, T | None]:
        """(finished, value). Waits forever when wait is None; re-raises the job's error if it finished with one."""
        try:
            return True, await asyncio.wait_for(asyncio.shield(fut), wait)
        except asyncio.TimeoutError:
            return False, None

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
