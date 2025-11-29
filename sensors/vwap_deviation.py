"""
VWAPDeviation Sensor (V3).
Tier 3: Good.
Logic: Price deviation from VWAP (Mean Reversion).
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VWAPDeviationV3(SensorV3):
    @property
    def name(self) -> str:
        return "VWAPDeviation"

    def __init__(self, period=20, deviation_threshold=0.015):
        self.period = period
        self.deviation_threshold = deviation_threshold
        self.typical_prices = deque(maxlen=period)
        self.volumes = deque(maxlen=period)

    def calculate(self, candle: dict) -> dict:
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle["volume"]

        tp = (high + low + close) / 3.0
        self.typical_prices.append(tp)
        self.volumes.append(volume)

        if len(self.typical_prices) < self.period:
            return None

        # Calculate VWAP
        tp_arr = np.array(self.typical_prices)
        vol_arr = np.array(self.volumes)
        total_vol = np.sum(vol_arr)

        if total_vol == 0:
            return None

        vwap = np.sum(tp_arr * vol_arr) / total_vol
        deviation = (close - vwap) / vwap

        signal = None

        # Price far below VWAP -> LONG (Mean Reversion)
        if deviation < -self.deviation_threshold:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"deviation": deviation}}

        # Price far above VWAP -> SHORT (Mean Reversion)
        elif deviation > self.deviation_threshold:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"deviation": deviation}}

        return signal
