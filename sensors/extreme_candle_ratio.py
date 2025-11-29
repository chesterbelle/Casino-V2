"""
ExtremeCandleRatio Sensor (V3).
Tier 2: Excellent.
Logic: Candle body larger than historical percentile.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class ExtremeCandleRatioV3(SensorV3):
    @property
    def name(self) -> str:
        return "ExtremeCandleRatio"

    def __init__(self, lookback=30, percentile=0.95):
        self.lookback = lookback
        self.percentile = percentile
        self.bodies = deque(maxlen=lookback + 1)

    def calculate(self, candle: dict) -> dict:
        open_p = candle["open"]
        close = candle["close"]
        body = abs(close - open_p)

        # Calculate threshold BEFORE adding current body
        if len(self.bodies) < self.lookback:
            self.bodies.append(body)
            return None

        threshold = np.percentile(self.bodies, self.percentile * 100)
        self.bodies.append(body)

        signal = None

        if body > threshold:
            if close > open_p:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"ratio": body / threshold if threshold else 0}}
            else:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"ratio": body / threshold if threshold else 0}}

        return signal
