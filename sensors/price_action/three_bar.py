"""
Three Bar Reversal Sensor

Detects 3-candle exhaustion patterns showing momentum loss and imminent reversal.
Decreasing ranges show exhaustion; weak close signals reversal is imminent.

Pattern:
- LONG: 3 consecutive red candles with decreasing range + final candle closes in upper 40%
- SHORT: 3 consecutive green candles with decreasing range + final candle closes in lower 40%
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class ThreeBarReversal:
    """Detects three-bar exhaustion reversal patterns."""

    def __init__(
        self,
        range_decrease_threshold: float = 0.7,  # Third candle range < 70% of first
        close_position_threshold: float = 0.4,  # Close in top/bottom 40%
    ):
        self.range_decrease_threshold = range_decrease_threshold
        self.close_position_threshold = close_position_threshold
        self.candle_buffer = deque(maxlen=10)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """
        Detect three-bar reversal patterns.

        Args:
            candles: Array of OHLCV data (last 3 candles minimum)

        Returns:
            Signal dict or None
        """
        if len(candles) < 3:
            return None

        c1 = candles[-3]  # First candle
        c2 = candles[-2]  # Second candle
        c3 = candles[-1]  # Third candle (current)

        # Extract OHLC for each candle
        c1_open, c1_high, c1_low, c1_close = (
            float(c1["open"]),
            float(c1["high"]),
            float(c1["low"]),
            float(c1["close"]),
        )
        c2_open, _, _, c2_close = (
            float(c2["open"]),
            float(c2["high"]),
            float(c2["low"]),
            float(c2["close"]),
        )
        c3_open, c3_high, c3_low, c3_close = (
            float(c3["open"]),
            float(c3["high"]),
            float(c3["low"]),
            float(c3["close"]),
        )

        # Calculate ranges
        c1_range = c1_high - c1_low
        c3_range = c3_high - c3_low

        if c1_range == 0 or c3_range == 0:
            return None

        # Check range decrease (exhaustion)
        range_ratio = c3_range / c1_range
        if range_ratio >= self.range_decrease_threshold:
            return None

        # Calculate close position in third candle (0 = bottom, 1 = top)
        close_position = (c3_close - c3_low) / c3_range if c3_range > 0 else 0.5

        # Bullish Reversal (3 consecutive red candles showing exhaustion)
        if (
            c1_close < c1_open  # First candle bearish
            and c2_close < c2_open  # Second candle bearish
            and c3_close < c3_open  # Third candle bearish
            and close_position >= (1 - self.close_position_threshold)  # Weak close (in upper 40%)
        ):
            return {
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "pattern": "three_bar_bullish_reversal",
                    "range_decrease": (1 - range_ratio) * 100,
                    "close_position": close_position,
                    "exhaustion_score": (1 - range_ratio) * close_position,
                },
            }

        # Bearish Reversal (3 consecutive green candles showing exhaustion)
        if (
            c1_close > c1_open  # First candle bullish
            and c2_close > c2_open  # Second candle bullish
            and c3_close > c3_open  # Third candle bullish
            and close_position <= self.close_position_threshold  # Weak close (in lower 40%)
        ):
            return {
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "pattern": "three_bar_bearish_reversal",
                    "range_decrease": (1 - range_ratio) * 100,
                    "close_position": close_position,
                    "exhaustion_score": (1 - range_ratio) * (1 - close_position),
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for three bar reversal using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 3:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
