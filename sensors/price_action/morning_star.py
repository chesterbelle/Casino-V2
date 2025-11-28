"""
Morning Star / Evening Star Sensor

Detects 3-candle reversal patterns showing trend exhaustion.
Classic reversal patterns with high reliability in crypto.

Pattern:
- Morning Star (LONG): Large bearish → Small star → Large bullish
- Evening Star (SHORT): Large bullish → Small star → Large bearish
- Third candle must close past midpoint of first candle
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class MorningStarEvening:
    """Detects morning star and evening star reversal patterns."""

    def __init__(
        self,
        min_large_body_pct: float = 0.004,  # 0.4% minimum for large candles
        max_star_body_pct: float = 0.002,  # 0.2% maximum for star candle
        confirmation_threshold: float = 0.5,  # Close past 50% of first candle
    ):
        self.min_large_body_pct = min_large_body_pct
        self.max_star_body_pct = max_star_body_pct
        self.confirmation_threshold = confirmation_threshold
        self.candle_buffer = deque(maxlen=10)

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """Detect morning/evening star patterns."""
        if len(candles) < 3:
            return None

        c1 = candles[-3]  # First candle
        c2 = candles[-2]  # Star candle
        c3 = candles[-1]  # Confirmation candle

        # Extract OHLC
        c1_open, c1_close = float(c1["open"]), float(c1["close"])
        c2_open, c2_close = float(c2["open"]), float(c2["close"])
        c3_open, c3_close = float(c3["open"]), float(c3["close"])

        c1_body = abs(c1_close - c1_open)
        c2_body = abs(c2_close - c2_open)
        c3_body = abs(c3_close - c3_open)

        price = c3_close

        # Check body sizes
        c1_body_pct = c1_body / price
        c2_body_pct = c2_body / price
        c3_body_pct = c3_body / price

        if c1_body_pct < self.min_large_body_pct:
            return None  # First candle not large enough

        if c2_body_pct > self.max_star_body_pct:
            return None  # Star candle too large

        if c3_body_pct < self.min_large_body_pct:
            return None  # Confirmation candle not large enough

        # Morning Star (Bullish Reversal)
        if c1_close < c1_open and c3_close > c3_open:
            # Calculate midpoint of first candle
            c1_midpoint = (c1_open + c1_close) / 2

            # Check if third candle closes above midpoint
            if c3_close > c1_midpoint:
                penetration = (c3_close - c1_close) / c1_body

                return {
                    "side": "LONG",
                    "range_score": 3,
                    "features": {
                        "pattern": "morning_star",
                        "first_body_pct": c1_body_pct * 100,
                        "star_body_pct": c2_body_pct * 100,
                        "confirm_body_pct": c3_body_pct * 100,
                        "penetration": penetration,
                    },
                }

        # Evening Star (Bearish Reversal)
        if c1_close > c1_open and c3_close < c3_open:
            # Calculate midpoint of first candle
            c1_midpoint = (c1_open + c1_close) / 2

            # Check if third candle closes below midpoint
            if c3_close < c1_midpoint:
                penetration = (c1_close - c3_close) / c1_body

                return {
                    "side": "SHORT",
                    "range_score": 3,
                    "features": {
                        "pattern": "evening_star",
                        "first_body_pct": c1_body_pct * 100,
                        "star_body_pct": c2_body_pct * 100,
                        "confirm_body_pct": c3_body_pct * 100,
                        "penetration": penetration,
                    },
                }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for morning/evening star pattern using candle buffer."""
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
