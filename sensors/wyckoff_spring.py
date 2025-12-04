"""
WyckoffSpring Sensor (V3).
Logic: Detects Wyckoff spring and upthrust patterns.

Spring: False breakdown below support with quick reversal (bullish)
Upthrust: False breakout above resistance with quick reversal (bearish)
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class WyckoffSpringV3(SensorV3):
    @property
    def name(self) -> str:
        return "WyckoffSpring"

    def __init__(self, lookback=20, volume_factor=1.5, reversal_threshold=0.002):
        """
        Args:
            lookback: Period to establish support/resistance
            volume_factor: Volume spike multiplier for confirmation
            reversal_threshold: Min reversal % to confirm spring/upthrust
        """
        self.lookback = lookback
        self.volume_factor = volume_factor
        self.reversal_threshold = reversal_threshold

        self.candles = deque(maxlen=lookback + 5)
        self.volumes = deque(maxlen=lookback + 5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        self.candles.append(candle)
        self.volumes.append(candle.get("volume", 0))

        if len(self.candles) < self.lookback:
            return None

        # Calculate support and resistance levels
        support, resistance = self._find_sr_levels()

        # Check for spring or upthrust
        signal = self._check_wyckoff_pattern(candle, support, resistance)
        return signal

    def _find_sr_levels(self):
        """Find support and resistance from recent lows/highs."""
        candles = list(self.candles)[:-1]  # Exclude current candle

        lows = [c["low"] for c in candles]
        highs = [c["high"] for c in candles]

        # Use recent min/max as key levels
        support = min(lows[-self.lookback :])
        resistance = max(highs[-self.lookback :])

        return support, resistance

    def _check_wyckoff_pattern(self, candle, support, resistance):
        """Check for spring or upthrust pattern."""
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle.get("volume", 0)

        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else 1
        volume_spike = volume > avg_volume * self.volume_factor

        # Spring: Low pierces support but closes above it
        if low < support:
            reversal_pct = (close - low) / low if low > 0 else 0
            closed_above_support = close > support

            if closed_above_support and reversal_pct > self.reversal_threshold:
                return {
                    "side": "LONG",
                    "score": 1.0 if volume_spike else 0.7,
                    "metadata": {
                        "pattern": "spring",
                        "support": support,
                        "low": low,
                        "reversal_pct": reversal_pct,
                        "volume_spike": volume_spike,
                    },
                }

        # Upthrust: High pierces resistance but closes below it
        if high > resistance:
            reversal_pct = (high - close) / high if high > 0 else 0
            closed_below_resistance = close < resistance

            if closed_below_resistance and reversal_pct > self.reversal_threshold:
                return {
                    "side": "SHORT",
                    "score": 1.0 if volume_spike else 0.7,
                    "metadata": {
                        "pattern": "upthrust",
                        "resistance": resistance,
                        "high": high,
                        "reversal_pct": reversal_pct,
                        "volume_spike": volume_spike,
                    },
                }

        return None
