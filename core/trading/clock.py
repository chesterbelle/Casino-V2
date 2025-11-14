from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional


@dataclass
class ClockJob:
    name: str
    handler: Callable[[], Awaitable[None]]
    interval: float  # seconds
    timeout: float = 0.5  # seconds
    last_run: float = field(default_factory=lambda: 0.0)
    next_run: float = field(default_factory=lambda: 0.0)


class MasterClock:
    """
    Master Clock with a fixed base tick and a simple scheduler for async jobs.

    - Base tick: controls wake-ups; jobs run when now >= next_run
    - Each job has its own interval and timeout
    - Jobs must be idempotent and quick (< timeout)
    - Exceptions are logged and do not crash the clock
    """

    def __init__(self, base_tick: float = 1.0, logger: Optional[logging.Logger] = None):
        self._base_tick = float(base_tick)
        self._logger = logger or logging.getLogger("MasterClock")
        self._jobs: Dict[str, ClockJob] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def register_job(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        interval: float,
        timeout: float = 0.5,
    ) -> None:
        now = time.monotonic()
        job = ClockJob(name=name, handler=handler, interval=float(interval), timeout=float(timeout))
        job.last_run = 0.0
        job.next_run = now + job.interval
        self._jobs[name] = job
        self._logger.info(f"🕒 Job registered | {name} every {interval:.2f}s (timeout {timeout:.2f}s)")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        self._logger.info("🕒 MasterClock started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("🕒 MasterClock stopped")

    async def _run(self) -> None:
        try:
            while self._running:
                started = time.monotonic()
                await self._tick_once()
                elapsed = time.monotonic() - started
                sleep_for = max(0.0, self._base_tick - elapsed)
                await asyncio.sleep(sleep_for)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"❌ MasterClock crashed: {e}")

    async def _tick_once(self) -> None:
        now = time.monotonic()
        for job in list(self._jobs.values()):
            if now < job.next_run:
                continue
            # run job with timeout
            try:
                await asyncio.wait_for(job.handler(), timeout=job.timeout)
            except asyncio.TimeoutError:
                self._logger.warning(f"⏱️ Job timed out: {job.name} (> {job.timeout:.2f}s)")
            except Exception as e:
                self._logger.warning(f"⚠️ Job error: {job.name}: {e}")
            finally:
                job.last_run = now
                job.next_run = now + job.interval
