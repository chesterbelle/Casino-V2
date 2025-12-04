"""
ZScoreReversion Sensor (V3).
Logic: Z-Score statistical mean reversion.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class ZScoreReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "ZScoreReversion"

    def __init__(self, period=20, entry_threshold=2.0):
        self.period = period
        self.entry_threshold = entry_threshold
        self.closes = deque(maxlen=period)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        close = candle["close"]
        self.closes.append(close)

        if len(self.closes) < self.period:
            return None

        zscore = self._compute_zscore()
        signal = None

        if zscore < -self.entry_threshold:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"zscore": zscore}}
        elif zscore > self.entry_threshold:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"zscore": zscore}}

        return signal

    def _compute_zscore(self):
        closes_array = np.array(self.closes)
        mean = np.mean(closes_array)
        std = np.std(closes_array)

        if std == 0:
            return 0.0

        current_price = self.closes[-1]
        zscore = (current_price - mean) / std
        return zscore
