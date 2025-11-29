"""
Data Feed Layer for Casino-V3.
Manages Websocket streams via CCXTAdapter and dispatches events to the Engine.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Set

from exchanges.adapters.ccxt_adapter import CCXTAdapter

from .events import EventType, OrderBookEvent, TickEvent

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Manages websocket streams and pushes events to the Engine.
    """

    def __init__(self, adapter: CCXTAdapter, engine):
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
        """Continuous loop to watch ticker."""
        while self.running:
            try:
                ticker = await self.adapter.watch_ticker(symbol)
                await self.on_ticker(ticker)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in ticker stream for {symbol}: {e}")
                await asyncio.sleep(1)  # Backoff on error

    async def _watch_order_book_loop(self, symbol: str):
        """Continuous loop to watch order book."""
        while self.running:
            try:
                ob = await self.adapter.watch_order_book(symbol)

                # Create and dispatch event
                event = OrderBookEvent(
                    type=EventType.ORDER_BOOK,
                    timestamp=time.time(),
                    symbol=symbol,
                    bids=ob.get("bids", []),
                    asks=ob.get("asks", []),
                )
                await self.engine.dispatch(event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in order book stream for {symbol}: {e}")
                await asyncio.sleep(1)  # Backoff on error

    async def on_ticker(self, ticker: Dict[str, Any]):
        """Handle ticker update."""
        # logger.debug(f"Tick received: {ticker['symbol']} {ticker['last']}")
        event = TickEvent(
            type=EventType.TICK,
            timestamp=ticker["timestamp"] / 1000.0,
            symbol=ticker["symbol"],
            price=ticker["last"],
            volume=ticker.get("baseVolume", 0.0),
        )
        # logger.info(f"debug: dispatching tick {event.price}")
        await self.engine.dispatch(event)
