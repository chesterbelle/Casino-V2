"""
VWAPBreakout Sensor (V3).
Tier 2: Excellent.
Logic: Volatility expansion away from VWAP.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VWAPBreakoutV3(SensorV3):
    @property
    def name(self) -> str:
        return "VWAPBreakout"

    def __init__(self, std_dev_mult=1.0, volume_factor=1.2, adx_threshold=20.0):
        self.std_dev_mult = std_dev_mult
        self.volume_factor = volume_factor
        self.adx_threshold = adx_threshold

        # State
        self.volumes = deque(maxlen=20)
        self.cum_vol = 0.0
        self.cum_vol_price = 0.0
        self.cum_vol_price_sq = 0.0
        self.start_timestamp = None

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]
        volume = candle["volume"]
        timestamp = candle["timestamp"]

        self.volumes.append(volume)
        vwap, std_dev = self._update_vwap(high, low, close, volume, timestamp)

        if len(self.volumes) < 20:
            return None

        avg_volume = np.mean(self.volumes)
        adx = 25.0  # Placeholder ADX

        if adx < self.adx_threshold:
            return None

        if volume < avg_volume * self.volume_factor:
            return None

        upper_band = vwap + (std_dev * self.std_dev_mult)
        lower_band = vwap - (std_dev * self.std_dev_mult)

        signal = None

        if close > upper_band:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"vwap": vwap}}
        elif close < lower_band:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"vwap": vwap}}

        return signal

    def _update_vwap(self, high, low, close, volume, timestamp):
        tp = (high + low + close) / 3.0

        # Reset daily (simplified logic)
        current_day = int(timestamp / (86400))  # timestamp is seconds in V3
        if self.start_timestamp is None or current_day > self.start_timestamp:
            self.cum_vol = 0.0
            self.cum_vol_price = 0.0
            self.cum_vol_price_sq = 0.0
            self.start_timestamp = current_day

        self.cum_vol += volume
        self.cum_vol_price += tp * volume
        self.cum_vol_price_sq += (tp * tp) * volume

        if self.cum_vol == 0:
            return tp, 0.0

        vwap = self.cum_vol_price / self.cum_vol
        mean_sq = self.cum_vol_price_sq / self.cum_vol
        variance = mean_sq - (vwap * vwap)
        std_dev = np.sqrt(max(0, variance))

        return vwap, std_dev
