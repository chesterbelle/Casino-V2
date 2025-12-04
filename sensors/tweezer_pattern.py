"""
TweezerPattern Sensor (V3).
Logic: Tweezer tops and bottoms detection.

Tweezer Bottom: Two candles with matching lows (bullish)
Tweezer Top: Two candles with matching highs (bearish)
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class TweezerPatternV3(SensorV3):
    @property
    def name(self) -> str:
        return "TweezerPattern"

    def __init__(self, max_diff_pct=0.0005, min_body_pct=0.002):
        """
        Args:
            max_diff_pct: Max difference between matching levels (as % of price)
            min_body_pct: Min body size of second candle (confirms reversal)
        """
        self.max_diff_pct = max_diff_pct
        self.min_body_pct = min_body_pct

        self.candles = deque(maxlen=5)

    def calculate(self, candle: dict) -> dict:
        self.candles.append(candle)

        if len(self.candles) < 2:
            return None

        signal = self._check_tweezer()
        return signal

    def _check_tweezer(self):
        """Check for tweezer pattern."""
        first = self.candles[-2]
        second = self.candles[-1]

        avg_price = (first["high"] + first["low"] + second["high"] + second["low"]) / 4

        # Tweezer Bottom
        low_diff = abs(first["low"] - second["low"])
        low_diff_pct = low_diff / avg_price

        if low_diff_pct < self.max_diff_pct:
            # First should be bearish, second bullish
            first_bearish = first["close"] < first["open"]
            second_bullish = second["close"] > second["open"]
            second_body = abs(second["close"] - second["open"]) / avg_price

            if first_bearish and second_bullish and second_body > self.min_body_pct:
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "tweezer_bottom",
                        "low_diff_pct": low_diff_pct,
                        "matching_low": min(first["low"], second["low"]),
                    },
                }

        # Tweezer Top
        high_diff = abs(first["high"] - second["high"])
        high_diff_pct = high_diff / avg_price

        if high_diff_pct < self.max_diff_pct:
            # First should be bullish, second bearish
            first_bullish = first["close"] > first["open"]
            second_bearish = second["close"] < second["open"]
            second_body = abs(second["close"] - second["open"]) / avg_price

            if first_bullish and second_bearish and second_body > self.min_body_pct:
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "tweezer_top",
                        "high_diff_pct": high_diff_pct,
                        "matching_high": max(first["high"], second["high"]),
                    },
                }

        return None
