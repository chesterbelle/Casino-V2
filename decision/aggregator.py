"""
Signal Aggregator for Casino-V3.
Collects signals from multiple sensors and applies voting logic.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from config import paroli

from core.events import Event, EventType, SignalEvent

logger = logging.getLogger(__name__)

# Configuration
VOTING_THRESHOLD = getattr(paroli, "VOTING_THRESHOLD", 1.5)
SIGNAL_TIMEOUT_MS = getattr(paroli, "SIGNAL_TIMEOUT_MS", 100)


class AggregatedSignalEvent(Event):
    """Aggregated signal from multiple sensors."""

    def __init__(
        self,
        symbol: str,
        candle_timestamp: float,
        long_votes: int,
        short_votes: int,
        total_sensors: int,
        side: str,
        confidence: float,
    ):
        super().__init__(type=EventType.AGGREGATED_SIGNAL, timestamp=time.time())
        self.symbol = symbol
        self.candle_timestamp = candle_timestamp
        self.long_votes = long_votes
        self.short_votes = short_votes
        self.total_sensors = total_sensors
        self.side = side
        self.confidence = confidence


class SignalAggregatorV3:
    """
    Aggregates signals from multiple sensors per candle.
    Applies simple majority voting with threshold.
    """

    def __init__(self, engine):
        self.engine = engine
        self.signal_buffer: Dict[float, List[SignalEvent]] = defaultdict(list)
        self.current_candle_timestamp: Optional[float] = None
        self.timeout_task: Optional[asyncio.Task] = None

        # Subscribe to SIGNAL events
        self.engine.subscribe(EventType.SIGNAL, self.on_signal)

        # Subscribe to CANDLE events to track candle changes
        self.engine.subscribe(EventType.CANDLE, self.on_candle)

        logger.info("✅ SignalAggregator initialized")

    async def on_candle(self, event):
        """Track new candles to reset signal buffer."""
        # If we have a pending candle, process it first
        if self.current_candle_timestamp and self.signal_buffer.get(self.current_candle_timestamp):
            await self._process_signals(self.current_candle_timestamp)

        # Update to new candle
        self.current_candle_timestamp = event.timestamp

        # Clean old buffers (keep last 5 candles only)
        if len(self.signal_buffer) > 5:
            oldest = min(self.signal_buffer.keys())
            del self.signal_buffer[oldest]

    async def on_signal(self, event: SignalEvent):
        """Collect signal and start timeout if first signal for this candle."""
        candle_ts = self.current_candle_timestamp
        if candle_ts is None:
            logger.warning("⚠️ Received signal but no candle timestamp set")
            return

        # Add signal to buffer
        self.signal_buffer[candle_ts].append(event)

        # If this is the first signal for this candle, start timeout
        if len(self.signal_buffer[candle_ts]) == 1:
            self.timeout_task = asyncio.create_task(self._timeout_handler(candle_ts))
            logger.debug(f"🕐 Started {SIGNAL_TIMEOUT_MS}ms timeout for candle {candle_ts}")

    async def _timeout_handler(self, candle_ts: float):
        """Wait for timeout, then process signals."""
        await asyncio.sleep(SIGNAL_TIMEOUT_MS / 1000.0)
        await self._process_signals(candle_ts)

    async def _process_signals(self, candle_ts: float):
        """Process buffered signals and emit aggregated signal."""
        signals = self.signal_buffer.get(candle_ts, [])

        if not signals:
            return

        # Count votes
        long_votes = sum(1 for s in signals if s.side == "LONG")
        short_votes = sum(1 for s in signals if s.side == "SHORT")
        total = len(signals)

        # Determine consensus
        side = "SKIP"
        confidence = 0.0

        if long_votes > short_votes * VOTING_THRESHOLD:
            side = "LONG"
            confidence = long_votes / total
        elif short_votes > long_votes * VOTING_THRESHOLD:
            side = "SHORT"
            confidence = short_votes / total

        # Log voting results
        logger.info(
            f"📊 Voting Results: {long_votes} LONG, {short_votes} SHORT → {side} (confidence: {confidence:.2%})"
        )

        # Emit aggregated signal
        aggregated = AggregatedSignalEvent(
            symbol=signals[0].symbol,
            candle_timestamp=candle_ts,
            long_votes=long_votes,
            short_votes=short_votes,
            total_sensors=total,
            side=side,
            confidence=confidence,
        )

        await self.engine.dispatch(aggregated)

        # Clear processed signals
        if candle_ts in self.signal_buffer:
            del self.signal_buffer[candle_ts]
