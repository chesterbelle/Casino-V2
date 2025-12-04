"""
ThreeBar Sensor (V3).
Logic: Three bar reversal pattern detection.

Pattern: Three consecutive candles showing:
1. Trend candle
2. Small body (indecision)
3. Reversal candle closing past first candle
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class ThreeBarV3(SensorV3):
    @property
    def name(self) -> str:
        return "ThreeBar"

    def __init__(self, range_decrease=0.7, close_threshold=0.4):
        """
        Args:
            range_decrease: Middle candle should be this % of first candle range
            close_threshold: Third candle should close past this % of first
        """
        self.range_decrease = range_decrease
        self.close_threshold = close_threshold

        self.candles = deque(maxlen=5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)

        if len(self.candles) < 3:
            return None

        signal = self._check_three_bar()
        return signal

    def _check_three_bar(self):
        """Check for three bar reversal pattern."""
        candles = list(self.candles)
        first = candles[-3]
        second = candles[-2]
        third = candles[-1]

        first_range = first["high"] - first["low"]
        second_range = second["high"] - second["low"]

        if first_range == 0:
            return None

        # Middle candle should be smaller
        range_ratio = second_range / first_range
        if range_ratio > self.range_decrease:
            return None

        # Bullish three bar: Down-Small-Up
        first_bearish = first["close"] < first["open"]
        third_bullish = third["close"] > third["open"]

        if first_bearish and third_bullish:
            # Third should close above some % of first candle range
            first_body_top = first["open"]
            if third["close"] > first_body_top - (first_range * self.close_threshold):
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bullish_three_bar",
                        "range_ratio": range_ratio,
                    },
                }

        # Bearish three bar: Up-Small-Down
        first_bullish = first["close"] > first["open"]
        third_bearish = third["close"] < third["open"]

        if first_bullish and third_bearish:
            first_body_bottom = first["open"]
            if third["close"] < first_body_bottom + (first_range * self.close_threshold):
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bearish_three_bar",
                        "range_ratio": range_ratio,
                    },
                }

        return None
