"""
VWAPMomentum Sensor (V3).
Logic: Detects momentum moves relative to VWAP.

Signals when price shows strong momentum away from VWAP
with volume confirmation.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VWAPMomentumV3(SensorV3):
    @property
    def name(self) -> str:
        return "VWAPMomentum"

    def __init__(self, momentum_threshold=0.003, volume_factor=1.5, lookback=50):
        """
        Args:
            momentum_threshold: Min distance from VWAP as % for signal
            volume_factor: Min volume ratio for confirmation
            lookback: Period for VWAP calculation
        """
        self.momentum_threshold = momentum_threshold
        self.volume_factor = volume_factor
        self.lookback = lookback

        self.candles = deque(maxlen=lookback + 10)
        self.volumes = deque(maxlen=lookback + 10)
        self.cum_tp_vol = 0
        self.cum_vol = 0

    def calculate(self, candle: dict) -> dict:
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle.get("volume", 1)

        typical_price = (high + low + close) / 3

        self.candles.append(candle)
        self.volumes.append(volume)

        # Update cumulative values
        self.cum_tp_vol += typical_price * volume
        self.cum_vol += volume

        if len(self.candles) < 20:
            return None

        # Calculate VWAP
        if self.cum_vol == 0:
            return None

        vwap = self.cum_tp_vol / self.cum_vol

        # Calculate distance from VWAP
        distance_pct = (close - vwap) / vwap if vwap > 0 else 0

        # Check volume confirmation
        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else 1
        volume_confirmed = volume > avg_volume * self.volume_factor

        open_price = candle["open"]

        # Bullish momentum: Price well above VWAP with volume
        if distance_pct > self.momentum_threshold and close > open_price and volume_confirmed:
            return {
                "side": "LONG",
                "score": min(distance_pct / self.momentum_threshold / 2, 1.0),
                "metadata": {
                    "pattern": "vwap_momentum_up",
                    "vwap": vwap,
                    "distance_pct": distance_pct,
                    "volume_ratio": volume / avg_volume,
                },
            }

        # Bearish momentum: Price well below VWAP with volume
        if distance_pct < -self.momentum_threshold and close < open_price and volume_confirmed:
            return {
                "side": "SHORT",
                "score": min(abs(distance_pct) / self.momentum_threshold / 2, 1.0),
                "metadata": {
                    "pattern": "vwap_momentum_down",
                    "vwap": vwap,
                    "distance_pct": distance_pct,
                    "volume_ratio": volume / avg_volume,
                },
            }

        return None
