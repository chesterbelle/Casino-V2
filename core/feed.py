"""
Data Feed Layer for Casino-V3.
Manages Websocket streams via CCXTAdapter and dispatches events to the Engine.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Set

from exchanges.adapters import ExchangeAdapter

from .events import EventType, OrderBookEvent, TickEvent

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Manages Websocket streams and dispatches events to the Engine.
    """

    def __init__(self, adapter: ExchangeAdapter, engine):
        self.adapter = adapter
        self.engine = engine
        self.running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribed_symbols: Set[str] = set()

    async def connect(self):
        """Connect the adapter."""
        logger.info("🔌 Connecting Data Feed...")
        await self.adapter.connect()
        self.running = True

        # Start tasks for queued subscriptions
        for symbol in self._subscribed_symbols:
            if f"ticker_{symbol}" not in self._tasks:
                self._tasks[f"ticker_{symbol}"] = asyncio.create_task(self._watch_ticker_loop(symbol))
            if f"ob_{symbol}" not in self._tasks:
                self._tasks[f"ob_{symbol}"] = asyncio.create_task(self._watch_order_book_loop(symbol))

    async def disconnect(self):
        """Disconnect and stop all streams."""
        logger.info("🔌 Disconnecting Data Feed...")
        self.running = False
        for task in self._tasks.values():
            task.cancel()
        await self.adapter.disconnect()

    async def subscribe_ticker(self, symbol: str):
        """Subscribe to ticker updates for a symbol."""
        self._subscribed_symbols.add(symbol)

        if self.running:
            if f"ticker_{symbol}" in self._tasks:
                return
            logger.info(f"📡 Subscribing to ticker: {symbol}")
            self._tasks[f"ticker_{symbol}"] = asyncio.create_task(self._watch_ticker_loop(symbol))
        else:
            logger.info(f"📝 Queued ticker subscription: {symbol}")

    async def subscribe_order_book(self, symbol: str):
        """Subscribe to order book updates for a symbol."""
        self._subscribed_symbols.add(symbol)

        if self.running:
            if f"ob_{symbol}" in self._tasks:
                return
            logger.info(f"📡 Subscribing to order book: {symbol}")
            self._tasks[f"ob_{symbol}"] = asyncio.create_task(self._watch_order_book_loop(symbol))
        else:
            logger.info(f"📝 Queued order book subscription: {symbol}")

    async def _watch_ticker_loop(self, symbol: str):
        """Continuous loop to watch ticker with error handling and auto-recovery."""
        logger.info(f"🔍 Starting ticker loop for {symbol}")

        try:
            from core.error_handling import RetryConfig, get_error_handler

            error_handler = get_error_handler()
            breaker_name = f"ticker_stream_{symbol}"
            consecutive_failures = 0
            max_consecutive_failures = 10
            recovery_pause = 60  # Pause before recovery attempt
        except Exception as e:
            logger.critical(f"❌ Failed to initialize ticker loop: {e}", exc_info=True)
            return

        while self.running:
            try:
                # Use error handler with circuit breaker
                ticker = await error_handler.execute_with_breaker(
                    breaker_name,
                    self.adapter.watch_ticker,
                    symbol,
                    retry_config=RetryConfig(
                        max_retries=3,
                        backoff_base=1.0,
                        backoff_max=30.0,
                    ),
                )
                await self.on_ticker(ticker)

                # Reset failure count on success
                consecutive_failures = 0

            except asyncio.CancelledError:
                logger.info(f"📡 Ticker stream for {symbol} cancelled")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(
                    f"❌ Error in ticker stream for {symbol} "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures}): {e}"
                )

                # If too many consecutive failures, enter recovery mode (don't stop!)
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"⚠️ Ticker stream for {symbol} failed {max_consecutive_failures} times. "
                        f"Entering recovery mode - pausing {recovery_pause}s before retry..."
                    )
                    # Reset circuit breaker
                    error_handler.reset_circuit_breaker(breaker_name)
                    consecutive_failures = 0
                    await asyncio.sleep(recovery_pause)
                    logger.info(f"🔄 Ticker stream for {symbol} attempting recovery...")
                    continue

                # Exponential backoff
                backoff = min(2**consecutive_failures, 60)
                logger.info(f"⏳ Backing off for {backoff}s before retry")
                await asyncio.sleep(backoff)

    async def _watch_order_book_loop(self, symbol: str):
        """Continuous loop to watch order book with error handling and auto-recovery."""
        from core.error_handling import RetryConfig, get_error_handler

        error_handler = get_error_handler()
        breaker_name = f"orderbook_stream_{symbol}"
        consecutive_failures = 0
        max_consecutive_failures = 10
        recovery_pause = 60  # Pause before recovery attempt

        while self.running:
            try:
                # Use error handler with circuit breaker
                ob = await error_handler.execute_with_breaker(
                    breaker_name,
                    self.adapter.watch_order_book,
                    symbol,
                    retry_config=RetryConfig(
                        max_retries=3,
                        backoff_base=1.0,
                        backoff_max=30.0,
                    ),
                )

                # Create and dispatch event
                event = OrderBookEvent(
                    type=EventType.ORDER_BOOK,
                    timestamp=time.time(),
                    symbol=symbol,
                    bids=ob.get("bids", []),
                    asks=ob.get("asks", []),
                )
                await self.engine.dispatch(event)

                # Reset failure count on success
                consecutive_failures = 0

            except asyncio.CancelledError:
                logger.info(f"📡 Order book stream for {symbol} cancelled")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(
                    f"❌ Error in order book stream for {symbol} "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures}): {e}"
                )

                # If too many consecutive failures, enter recovery mode (don't stop!)
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"⚠️ Order book stream for {symbol} failed {max_consecutive_failures} times. "
                        f"Entering recovery mode - pausing {recovery_pause}s before retry..."
                    )
                    # Reset circuit breaker
                    error_handler.reset_circuit_breaker(breaker_name)
                    consecutive_failures = 0
                    await asyncio.sleep(recovery_pause)
                    logger.info(f"🔄 Order book stream for {symbol} attempting recovery...")
                    continue

                # Exponential backoff
                backoff = min(2**consecutive_failures, 60)
                logger.info(f"⏳ Backing off for {backoff}s before retry")
                await asyncio.sleep(backoff)

    async def on_ticker(self, ticker: Dict[str, Any]):
        """Handle ticker update."""
        # Log every 10th tick for visibility
        if not hasattr(self, "_tick_count"):
            self._tick_count = 0
        self._tick_count += 1
        if self._tick_count % 10 == 0:
            logger.info(f"⚡ Tick: {ticker['symbol']} {ticker['last']}")

        event = TickEvent(
            type=EventType.TICK,
            timestamp=ticker["timestamp"] / 1000.0,
            symbol=ticker["symbol"],
            price=ticker["last"],
            volume=ticker.get("volume", 0.0),
        )
        # logger.info(f"debug: dispatching tick {event.price}")
        await self.engine.dispatch(event)
