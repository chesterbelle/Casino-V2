"""
Marubozu Momentum Sensor

Detects strong directional candles with minimal wicks (marubozu).
Marubozu shows strong conviction with no hesitation - pure momentum.

Pattern:
- Body > 80% of total range (minimal wicks)
- Body size > 0.4% (significant move)
- LONG: Bullish marubozu (close near high)
- SHORT: Bearish marubozu (close near low)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class MarubozuMomentum:
    """Detects strong directional candles (marubozu patterns)."""

    def __init__(
        self,
        min_body_to_range: float = 0.8,  # 80% body to range ratio
        min_body_size_pct: float = 0.004,  # 0.4% minimum move
    ):
        self.min_body_to_range = min_body_to_range
        self.min_body_size_pct = min_body_size_pct
        self.candle_buffer = deque(maxlen=5)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect marubozu momentum patterns."""
        if len(candles) < 1:
            return None

        current = candles[-1]

        open_price = float(current["open"])
        high = float(current["high"])
        low = float(current["low"])
        close = float(current["close"])

        total_range = high - low
        if total_range == 0:
            return None

        body = abs(close - open_price)
        body_to_range = body / total_range

        # Check body to range ratio
        if body_to_range < self.min_body_to_range:
            return None

        # Check minimum body size
        price = close
        body_pct = body / price

        if body_pct < self.min_body_size_pct:
            return None

        # Bullish Marubozu
        if close > open_price:
            upper_wick = high - close
            lower_wick = open_price - low

            return {
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "pattern": "bullish_marubozu",
                    "body_to_range": body_to_range,
                    "body_size_pct": body_pct * 100,
                    "upper_wick_pct": (upper_wick / price) * 100,
                    "lower_wick_pct": (lower_wick / price) * 100,
                },
            }

        # Bearish Marubozu
        if close < open_price:
            upper_wick = high - open_price
            lower_wick = close - low

            return {
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "pattern": "bearish_marubozu",
                    "body_to_range": body_to_range,
                    "body_size_pct": body_pct * 100,
                    "upper_wick_pct": (upper_wick / price) * 100,
                    "lower_wick_pct": (lower_wick / price) * 100,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for marubozu pattern using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 1:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
