"""
SupportResistance Sensor (V3).
Logic: Detects bounces off support and resistance levels.

Uses pivot points and recent swing highs/lows as S/R levels.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class SupportResistanceV3(SensorV3):
    @property
    def name(self) -> str:
        return "SupportResistance"

    def __init__(self, lookback=20, touch_tolerance=0.001, bounce_threshold=0.002):
        """
        Args:
            lookback: Period for finding S/R levels
            touch_tolerance: How close price must get to level (as %)
            bounce_threshold: Min bounce for confirmation (as %)
        """
        self.lookback = lookback
        self.touch_tolerance = touch_tolerance
        self.bounce_threshold = bounce_threshold

        self.candles = deque(maxlen=lookback + 10)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.candles.append(candle)

        if len(self.candles) < self.lookback:
            return None

        # Find S/R levels
        support_levels, resistance_levels = self._find_sr_levels()

        # Check for bounce
        signal = self._check_bounce(candle, support_levels, resistance_levels)
        return signal

    def _find_sr_levels(self):
        """Find support and resistance levels from swing points."""
        candles = list(self.candles)[:-1]

        support_levels = []
        resistance_levels = []

        for i in range(2, len(candles) - 2):
            # Swing low (support)
            if (
                candles[i]["low"] < candles[i - 1]["low"]
                and candles[i]["low"] < candles[i - 2]["low"]
                and candles[i]["low"] < candles[i + 1]["low"]
                and candles[i]["low"] < candles[i + 2]["low"]
            ):
                support_levels.append(candles[i]["low"])

            # Swing high (resistance)
            if (
                candles[i]["high"] > candles[i - 1]["high"]
                and candles[i]["high"] > candles[i - 2]["high"]
                and candles[i]["high"] > candles[i + 1]["high"]
                and candles[i]["high"] > candles[i + 2]["high"]
            ):
                resistance_levels.append(candles[i]["high"])

        # Add recent extremes
        if candles:
            recent_high = max(c["high"] for c in candles[-10:])
            recent_low = min(c["low"] for c in candles[-10:])
            resistance_levels.append(recent_high)
            support_levels.append(recent_low)

        return support_levels, resistance_levels

    def _check_bounce(self, candle, support_levels, resistance_levels):
        """Check for bounce off S/R level."""
        close = candle["close"]
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]

        # Check support bounce
        for level in support_levels:
            if level == 0:
                continue

            touch_distance = abs(low - level) / level
            if touch_distance < self.touch_tolerance:
                bounce = (close - low) / low if low > 0 else 0
                bullish = close > open_price

                if bounce > self.bounce_threshold and bullish:
                    return {
                        "side": "LONG",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "support_bounce",
                            "level": level,
                            "bounce_pct": bounce,
                        },
                    }

        # Check resistance bounce
        for level in resistance_levels:
            if level == 0:
                continue

            touch_distance = abs(high - level) / level
            if touch_distance < self.touch_tolerance:
                bounce = (high - close) / high if high > 0 else 0
                bearish = close < open_price

                if bounce > self.bounce_threshold and bearish:
                    return {
                        "side": "SHORT",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "resistance_bounce",
                            "level": level,
                            "bounce_pct": bounce,
                        },
                    }

        return None
