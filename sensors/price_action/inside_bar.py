"""
Inside Bar Breakout Sensor

Detects inside bars (consolidation) followed by directional breakouts.
Inside bars show indecision; breakouts often lead to strong directional moves.

Pattern:
- Setup: Current candle's high < previous high AND low > previous low
- LONG: Next candle breaks above inside bar high with strong close
- SHORT: Next candle breaks below inside bar low with strong close
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class InsideBarBreakout:
    """Detects inside bar consolidation followed by breakouts."""

    def __init__(
        self,
        max_inside_range_pct: float = 0.005,  # 0.5% max range for tight consolidation
        breakout_confirmation: bool = True,
    ):
        self.max_inside_range_pct = max_inside_range_pct
        self.breakout_confirmation = breakout_confirmation
        self.candle_buffer = deque(maxlen=10)
        self._inside_bar_detected = False
        self._inside_bar_high = None
        self._inside_bar_low = None

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """
        Detect inside bar breakout patterns.

        Args:
            candles: Array of OHLCV data (last 3 candles minimum)

        Returns:
            Signal dict or None
        """
        if len(candles) < 3:
            return None

        current = candles[-1]
        prev = candles[-2]
        prev_prev = candles[-3]

        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])

        prev_high = float(prev["high"])
        prev_low = float(prev["low"])

        prev_prev_high = float(prev_prev["high"])
        prev_prev_low = float(prev_prev["low"])

        # Check if previous candle was an inside bar
        is_inside_bar = prev_high < prev_prev_high and prev_low > prev_prev_low

        if is_inside_bar:
            # Calculate inside bar range
            inside_range = prev_high - prev_low
            price = curr_close
            inside_range_pct = inside_range / price

            # Only consider tight inside bars
            if inside_range_pct <= self.max_inside_range_pct:
                self._inside_bar_detected = True
                self._inside_bar_high = prev_high
                self._inside_bar_low = prev_low

        # Check for breakout if we have a detected inside bar
        if self._inside_bar_detected:
            # Bullish Breakout
            if curr_high > self._inside_bar_high:
                # Confirmation: close above breakout level
                if not self.breakout_confirmation or curr_close > self._inside_bar_high:
                    self._inside_bar_detected = False  # Reset
                    return {
                        "side": "LONG",
                        "range_score": 1,
                        "features": {
                            "pattern": "inside_bar_bullish_breakout",
                            "breakout_level": self._inside_bar_high,
                            "close_strength": (curr_close - self._inside_bar_high) / price * 100,
                        },
                    }

            # Bearish Breakout
            if curr_low < self._inside_bar_low:
                # Confirmation: close below breakout level
                if not self.breakout_confirmation or curr_close < self._inside_bar_low:
                    self._inside_bar_detected = False  # Reset
                    return {
                        "side": "SHORT",
                        "range_score": 1,
                        "features": {
                            "pattern": "inside_bar_bearish_breakout",
                            "breakout_level": self._inside_bar_low,
                            "close_strength": (self._inside_bar_low - curr_close) / price * 100,
                        },
                    }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for inside bar breakout using candle buffer."""
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
