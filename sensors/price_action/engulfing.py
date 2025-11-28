"""
Engulfing Pattern Sensor

Detects bullish and bearish engulfing candles that signal strong momentum shifts.
Engulfing patterns show aggressive buyers/sellers overpowering the previous move.

Pattern:
- LONG: Bullish engulfing (green candle body completely engulfs previous red body)
- SHORT: Bearish engulfing (red candle body completely engulfs previous green body)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class EngulfingPattern:
    """Detects engulfing candlestick patterns."""

    def __init__(
        self,
        volume_multiplier: float = 1.5,
        min_body_pct: float = 0.002,  # 0.2% minimum body size
    ):
        self.volume_multiplier = volume_multiplier
        self.min_body_pct = min_body_pct
        self.candle_buffer = deque(maxlen=20)  # Keep last 20 candles for volume avg

    def detect(self, candles: np.ndarray) -> Optional[Dict]:
        """
        Detect engulfing patterns.

        Args:
            candles: Array of OHLCV data (last 10 candles for volume average)

        Returns:
            Signal dict or None
        """
        if len(candles) < 10:
            return None

        current = candles[-1]
        prev = candles[-2]

        # Current candle
        curr_open = float(current["open"])
        curr_close = float(current["close"])
        curr_volume = float(current["volume"])

        # Previous candle
        prev_open = float(prev["open"])
        prev_close = float(prev["close"])

        # Calculate bodies
        curr_body = curr_close - curr_open
        prev_body = prev_close - prev_open

        curr_body_size = abs(curr_body)
        prev_body_size = abs(prev_body)

        # Check minimum body size
        price = curr_close
        if curr_body_size / price < self.min_body_pct:
            return None

        # Calculate average volume
        avg_volume = np.mean([float(c["volume"]) for c in candles[-10:-1]])

        # Volume confirmation
        volume_confirmed = curr_volume >= self.volume_multiplier * avg_volume

        # Bullish Engulfing
        if (
            prev_body < 0  # Previous candle was bearish
            and curr_body > 0  # Current candle is bullish
            and curr_open <= prev_close  # Opens at or below previous close
            and curr_close >= prev_open  # Closes at or above previous open
            and curr_body_size > prev_body_size  # Current body larger
            and volume_confirmed
        ):
            return {
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "pattern": "bullish_engulfing",
                    "body_ratio": curr_body_size / (prev_body_size + 1e-9),
                    "volume_ratio": curr_volume / (avg_volume + 1e-9),
                },
            }

        # Bearish Engulfing
        if (
            prev_body > 0  # Previous candle was bullish
            and curr_body < 0  # Current candle is bearish
            and curr_open >= prev_close  # Opens at or above previous close
            and curr_close <= prev_open  # Closes at or below previous open
            and curr_body_size > prev_body_size  # Current body larger
            and volume_confirmed
        ):
            return {
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "pattern": "bearish_engulfing",
                    "body_ratio": curr_body_size / (prev_body_size + 1e-9),
                    "volume_ratio": curr_volume / (avg_volume + 1e-9),
                },
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Check for engulfing pattern using candle buffer."""
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 10:
            return None

        candles_array = np.array(list(self.candle_buffer))
        signal = self.detect(candles_array)

        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")

        return signal
