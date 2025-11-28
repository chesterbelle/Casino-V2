"""
Tweezer Pattern Sensor

Detects precise reversal patterns with identical highs/lows.
Tweezer tops/bottoms show algorithmic resistance/support levels.

Pattern:
- Tweezer Tops (SHORT): Two candles with identical highs (within 0.05%)
- Tweezer Bottoms (LONG): Two candles with identical lows (within 0.05%)
- Second candle must confirm reversal with strong body
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class TweezerPattern:
    """Detects tweezer top/bottom reversal patterns."""

    def __init__(
        self,
        max_wick_diff_pct: float = 0.0005,  # 0.05% max difference
        min_second_body_pct: float = 0.002,  # 0.2% minimum body on confirmation
    ):
        self.max_wick_diff_pct = max_wick_diff_pct
        self.min_second_body_pct = min_second_body_pct
        self.candle_buffer = deque(maxlen=5)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect tweezer patterns."""
        if len(candles) < 2:
            return None

        prev = candles[-2]
        current = candles[-1]

        # Previous candle
        prev_high = float(prev["high"])
        prev_low = float(prev["low"])

        # Current candle
        curr_open = float(current["open"])
        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])
        curr_body = abs(curr_close - curr_open)

        price = curr_close

        # Check minimum body size on second candle
        if curr_body / price < self.min_second_body_pct:
            return None

        # Tweezer Bottoms (LONG) - identical lows
        low_diff_pct = abs(curr_low - prev_low) / price

        if low_diff_pct <= self.max_wick_diff_pct and curr_close > curr_open:
            return {
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "pattern": "tweezer_bottom",
                    "level_diff_pct": low_diff_pct * 100,
                    "support_level": prev_low,
                    "body_size_pct": (curr_body / price) * 100,
                },
            }

        # Tweezer Tops (SHORT) - identical highs
        high_diff_pct = abs(curr_high - prev_high) / price

        if high_diff_pct <= self.max_wick_diff_pct and curr_close < curr_open:
            return {
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "pattern": "tweezer_top",
                    "level_diff_pct": high_diff_pct * 100,
                    "resistance_level": prev_high,
                    "body_size_pct": (curr_body / price) * 100,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for tweezer pattern using candle buffer."""
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
