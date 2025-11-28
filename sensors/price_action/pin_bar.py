"""
Pin Bar Reversal Sensor

Detects pin bars (rejection candles) with long wicks and small bodies at key levels.
Pin bars show strong rejection by institutional traders and often precede reversals.

Pattern:
- LONG: Bullish pin bar (long lower wick ≥ 2x body, close in upper 30%)
- SHORT: Bearish pin bar (long upper wick ≥ 2x body, close in lower 30%)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class PinBarReversal:
    """Detects pin bar reversal patterns."""

    def __init__(
        self,
        wick_to_body_ratio: float = 2.0,
        min_wick_pct: float = 0.003,  # 0.3% minimum wick size
        close_position_threshold: float = 0.3,  # Close in top/bottom 30%
    ):
        self.wick_to_body_ratio = wick_to_body_ratio
        self.min_wick_pct = min_wick_pct
        self.close_position_threshold = close_position_threshold
        self.candle_buffer = deque(maxlen=10)  # Keep last 10 candles

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """
        Detect pin bar reversal patterns.

        Args:
            candles: Array of OHLCV data (last 3 candles minimum)

        Returns:
            Signal dict or None
        """
        if len(candles) < 3:
            return None

        current = candles[-1]

        open_price = float(current["open"])
        high = float(current["high"])
        low = float(current["low"])
        close = float(current["close"])

        # Calculate candle metrics
        total_range = high - low
        if total_range == 0:
            return None

        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low

        # Normalize to percentage of price
        price = close
        upper_wick_pct = upper_wick / price
        lower_wick_pct = lower_wick / price

        # Calculate close position in range (0 = bottom, 1 = top)
        close_position = (close - low) / total_range if total_range > 0 else 0.5

        # Bullish Pin Bar (Hammer)
        if (
            lower_wick_pct >= self.min_wick_pct
            and lower_wick >= self.wick_to_body_ratio * body
            and close_position >= (1 - self.close_position_threshold)
        ):
            return {
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "pattern": "bullish_pin_bar",
                    "lower_wick_pct": lower_wick_pct * 100,
                    "wick_to_body": lower_wick / (body + 1e-9),
                    "close_position": close_position,
                },
            }

        # Bearish Pin Bar (Shooting Star)
        if (
            upper_wick_pct >= self.min_wick_pct
            and upper_wick >= self.wick_to_body_ratio * body
            and close_position <= self.close_position_threshold
        ):
            return {
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "pattern": "bearish_pin_bar",
                    "upper_wick_pct": upper_wick_pct * 100,
                    "wick_to_body": upper_wick / (body + 1e-9),
                    "close_position": close_position,
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for pin bar signal using candle buffer."""
        # Add current candle to buffer
        self.candle_buffer.append(candle)

        # Need at least 3 candles
        if len(self.candle_buffer) < 3:
            return None

        # Convert buffer to numpy array format expected by detect()
        candles_array = np.array(list(self.candle_buffer))

        # Call detect method
        signal = self.detect(candles_array)

        if signal:
            # Add required fields for sensor manager
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
