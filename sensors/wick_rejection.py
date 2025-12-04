"""
WickRejection Sensor (V3).
Logic: Detects strong wick rejection patterns.

A wick rejection occurs when price tests a level but is
strongly rejected, leaving a long wick.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class WickRejectionV3(SensorV3):
    @property
    def name(self) -> str:
        return "WickRejection"

    def __init__(self, wick_ratio=2.0, min_wick_pct=0.003):
        """
        Args:
            wick_ratio: Min wick-to-body ratio for rejection
            min_wick_pct: Min wick size as % of price
        """
        self.wick_ratio = wick_ratio
        self.min_wick_pct = min_wick_pct

        self.candles = deque(maxlen=5)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.candles.append(candle)

        if len(self.candles) < 2:
            return None

        signal = self._check_wick_rejection(candle)
        return signal

    def _check_wick_rejection(self, candle):
        """Check for wick rejection pattern."""
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        body = abs(close - open_price)
        if body == 0:
            body = 0.0001  # Avoid division by zero

        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low

        avg_price = (high + low) / 2

        # Bullish rejection (long lower wick, small upper wick)
        if lower_wick > body * self.wick_ratio:
            wick_pct = lower_wick / avg_price
            if wick_pct > self.min_wick_pct:
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bullish_wick_rejection",
                        "wick_ratio": lower_wick / body,
                        "wick_pct": wick_pct,
                    },
                }

        # Bearish rejection (long upper wick, small lower wick)
        if upper_wick > body * self.wick_ratio:
            wick_pct = upper_wick / avg_price
            if wick_pct > self.min_wick_pct:
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "bearish_wick_rejection",
                        "wick_ratio": upper_wick / body,
                        "wick_pct": wick_pct,
                    },
                }

        return None
