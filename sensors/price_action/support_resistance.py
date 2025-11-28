"""
Support/Resistance Bounce Sensor

Detects price bouncing off recent swing highs/lows.
Recent S/R levels are self-fulfilling prophecies in HFT.

Pattern:
- Track recent swing highs/lows (last 20 candles)
- LONG: Price touches recent low (within 0.2%), then bounces with bullish candle
- SHORT: Price touches recent high (within 0.2%), then rejects with bearish candle
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class SupportResistanceBounce:
    """Detects bounces off dynamic support/resistance levels."""

    def __init__(
        self,
        lookback_candles: int = 20,
        touch_threshold_pct: float = 0.002,  # 0.2% proximity to level
        min_bounce_body_pct: float = 0.003,  # 0.3% minimum bounce
    ):
        self.lookback_candles = lookback_candles
        self.touch_threshold_pct = touch_threshold_pct
        self.min_bounce_body_pct = min_bounce_body_pct
        self.candle_buffer = deque(maxlen=lookback_candles + 5)

    def _find_swing_levels(self, candles: np.ndarray) -> tuple:
        """Find recent swing high and low."""
        if len(candles) < 3:
            return None, None

        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]

        # Find swing high (local maximum)
        swing_high = None
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                swing_high = highs[i]
                break

        # Find swing low (local minimum)
        swing_low = None
        for i in range(1, len(lows) - 1):
            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                swing_low = lows[i]
                break

        return swing_high, swing_low

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect S/R bounce patterns."""
        if len(candles) < self.lookback_candles:
            return None

        # Get lookback candles and current candle
        lookback = candles[:-1]
        current = candles[-1]

        curr_open = float(current["open"])
        curr_high = float(current["high"])
        curr_low = float(current["low"])
        curr_close = float(current["close"])
        curr_body = abs(curr_close - curr_open)

        price = curr_close

        # Check minimum bounce size
        if curr_body / price < self.min_bounce_body_pct:
            return None

        # Find swing levels
        swing_high, swing_low = self._find_swing_levels(lookback)

        # Support Bounce (LONG)
        if swing_low is not None and curr_close > curr_open:
            # Check if current low touched support
            touch_diff_pct = abs(curr_low - swing_low) / price

            if touch_diff_pct <= self.touch_threshold_pct:
                bounce_strength = (curr_close - curr_low) / curr_low

                return {
                    "side": "LONG",
                    "range_score": 2,
                    "features": {
                        "pattern": "support_bounce",
                        "support_level": swing_low,
                        "touch_diff_pct": touch_diff_pct * 100,
                        "bounce_strength": bounce_strength * 100,
                        "body_size_pct": (curr_body / price) * 100,
                    },
                }

        # Resistance Rejection (SHORT)
        if swing_high is not None and curr_close < curr_open:
            # Check if current high touched resistance
            touch_diff_pct = abs(curr_high - swing_high) / price

            if touch_diff_pct <= self.touch_threshold_pct:
                rejection_strength = (swing_high - curr_close) / swing_high

                return {
                    "side": "SHORT",
                    "range_score": 2,
                    "features": {
                        "pattern": "resistance_rejection",
                        "resistance_level": swing_high,
                        "touch_diff_pct": touch_diff_pct * 100,
                        "rejection_strength": rejection_strength * 100,
                        "body_size_pct": (curr_body / price) * 100,
                    },
                }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for S/R bounce pattern using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < self.lookback_candles:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
