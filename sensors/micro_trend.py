"""
MicroTrend Sensor (V3).
Logic: Detects micro trend pullbacks for scalping.

Identifies short-term trends and entries on pullbacks.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class MicroTrendV3(SensorV3):
    @property
    def name(self) -> str:
        return "MicroTrend"

    def __init__(self, trend_period=10, pullback_period=3, min_trend_pct=0.002):
        """
        Args:
            trend_period: Period to establish micro trend
            pullback_period: Period to identify pullback
            min_trend_pct: Minimum trend move as % to qualify
        """
        self.trend_period = trend_period
        self.pullback_period = pullback_period
        self.min_trend_pct = min_trend_pct

        self.candles = deque(maxlen=trend_period + pullback_period + 5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        self.candles.append(candle)

        if len(self.candles) < self.trend_period + self.pullback_period:
            return None

        signal = self._check_micro_trend(candle)
        return signal

    def _check_micro_trend(self, candle):
        """Check for micro trend pullback setup."""
        candles = list(self.candles)

        # Split into trend and pullback periods
        trend_candles = candles[: self.trend_period]
        pullback_candles = candles[self.trend_period :]

        # Calculate trend direction
        trend_start = trend_candles[0]["close"]
        trend_end = trend_candles[-1]["close"]
        trend_pct = (trend_end - trend_start) / trend_start if trend_start > 0 else 0

        # Check for micro uptrend with pullback
        if trend_pct > self.min_trend_pct:
            # Verify pullback (recent candles moving against trend)
            pullback_closes = [c["close"] for c in pullback_candles]
            is_pullback = pullback_closes[-1] < pullback_closes[0]

            # Current candle should show reversal (bullish)
            bullish = candle["close"] > candle["open"]

            if is_pullback and bullish:
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "uptrend_pullback",
                        "trend_pct": trend_pct,
                    },
                }

        # Check for micro downtrend with pullback
        if trend_pct < -self.min_trend_pct:
            # Verify pullback (recent candles moving against trend)
            pullback_closes = [c["close"] for c in pullback_candles]
            is_pullback = pullback_closes[-1] > pullback_closes[0]

            # Current candle should show reversal (bearish)
            bearish = candle["close"] < candle["open"]

            if is_pullback and bearish:
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "downtrend_pullback",
                        "trend_pct": trend_pct,
                    },
                }

        return None
