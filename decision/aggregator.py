"""
Signal Aggregator for Casino-V3.
Collects signals from multiple sensors and applies intelligent scoring.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from config.strategies import get_strategy_for_sensor
from core.events import Event, EventType, SignalEvent

from .sensor_tracker import SensorTracker

logger = logging.getLogger(__name__)

# Configuration (previously from config.paroli)
SIGNAL_TIMEOUT_MS = 100  # Wait 100ms for all sensors to fire
CONFLICT_DELTA_THRESHOLD = 0.02  # Min score difference to resolve conflict


class AggregatedSignalEvent(Event):
    """Aggregated signal from multiple sensors."""

    def __init__(
        self,
        symbol: str,
        candle_timestamp: float,
        selected_sensor: str,
        sensor_score: float,
        side: str,
        confidence: float,
        total_signals: int,
        metadata: Optional[Dict[str, Any]] = None,
        strategy_name: Optional[str] = None,
    ):
        super().__init__(type=EventType.AGGREGATED_SIGNAL, timestamp=time.time())
        self.symbol = symbol
        self.candle_timestamp = candle_timestamp
        self.selected_sensor = selected_sensor
        self.sensor_score = sensor_score
        self.side = side
        self.confidence = confidence
        self.total_signals = total_signals
        self.metadata = metadata
        self.strategy_name = strategy_name


class SignalAggregatorV3:
    """
    Aggregates signals from multiple sensors using intelligent scoring.

    Instead of simple voting, scores each signal based on sensor's historical
    performance (expectancy, win rate, profit factor, etc).
    """

    def __init__(self, engine):
        self.engine = engine
        self.signal_buffer: Dict[float, List[SignalEvent]] = defaultdict(list)
        self.current_candle_timestamp: Optional[float] = None
        self.timeout_task: Optional[asyncio.Task] = None

        # Initialize sensor tracker
        self.tracker = SensorTracker()

        # Subscribe to SIGNAL events
        self.engine.subscribe(EventType.SIGNAL, self.on_signal)

        # Subscribe to CANDLE events to track candle changes
        self.engine.subscribe(EventType.CANDLE, self.on_candle)

        logger.info("✅ SignalAggregator initialized with intelligent scoring")

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
        """Process buffered signals using intelligent scoring."""
        signals = self.signal_buffer.get(candle_ts, [])

        if not signals:
            return

        # 1. Filter by Score (Strict Quality Control)
        # TEMPORARILY DISABLED: Allow all signals to validate demo mode
        # Threshold lowered to 0.5 to allow new sensors to trade (Cold Start)
        # Previously 0.6, which blocked sensors with default score (0.5)
        MIN_SCORE_THRESHOLD = 0.0  # TEMP: Disabled for demo validation

        valid_signals = [s for s in signals if self.tracker.get_sensor_score(s.sensor_id) >= MIN_SCORE_THRESHOLD]

        if not valid_signals:
            logger.debug(
                f"   All signals filtered out for candle {candle_ts} due to low score (< {MIN_SCORE_THRESHOLD})"
            )
            # Emit SKIP signal if no valid signals remain
            aggregated = AggregatedSignalEvent(
                symbol=signals[0].symbol,  # Use symbol from original signals, even if none are valid
                candle_timestamp=candle_ts,
                selected_sensor="None",
                sensor_score=0.0,
                side="SKIP",
                confidence=0.0,
                total_signals=len(signals),
            )
            await self.engine.dispatch(aggregated)
            # Clear processed signals
            if candle_ts in self.signal_buffer:
                del self.signal_buffer[candle_ts]
            return

        # 2. Extract HTF context from context sensors (HigherTFTrend, HurstRegime)
        context_sensors = {"HigherTFTrend", "HurstRegime", "MTFImpulse"}
        htf_context = None  # "LONG", "SHORT", or None

        for signal in valid_signals:
            if signal.sensor_id in context_sensors:
                htf_context = signal.side
                logger.debug(f"📊 HTF Context: {signal.sensor_id} = {htf_context}")
                break

        # 3. Score all valid signals with context adjustment
        scored_signals = []
        CONTEXT_BOOST = 1.2  # 20% boost for aligned signals
        CONTEXT_PENALTY = 0.8  # 20% penalty for opposing signals

        for signal in valid_signals:
            sensor_id = signal.sensor_id if hasattr(signal, "sensor_id") else "Unknown"
            base_score = self.tracker.get_sensor_score(sensor_id)

            # Apply context adjustment (skip for context sensors themselves)
            if htf_context and sensor_id not in context_sensors:
                if signal.side == htf_context:
                    # Signal aligns with HTF trend - boost
                    score = base_score * CONTEXT_BOOST
                    logger.debug(
                        f"   ⬆️ {sensor_id} boosted: {base_score:.3f} → {score:.3f} (aligned with {htf_context})"
                    )
                else:
                    # Signal opposes HTF trend - penalize
                    score = base_score * CONTEXT_PENALTY
                    logger.debug(f"   ⬇️ {sensor_id} penalized: {base_score:.3f} → {score:.3f} (against {htf_context})")
            else:
                score = base_score

            scored_signals.append({"signal": signal, "sensor_id": sensor_id, "score": score, "side": signal.side})

        # Select best signal
        selected = self._select_best_signal(scored_signals)

        if selected is None:
            logger.info("📊 No signal selected (all below threshold or conflict unresolved)")
            # Emit SKIP signal
            aggregated = AggregatedSignalEvent(
                symbol=signals[0].symbol,
                candle_timestamp=candle_ts,
                selected_sensor="None",
                sensor_score=0.0,
                side="SKIP",
                confidence=0.0,
                total_signals=len(signals),
            )
        else:
            # Get strategy context for selected sensor
            strategies = get_strategy_for_sensor(selected["sensor_id"])
            strategy_name = strategies[0] if strategies else "Unknown"

            logger.info(
                f"📊 Selected: {selected['sensor_id']} ({selected['side']}) | "
                f"Score: {selected['score']:.3f} | "
                f"Strategy: {strategy_name} | "
                f"Total signals: {len(signals)}"
            )

            aggregated = AggregatedSignalEvent(
                symbol=selected["signal"].symbol,
                candle_timestamp=candle_ts,
                selected_sensor=selected["sensor_id"],
                sensor_score=selected["score"],
                side=selected["side"],
                confidence=selected["score"],  # Score is our confidence
                total_signals=len(signals),
                metadata=selected["signal"].metadata,
                strategy_name=strategy_name,
            )

        await self.engine.dispatch(aggregated)

        # Clear processed signals
        if candle_ts in self.signal_buffer:
            del self.signal_buffer[candle_ts]

    def _select_best_signal(self, scored_signals: List[Dict]) -> Optional[Dict]:
        """
        Select the best signal from scored signals.

        Logic:
        1. Group by direction (LONG/SHORT)
        2. Pick highest score in each direction
        3. If same direction: return best
        4. If opposite directions: return best if delta > threshold, else SKIP

        Returns:
            Selected signal dict or None (SKIP)
        """
        if not scored_signals:
            return None

        # Group by direction
        long_signals = [s for s in scored_signals if s["side"] == "LONG"]
        short_signals = [s for s in scored_signals if s["side"] == "SHORT"]

        # Case 1: Only one direction - pick best
        if long_signals and not short_signals:
            best = max(long_signals, key=lambda s: s["score"])
            logger.debug(f"   Best LONG: {best['sensor_id']} (score: {best['score']:.3f})")
            return best

        if short_signals and not long_signals:
            best = max(short_signals, key=lambda s: s["score"])
            logger.debug(f"   Best SHORT: {best['sensor_id']} (score: {best['score']:.3f})")
            return best

        # Case 2: Conflicting directions - pick best overall if delta is significant
        if long_signals and short_signals:
            best_long = max(long_signals, key=lambda s: s["score"])
            best_short = max(short_signals, key=lambda s: s["score"])

            score_delta = abs(best_long["score"] - best_short["score"])

            # If difference is too small, skip (no clear winner)
            if score_delta < CONFLICT_DELTA_THRESHOLD:
                logger.info(
                    f"⚖️ Conflict unresolved | "
                    f"LONG: {best_long['sensor_id']} ({best_long['score']:.3f}) vs "
                    f"SHORT: {best_short['sensor_id']} ({best_short['score']:.3f}) | "
                    f"Delta: {score_delta:.3f} < {CONFLICT_DELTA_THRESHOLD}"
                )
                return None

            # Return the higher scored signal
            winner = best_long if best_long["score"] > best_short["score"] else best_short
            loser = best_short if winner == best_long else best_long
            logger.info(
                f"⚖️ Conflict resolved | "
                f"Winner: {winner['sensor_id']} ({winner['side']}, {winner['score']:.3f}) | "
                f"Loser: {loser['sensor_id']} ({loser['side']}, {loser['score']:.3f})"
            )
            return winner

        # Case 3: No valid signals
        return None
