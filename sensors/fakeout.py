"""
Fakeout Sensor (V3).
Logic: Detects fakeout/false breakout reversals.

A fakeout occurs when price breaks a key level but immediately
reverses, trapping breakout traders.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class FakeoutV3(SensorV3):
    @property
    def name(self) -> str:
        return "Fakeout"

    def __init__(self, lookback=10, breakout_threshold=0.002, reversal_body_pct=0.6):
        """
        Args:
            lookback: Period to establish range high/low
            breakout_threshold: Min % to consider a breakout
            reversal_body_pct: Min body % for reversal confirmation
        """
        self.lookback = lookback
        self.breakout_threshold = breakout_threshold
        self.reversal_body_pct = reversal_body_pct

        self.candles = deque(maxlen=lookback + 5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)

        if len(self.candles) < self.lookback:
            return None

        # Find range boundaries
        range_high, range_low = self._find_range()

        # Check for fakeout
        signal = self._check_fakeout(candle, range_high, range_low)
        return signal

    def _find_range(self):
        """Find the recent range high and low."""
        candles = list(self.candles)[:-1]  # Exclude current

        highs = [c["high"] for c in candles[-self.lookback :]]
        lows = [c["low"] for c in candles[-self.lookback :]]

        return max(highs), min(lows)

    def _check_fakeout(self, candle, range_high, range_low):
        """Check for fakeout pattern."""
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        candle_range = high - low
        if candle_range == 0:
            return None

        body = abs(close - open_price)
        body_pct = body / candle_range

        # Bullish fakeout: Broke below range but closed inside
        if low < range_low:
            broke_below = (range_low - low) / range_low > self.breakout_threshold
            closed_inside = close > range_low
            bullish_body = close > open_price and body_pct > self.reversal_body_pct

            if broke_below and closed_inside and bullish_body:
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bullish_fakeout",
                        "range_low": range_low,
                        "low": low,
                        "breakout_depth": (range_low - low) / range_low,
                    },
                }

        # Bearish fakeout: Broke above range but closed inside
        if high > range_high:
            broke_above = (high - range_high) / range_high > self.breakout_threshold
            closed_inside = close < range_high
            bearish_body = close < open_price and body_pct > self.reversal_body_pct

            if broke_above and closed_inside and bearish_body:
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bearish_fakeout",
                        "range_high": range_high,
                        "high": high,
                        "breakout_depth": (high - range_high) / range_high,
                    },
                }

        return None
