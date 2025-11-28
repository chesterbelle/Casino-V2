"""
Rails Pattern Sensor

Detects parallel rejection patterns (double top/bottom).
Two consecutive candles with nearly identical highs or lows.

Pattern:
- LONG: Two candles with similar lows (within 0.1%), both close in upper 50%
- SHORT: Two candles with similar highs (within 0.1%), both close in lower 50%
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class RailsPattern:
    """Detects rails (parallel rejection) patterns."""

    def __init__(
        self,
        max_level_diff_pct: float = 0.001,  # 0.1% max difference between levels
        min_close_position: float = 0.5,  # Close in upper/lower 50%
    ):
        self.max_level_diff_pct = max_level_diff_pct
        self.min_close_position = min_close_position
        self.candle_buffer = deque(maxlen=5)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect rails patterns."""
        if len(candles) < 2:
            return None

        prev = candles[-2]
        current = candles[-1]

        # Previous candle
        prev_high = float(prev["high"])
        prev_low = float(prev["low"])
        prev_close = float(prev["close"])
        prev_range = prev_high - prev_low

        # Current candle
        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])
        curr_range = curr_high - curr_low

        if prev_range == 0 or curr_range == 0:
            return None

        price = curr_close

        # Calculate close positions (0 = bottom, 1 = top)
        prev_close_pos = (prev_close - prev_low) / prev_range
        curr_close_pos = (curr_close - curr_low) / curr_range

        # Bullish Rails (double bottom)
        low_diff_pct = abs(curr_low - prev_low) / price

        if (
            low_diff_pct <= self.max_level_diff_pct
            and prev_close_pos >= self.min_close_position
            and curr_close_pos >= self.min_close_position
        ):
            return {
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "pattern": "bullish_rails",
                    "level_diff_pct": low_diff_pct * 100,
                    "support_level": min(prev_low, curr_low),
                    "prev_close_pos": prev_close_pos,
                    "curr_close_pos": curr_close_pos,
                },
            }

        # Bearish Rails (double top)
        high_diff_pct = abs(curr_high - prev_high) / price

        if (
            high_diff_pct <= self.max_level_diff_pct
            and prev_close_pos <= (1 - self.min_close_position)
            and curr_close_pos <= (1 - self.min_close_position)
        ):
            return {
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "pattern": "bearish_rails",
                    "level_diff_pct": high_diff_pct * 100,
                    "resistance_level": max(prev_high, curr_high),
                    "prev_close_pos": prev_close_pos,
                    "curr_close_pos": curr_close_pos,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for rails pattern using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 2:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
