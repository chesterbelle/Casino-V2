"""
Fakeout Reversal Sensor

Detects false breakouts (liquidity grabs/stop hunts) that reverse quickly.
Fakeouts trap retail traders and often precede strong reversals as smart money enters.

Pattern:
- LONG: Price breaks recent low, then closes back above within 1-2 candles
- SHORT: Price breaks recent high, then closes back below within 1-2 candles
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class FakeoutReversal:
    """Detects fakeout/stop hunt reversal patterns."""

    def __init__(
        self,
        breakout_threshold_pct: float = 0.002,  # 0.2% breakout distance
        lookback_candles: int = 10,
        reversal_body_pct: float = 0.6,  # Reversal candle body must be 60% of range
    ):
        self.breakout_threshold_pct = breakout_threshold_pct
        self.lookback_candles = lookback_candles
        self.reversal_body_pct = reversal_body_pct
        self.candle_buffer = deque(maxlen=20)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """
        Detect fakeout reversal patterns.

        Args:
            candles: Array of OHLCV data (lookback_candles + 2 minimum)

        Returns:
            Signal dict or None
        """
        if len(candles) < self.lookback_candles + 2:
            return None

        current = candles[-1]
        prev = candles[-2]
        lookback = candles[-(self.lookback_candles + 2) : -2]

        curr_open = float(current["open"])
        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])

        prev_low = float(prev["low"])
        prev_high = float(prev["high"])

        # Find recent high and low from lookback period
        recent_high = max(float(c["high"]) for c in lookback)
        recent_low = min(float(c["low"]) for c in lookback)

        price = curr_close
        curr_body = abs(curr_close - curr_open)
        curr_range = curr_high - curr_low

        # Check body strength
        if curr_range == 0 or curr_body / curr_range < self.reversal_body_pct:
            return None

        # Bullish Fakeout (False breakdown that reverses up)
        # Previous candle broke below recent low, current candle closes back above
        breakout_distance = (recent_low - prev_low) / price
        if (
            prev_low < recent_low  # Previous candle broke low
            and breakout_distance >= self.breakout_threshold_pct  # Significant break
            and curr_close > recent_low  # Current closes back above
            and curr_close > curr_open  # Bullish candle
        ):
            return {
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "pattern": "bullish_fakeout",
                    "breakout_distance_pct": breakout_distance * 100,
                    "reversal_strength": (curr_close - recent_low) / price * 100,
                    "body_pct": curr_body / curr_range,
                },
            }

        # Bearish Fakeout (False breakout that reverses down)
        # Previous candle broke above recent high, current candle closes back below
        breakout_distance = (prev_high - recent_high) / price
        if (
            prev_high > recent_high  # Previous candle broke high
            and breakout_distance >= self.breakout_threshold_pct  # Significant break
            and curr_close < recent_high  # Current closes back below
            and curr_close < curr_open  # Bearish candle
        ):
            return {
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "pattern": "bearish_fakeout",
                    "breakout_distance_pct": breakout_distance * 100,
                    "reversal_strength": (recent_high - curr_close) / price * 100,
                    "body_pct": curr_body / curr_range,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for fakeout reversal using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 12:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
