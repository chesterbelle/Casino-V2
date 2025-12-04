"""
LongTail Sensor (V3).
Logic: Detects long-tailed distribution patterns.

Long tails indicate exhaustion and potential reversal.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class LongTailV3(SensorV3):
    @property
    def name(self) -> str:
        return "LongTail"

    def __init__(self, lookback=5, tail_factor=3.0, min_tail_pct=0.003):
        """
        Args:
            lookback: Period to compare tail size
            tail_factor: Current tail must be this many times larger
            min_tail_pct: Minimum tail size as % of price
        """
        self.lookback = lookback
        self.tail_factor = tail_factor
        self.min_tail_pct = min_tail_pct

        self.candles = deque(maxlen=lookback + 5)

    def calculate(self, candle: dict) -> dict:
        self.candles.append(candle)

        if len(self.candles) < self.lookback:
            return None

        signal = self._check_long_tail(candle)
        return signal

    def _check_long_tail(self, candle):
        """Check for long tail pattern."""
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        body_top = max(open_price, close)
        body_bottom = min(open_price, close)

        upper_tail = high - body_top
        lower_tail = body_bottom - low

        avg_price = (high + low) / 2
        if avg_price == 0:
            return None

        # Calculate average tail size from recent candles
        prev_candles = list(self.candles)[:-1]
        prev_lower_tails = []
        prev_upper_tails = []

        for c in prev_candles:
            c_body_top = max(c["open"], c["close"])
            c_body_bottom = min(c["open"], c["close"])
            prev_lower_tails.append(c_body_bottom - c["low"])
            prev_upper_tails.append(c["high"] - c_body_top)

        avg_lower_tail = np.mean(prev_lower_tails) if prev_lower_tails else 0
        avg_upper_tail = np.mean(prev_upper_tails) if prev_upper_tails else 0

        # Long lower tail (bullish)
        lower_tail_pct = lower_tail / avg_price
        if lower_tail_pct > self.min_tail_pct:
            if avg_lower_tail > 0 and lower_tail > avg_lower_tail * self.tail_factor:
                if close > open_price:  # Bullish close
                    return {
                        "side": "LONG",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "long_lower_tail",
                            "tail_pct": lower_tail_pct,
                            "tail_factor": lower_tail / avg_lower_tail,
                        },
                    }

        # Long upper tail (bearish)
        upper_tail_pct = upper_tail / avg_price
        if upper_tail_pct > self.min_tail_pct:
            if avg_upper_tail > 0 and upper_tail > avg_upper_tail * self.tail_factor:
                if close < open_price:  # Bearish close
                    return {
                        "side": "SHORT",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "long_upper_tail",
                            "tail_pct": upper_tail_pct,
                            "tail_factor": upper_tail / avg_upper_tail,
                        },
                    }

        return None
