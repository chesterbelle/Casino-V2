"""
AbsorptionBlock Sensor (V3).
Logic: Detects volume absorption patterns.

Absorption occurs when high volume fails to move price,
indicating strong opposing interest that may lead to reversal.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class AbsorptionBlockV3(SensorV3):
    @property
    def name(self) -> str:
        return "AbsorptionBlock"

    def __init__(self, volume_factor=2.0, body_factor=0.3, lookback=20):
        """
        Args:
            volume_factor: Multiplier for volume spike detection
            body_factor: Max body/range ratio for absorption (small body)
            lookback: Period for average volume calculation
        """
        self.volume_factor = volume_factor
        self.body_factor = body_factor
        self.lookback = lookback

        self.candles = deque(maxlen=lookback + 5)
        self.volumes = deque(maxlen=lookback + 5)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.candles.append(candle)
        self.volumes.append(candle.get("volume", 0))

        if len(self.candles) < self.lookback:
            return None

        # Check for absorption pattern
        signal = self._check_absorption(candle)
        return signal

    def _check_absorption(self, candle):
        """Check for volume absorption pattern."""
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle.get("volume", 0)

        # Calculate metrics
        candle_range = high - low
        if candle_range == 0:
            return None

        body = abs(close - open_price)
        body_ratio = body / candle_range

        # Average volume (excluding current)
        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else 1

        # Check for absorption: high volume + small body
        volume_spike = volume > avg_volume * self.volume_factor
        small_body = body_ratio < self.body_factor

        if not (volume_spike and small_body):
            return None

        # Determine direction based on previous trend
        prev_candles = list(self.candles)[-5:-1]
        if len(prev_candles) < 3:
            return None

        # Check if we were trending down (potential bullish absorption)
        closes = [c["close"] for c in prev_candles]
        was_downtrend = closes[-1] < closes[0]
        was_uptrend = closes[-1] > closes[0]

        # Absorption at bottom = bullish
        if was_downtrend and close > open_price:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "pattern": "bullish_absorption",
                    "volume_ratio": volume / avg_volume,
                    "body_ratio": body_ratio,
                },
            }

        # Absorption at top = bearish
        if was_uptrend and close < open_price:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "pattern": "bearish_absorption",
                    "volume_ratio": volume / avg_volume,
                    "body_ratio": body_ratio,
                },
            }

        return None
