"""
Core Engine for Casino-V3.
Handles the main event loop, component lifecycle, and event dispatching.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from .events import Event, EventType

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self):
        self.running = False
        # Do not create a new loop here. Use the running loop.
        # self.loop = asyncio.new_event_loop()

        # Event Bus: Map EventType -> List[Callback]
        self._subscribers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}

        # Components
        self.strategies = []
        self.data_feed = None
        self.order_manager = None

        # Graceful shutdown
        # We'll setup signals in start() or let the runner handle it
        # self._setup_signal_handlers()

    def subscribe(self, event_type: EventType, callback: Callable[[Event], Awaitable[None]]):
        """Subscribe a callback to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def dispatch(self, event: Event):
        """Dispatch an event to all subscribers."""
        if event.type in self._subscribers:
            # Execute all callbacks concurrently
            callbacks = self._subscribers[event.type]
            await asyncio.gather(*(cb(event) for cb in callbacks), return_exceptions=True)

    async def start(self, blocking: bool = True):
        """Start the engine and all components."""
        logger.info("🚀 Starting Casino-V3 Engine...")
        self.running = True

        # Start Data Feed
        if self.data_feed:
            await self.data_feed.connect()

        # Start Strategies
        for strategy in self.strategies:
            if hasattr(strategy, "on_start"):
                await strategy.on_start()

        logger.info("✅ Engine running. Waiting for events...")

        if blocking:
            # Keep the loop alive
            while self.running:
                await asyncio.sleep(0.1)

            await self.stop()

    async def stop(self):
        """Stop the engine and cleanup."""
        logger.info("🛑 Stopping Engine...")
        self.running = False

        # Stop Strategies
        for strategy in self.strategies:
            if hasattr(strategy, "on_stop"):
                await strategy.on_stop()

        # Stop Data Feed
        if self.data_feed:
            await self.data_feed.disconnect()

        logger.info("👋 Engine stopped.")

        # Cancel all running tasks (except current)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

        # Wait for tasks to cancel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def run(self):
        """Entry point to run the engine (blocking)."""
        # Legacy method if not using asyncio.run
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            pass
