"""
VSAReversal Sensor (V3).
Logic: Volume Spread Analysis reversal detection.

VSA looks at the relationship between volume and price spread
to identify smart money activity.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VSAReversalV3(SensorV3):
    @property
    def name(self) -> str:
        return "VSAReversal"

    def __init__(self, lookback=20, volume_threshold=1.5, spread_threshold=0.7):
        """
        Args:
            lookback: Period for averages
            volume_threshold: Min volume ratio for signal
            spread_threshold: Max spread ratio for narrow bar (absorption)
        """
        self.lookback = lookback
        self.volume_threshold = volume_threshold
        self.spread_threshold = spread_threshold

        self.candles = deque(maxlen=lookback + 5)
        self.volumes = deque(maxlen=lookback + 5)
        self.spreads = deque(maxlen=lookback + 5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        spread = candle["high"] - candle["low"]
        self.candles.append(candle)
        self.volumes.append(candle.get("volume", 0))
        self.spreads.append(spread)

        if len(self.volumes) < self.lookback:
            return None

        signal = self._check_vsa(candle, spread)
        return signal

    def _check_vsa(self, candle, spread):
        """Check for VSA patterns."""
        volume = candle.get("volume", 0)
        close = candle["close"]
        open_price = candle["open"]

        avg_volume = np.mean(list(self.volumes)[:-1])
        avg_spread = np.mean(list(self.spreads)[:-1])

        if avg_volume == 0 or avg_spread == 0:
            return None

        volume_ratio = volume / avg_volume
        spread_ratio = spread / avg_spread

        # Check previous trend
        prev_candles = list(self.candles)[-5:-1]
        if len(prev_candles) < 3:
            return None

        closes = [c["close"] for c in prev_candles]
        was_downtrend = closes[-1] < closes[0]
        was_uptrend = closes[-1] > closes[0]

        # Stopping Volume: High volume + narrow spread after downtrend
        # Indicates buying absorption
        if was_downtrend:
            if volume_ratio > self.volume_threshold and spread_ratio < self.spread_threshold:
                if close > open_price:  # Bullish close
                    return {
                        "side": "LONG",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "stopping_volume",
                            "volume_ratio": volume_ratio,
                            "spread_ratio": spread_ratio,
                        },
                    }

        # No Supply: High volume + narrow spread after uptrend
        # Indicates selling absorption
        if was_uptrend:
            if volume_ratio > self.volume_threshold and spread_ratio < self.spread_threshold:
                if close < open_price:  # Bearish close
                    return {
                        "side": "SHORT",
                        "score": 1.0,
                        "metadata": {
                            "pattern": "no_demand",
                            "volume_ratio": volume_ratio,
                            "spread_ratio": spread_ratio,
                        },
                    }

        return None
