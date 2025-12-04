"""
VolumeSpike Sensor (V3).
Logic: Detects volume spike reversals.

A volume spike with reversal candle often signals
exhaustion and potential trend change.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VolumeSpikeV3(SensorV3):
    @property
    def name(self) -> str:
        return "VolumeSpike"

    def __init__(self, volume_multiplier=3.0, min_body_pct=0.004, lookback=20):
        """
        Args:
            volume_multiplier: Multiplier for volume spike detection
            min_body_pct: Min body size as % for reversal confirmation
            lookback: Period for average volume
        """
        self.volume_multiplier = volume_multiplier
        self.min_body_pct = min_body_pct
        self.lookback = lookback

        self.candles = deque(maxlen=lookback + 5)
        self.volumes = deque(maxlen=lookback + 5)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)
        self.volumes.append(candle.get("volume", 0))

        if len(self.volumes) < self.lookback:
            return None

        signal = self._check_volume_spike(candle)
        return signal

    def _check_volume_spike(self, candle):
        """Check for volume spike with reversal."""
        volume = candle.get("volume", 0)
        avg_volume = np.mean(list(self.volumes)[:-1])

        if avg_volume == 0:
            return None

        # Check for spike
        volume_ratio = volume / avg_volume
        if volume_ratio < self.volume_multiplier:
            return None

        # Check for reversal candle
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        body = abs(close - open_price)
        avg_price = (high + low) / 2
        body_pct = body / avg_price

        if body_pct < self.min_body_pct:
            return None

        # Get previous trend
        prev_candles = list(self.candles)[-5:-1]
        if len(prev_candles) < 3:
            return None

        closes = [c["close"] for c in prev_candles]
        was_downtrend = closes[-1] < closes[0]
        was_uptrend = closes[-1] > closes[0]

        # Bullish volume spike reversal
        if was_downtrend and close > open_price:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "pattern": "bullish_volume_spike",
                    "volume_ratio": volume_ratio,
                    "body_pct": body_pct,
                },
            }

        # Bearish volume spike reversal
        if was_uptrend and close < open_price:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "pattern": "bearish_volume_spike",
                    "volume_ratio": volume_ratio,
                    "body_pct": body_pct,
                },
            }

        return None
