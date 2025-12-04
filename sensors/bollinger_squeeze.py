"""
BollingerSqueeze Sensor (V3).
Logic: Low volatility squeeze followed by breakout with volume.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class BollingerSqueezeV3(SensorV3):
    @property
    def name(self) -> str:
        return "BollingerSqueeze"

    def __init__(self, period=20, std_dev=2.0, squeeze_threshold=0.02, volume_factor=1.2):
        self.period = period
        self.std_dev = std_dev
        self.squeeze_threshold = squeeze_threshold
        self.volume_factor = volume_factor
        self.closes = deque(maxlen=period)
        self.volumes = deque(maxlen=period)
        self.in_squeeze = False

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.closes.append(candle["close"])
        self.volumes.append(candle["volume"])

        if len(self.closes) < self.period:
            return None

        closes_arr = np.array(self.closes)
        middle = np.mean(closes_arr)
        std = np.std(closes_arr)
        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)
        bbw = (upper - lower) / middle if middle > 0 else 0.0

        is_squeezed = bbw < self.squeeze_threshold

        if is_squeezed:
            self.in_squeeze = True
            return None

        if not self.in_squeeze:
            return None

        avg_volume = np.mean(list(self.volumes)[:-1])
        has_volume_spike = self.volumes[-1] > (avg_volume * self.volume_factor)

        if not has_volume_spike:
            return None

        signal = None
        close = candle["close"]

        if close > upper:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"bbw": bbw}}
            self.in_squeeze = False
        elif close < lower:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"bbw": bbw}}
            self.in_squeeze = False

        return signal
