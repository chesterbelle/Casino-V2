"""
StochasticReversion Sensor (V3).
Logic: Stochastic oscillator oversold/overbought.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class StochasticReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "StochasticReversion"

    def __init__(self, k_period=14, d_period=3, low_threshold=20.0, high_threshold=80.0):
        self.k_period = k_period
        self.d_period = d_period
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.highs = deque(maxlen=k_period)
        self.lows = deque(maxlen=k_period)
        self.closes = deque(maxlen=k_period)
        self.k_values = deque(maxlen=d_period)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        if len(self.closes) < self.k_period:
            return None

        k = self._compute_k()
        self.k_values.append(k)

        if len(self.k_values) < self.d_period:
            return None

        d = self._compute_d()
        signal = None

        if k < self.low_threshold and d < self.low_threshold:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"stoch_k": k, "stoch_d": d}}
        elif k > self.high_threshold and d > self.high_threshold:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"stoch_k": k, "stoch_d": d}}

        return signal

    def _compute_k(self):
        if len(self.closes) < self.k_period:
            return 50.0

        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        current_close = self.closes[-1]

        if highest_high == lowest_low:
            return 50.0

        k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        return k

    def _compute_d(self):
        if len(self.k_values) < self.d_period:
            return 50.0
        return np.mean(self.k_values)
