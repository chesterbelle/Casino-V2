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
            if f"trades_{symbol}" not in self._tasks:
                self._tasks[f"trades_{symbol}"] = asyncio.create_task(self._watch_trades_loop(symbol))

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

    async def subscribe_trades(self, symbol: str):
        """Subscribe to trade updates for a symbol."""
        self._subscribed_symbols.add(symbol)

        if self.running:
            if f"trades_{symbol}" in self._tasks:
                return
            logger.info(f"📡 Subscribing to trades: {symbol}")
            self._tasks[f"trades_{symbol}"] = asyncio.create_task(self._watch_trades_loop(symbol))
        else:
            logger.info(f"📝 Queued trades subscription: {symbol}")

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
                # Use error handler with circuit breaker AND timeout
                # We wrap the execution in wait_for to prevent hanging if the queue is empty
                # and the websocket is dead but not closed.
                ticker = await asyncio.wait_for(
                    error_handler.execute_with_breaker(
                        breaker_name,
                        self.adapter.watch_ticker,
                        symbol,
                        retry_config=RetryConfig(
                            max_retries=3,
                            backoff_base=1.0,
                            backoff_max=30.0,
                        ),
                    ),
                    timeout=10.0,  # 10s timeout for ticker (should be frequent)
                )
                await self.on_ticker(ticker)

                # Reset failure count on success
                consecutive_failures = 0

            except asyncio.TimeoutError:
                # Timeout is treated as a failure to trigger recovery if persistent
                consecutive_failures += 1
                logger.warning(
                    f"⚠️ Ticker stream for {symbol} timed out "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures})"
                )
                if consecutive_failures >= max_consecutive_failures:
                    # ... recovery logic ...
                    logger.warning(
                        f"⚠️ Ticker stream for {symbol} failed {max_consecutive_failures} times (Timeout). "
                        f"Entering recovery mode - pausing {recovery_pause}s before retry..."
                    )
                    error_handler.reset_circuit_breaker(breaker_name)
                    consecutive_failures = 0
                    await asyncio.sleep(recovery_pause)
                    logger.info(f"🔄 Ticker stream for {symbol} attempting recovery...")
                    continue

                # Short backoff on timeout
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                logger.info(f"📡 Ticker stream for {symbol} cancelled")
                break
            except Exception as e:
                consecutive_failures += 1
                # ... existing error handling ...
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

    async def _watch_trades_loop(self, symbol: str):
        """Continuous loop to watch trades with error handling and auto-recovery."""
        from core.error_handling import RetryConfig, get_error_handler

        error_handler = get_error_handler()
        breaker_name = f"trades_stream_{symbol}"
        consecutive_failures = 0
        max_consecutive_failures = 10
        recovery_pause = 60  # Pause before recovery attempt

        while self.running:
            try:
                # Use error handler with circuit breaker AND timeout
                trade = await asyncio.wait_for(
                    error_handler.execute_with_breaker(
                        breaker_name,
                        self.adapter.watch_trades,
                        symbol,
                        retry_config=RetryConfig(
                            max_retries=3,
                            backoff_base=1.0,
                            backoff_max=30.0,
                        ),
                    ),
                    timeout=30.0,  # 30s timeout for trades (might be less frequent)
                )

                # Create and dispatch TickEvent with REAL side
                event = TickEvent(
                    type=EventType.TICK,
                    timestamp=trade["timestamp"] / 1000.0,
                    symbol=symbol,
                    price=trade["price"],
                    volume=trade["amount"],
                    side=trade["side"],  # REAL SIDE from Exchange
                )
                await self.engine.dispatch(event)

                consecutive_failures = 0

            except asyncio.TimeoutError:
                # Timeout is treated as a failure to trigger recovery if persistent
                # For trades, silence might be normal if low volume, but we expect heartbeats/pings usually.
                # If we rely on queue.get(), timeout means NO TRADES.
                # We should probably be lenient here or check connection status.
                # For now, let's just log and continue without incrementing failure count aggressively
                # UNLESS we know the connection is dead.
                # Actually, if we timeout, we should just loop again.
                # But if we loop 100 times with timeout, is it a failure?
                # Let's assume silence is okay for trades, but we want to check "running" flag.
                pass

            except asyncio.CancelledError:
                logger.info(f"📡 Trades stream for {symbol} cancelled")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(
                    f"❌ Error in trades stream for {symbol} "
                    f"(consecutive failures: {consecutive_failures}/{max_consecutive_failures}): {e}"
                )

                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"⚠️ Trades stream for {symbol} failed {max_consecutive_failures} times. "
                        f"Entering recovery mode - pausing {recovery_pause}s before retry..."
                    )
                    error_handler.reset_circuit_breaker(breaker_name)
                    consecutive_failures = 0
                    await asyncio.sleep(recovery_pause)
                    logger.info(f"🔄 Trades stream for {symbol} attempting recovery...")
                    continue

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

        # Ticker events are still useful for price updates, but we don't use them for Footprint anymore
        # because we have the real trades stream.
        event = TickEvent(
            type=EventType.TICK,
            timestamp=ticker["timestamp"] / 1000.0,
            symbol=ticker["symbol"],
            price=float(ticker["last"]),
            volume=ticker.get("volume", 0.0),
            side="UNKNOWN",  # Side comes from trades stream now
        )
        await self.engine.dispatch(event)
