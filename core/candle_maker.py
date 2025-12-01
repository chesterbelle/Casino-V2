"""
Candle Maker Component.
Aggregates ticks into candles and emits CandleEvents.
"""

import logging
import time
from typing import Optional

from .events import CandleEvent, EventType, TickEvent

logger = logging.getLogger(__name__)


class CandleMaker:
    """
    Subscribes to TICK events and emits CANDLE events.
    """

    def __init__(self, engine, timeframe_seconds=60):
        self.engine = engine
        self.timeframe = timeframe_seconds
        self.current_candle: Optional[dict] = None
        self.last_candle_time = 0

        # Subscribe to Ticks
        self.engine.subscribe(EventType.TICK, self.on_tick)

    async def on_tick(self, tick: TickEvent):
        """Process incoming tick."""
        # Calculate candle start time (floor to minute)
        tick_time = int(tick.timestamp)
        candle_start_time = tick_time - (tick_time % self.timeframe)
        
        # Debug tick time
        # logger.info(f"DEBUG: Tick {tick_time} -> Candle Start {candle_start_time} (Last: {self.last_candle_time})")

        # If we have a current candle and we moved to a new minute
        if self.current_candle and candle_start_time > self.last_candle_time:
            # Emit the closed candle
            await self._emit_candle(self.current_candle)
            # Reset for new candle
            self.current_candle = None

        # Initialize new candle if needed
        if not self.current_candle:
            self.current_candle = {
                "timestamp": candle_start_time,
                "symbol": tick.symbol,
                "open": tick.price,
                "high": tick.price,
                "low": tick.price,
                "close": tick.price,
                "volume": tick.volume,
            }
            self.last_candle_time = candle_start_time
        else:
            # Update current candle
            self.current_candle["high"] = max(self.current_candle["high"], tick.price)
            self.current_candle["low"] = min(self.current_candle["low"], tick.price)
            self.current_candle["close"] = tick.price
            self.current_candle["volume"] += tick.volume

    async def _emit_candle(self, candle_data: dict):
        """Emit a closed candle event."""
        event = CandleEvent(
            type=EventType.CANDLE,
            timestamp=time.time(),  # Event timestamp
            symbol=candle_data["symbol"],
            timeframe="1m",  # Hardcoded for now
            open=candle_data["open"],
            high=candle_data["high"],
            low=candle_data["low"],
            close=candle_data["close"],
            volume=candle_data["volume"],
        )
        logger.info(f"🕯️ Candle Closed: {event.close} | Vol: {event.volume}")
        await self.engine.dispatch(event)
