"""
SmartRange Sensor (V3).
Logic: Smart range scalping within defined boundaries.

Identifies optimal entry points at range boundaries
with momentum confirmation.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class SmartRangeV3(SensorV3):
    @property
    def name(self) -> str:
        return "SmartRange"

    def __init__(self, lookback=20, boundary_pct=0.1, momentum_period=5):
        """
        Args:
            lookback: Period to establish range
            boundary_pct: Entry zone as % from boundary (0.1 = 10%)
            momentum_period: Period for momentum confirmation
        """
        self.lookback = lookback
        self.boundary_pct = boundary_pct
        self.momentum_period = momentum_period

        self.candles = deque(maxlen=lookback + 10)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        self.candles.append(candle)

        if len(self.candles) < self.lookback:
            return None

        signal = self._check_range_entry(candle)
        return signal

    def _check_range_entry(self, candle):
        """Check for range boundary entry."""
        candles = list(self.candles)[:-1]  # Exclude current

        highs = [c["high"] for c in candles[-self.lookback :]]
        lows = [c["low"] for c in candles[-self.lookback :]]

        range_high = max(highs)
        range_low = min(lows)
        range_size = range_high - range_low

        if range_size == 0:
            return None

        close = candle["close"]
        open_price = candle["open"]

        # Position within range (0 = bottom, 1 = top)
        position = (close - range_low) / range_size

        # Entry zone at bottom
        bottom_zone = position < self.boundary_pct

        # Entry zone at top
        top_zone = position > (1 - self.boundary_pct)

        # Check momentum (recent closes)
        recent_candles = list(self.candles)[-self.momentum_period :]
        if len(recent_candles) < 2:
            return None

        momentum_up = close > recent_candles[0]["close"]
        momentum_down = close < recent_candles[0]["close"]

        bullish_candle = close > open_price
        bearish_candle = close < open_price

        # Long at bottom with bullish momentum
        if bottom_zone and bullish_candle and momentum_up:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "range_position": position,
                    "range_high": range_high,
                    "range_low": range_low,
                },
            }

        # Short at top with bearish momentum
        if top_zone and bearish_candle and momentum_down:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "range_position": position,
                    "range_high": range_high,
                    "range_low": range_low,
                },
            }

        return None
