"""
Doji Indecision Sensor

Detects Doji candles (indecision) followed by strong directional breakouts.
Dojis show market equilibrium; breakouts from equilibrium are high-probability.

Pattern:
- Doji: Small body (< 0.1% of range), open ≈ close
- Breakout: Next candle breaks doji high/low with strong body (> 60% of range)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class DojiIndecision:
    """Detects doji indecision followed by directional breakout."""

    def __init__(
        self,
        max_body_pct: float = 0.001,  # 0.1% max body for doji
        breakout_body_pct: float = 0.6,  # 60% body on breakout candle
        min_breakout_size: float = 0.003,  # 0.3% minimum breakout move
    ):
        self.max_body_pct = max_body_pct
        self.breakout_body_pct = breakout_body_pct
        self.min_breakout_size = min_breakout_size
        self.candle_buffer = deque(maxlen=5)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect doji → breakout patterns."""
        if len(candles) < 2:
            return None

        prev = candles[-2]  # Potential doji
        current = candles[-1]  # Potential breakout

        # Previous candle metrics
        prev_open = float(prev["open"])
        prev_high = float(prev["high"])
        prev_low = float(prev["low"])
        prev_close = float(prev["close"])
        prev_range = prev_high - prev_low
        prev_body = abs(prev_close - prev_open)

        # Current candle metrics
        curr_open = float(current["open"])
        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])
        curr_range = curr_high - curr_low
        curr_body = abs(curr_close - curr_open)

        if prev_range == 0 or curr_range == 0:
            return None

        # Check if previous candle is a doji
        price = prev_close
        prev_body_pct = prev_body / price

        if prev_body_pct > self.max_body_pct:
            return None  # Not a doji

        # Check if current candle is a strong breakout
        curr_body_ratio = curr_body / curr_range
        curr_body_pct = curr_body / price

        if curr_body_ratio < self.breakout_body_pct:
            return None  # Weak breakout

        if curr_body_pct < self.min_breakout_size:
            return None  # Too small

        # Bullish Breakout (breaks doji high)
        if curr_close > curr_open and curr_high > prev_high:
            return {
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "pattern": "doji_bullish_breakout",
                    "doji_body_pct": prev_body_pct * 100,
                    "breakout_body_ratio": curr_body_ratio,
                    "breakout_size_pct": curr_body_pct * 100,
                },
            }

        # Bearish Breakout (breaks doji low)
        if curr_close < curr_open and curr_low < prev_low:
            return {
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "pattern": "doji_bearish_breakout",
                    "doji_body_pct": prev_body_pct * 100,
                    "breakout_body_ratio": curr_body_ratio,
                    "breakout_size_pct": curr_body_pct * 100,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for doji indecision pattern using candle buffer."""
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
