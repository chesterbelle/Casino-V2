"""
RSIReversion Sensor (V3).
Logic: RSI oversold/overbought mean reversion.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class RSIReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "RSIReversion"

    def __init__(self, period=2, low=10.0, high=90.0):
        self.period = period
        self.low = low
        self.high = high
        self.prices = deque(maxlen=250)

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        self.prices.append(close)

        if len(self.prices) < self.period + 1:
            return None

        rsi = self._compute_rsi()
        signal = None

        if rsi < self.low:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"rsi": rsi}}
        elif rsi > self.high:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"rsi": rsi}}

        return signal

    def _compute_rsi(self) -> float:
        prices_arr = np.array(self.prices)
        delta = np.diff(prices_arr)
        gains = np.maximum(delta, 0)
        losses = np.abs(np.minimum(delta, 0))

        avg_gain = np.mean(gains[-self.period :])
        avg_loss = np.mean(losses[-self.period :])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
