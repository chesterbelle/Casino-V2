"""
CCIReversion Sensor (V3).
Logic: Commodity Channel Index oversold/overbought.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class CCIReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "CCIReversion"

    def __init__(self, period=20, oversold=-100.0, overbought=100.0, constant=0.015):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.constant = constant
        self.typical_prices = deque(maxlen=period)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        typical_price = (high + low + close) / 3
        self.typical_prices.append(typical_price)

        if len(self.typical_prices) < self.period:
            return None

        cci = self._compute_cci()
        signal = None

        if cci < self.oversold:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"cci": cci}}
        elif cci > self.overbought:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"cci": cci}}

        return signal

    def _compute_cci(self):
        tp_array = np.array(self.typical_prices)
        sma_tp = np.mean(tp_array)
        mean_deviation = np.mean(np.abs(tp_array - sma_tp))

        if mean_deviation == 0:
            return 0.0

        current_tp = self.typical_prices[-1]
        cci = (current_tp - sma_tp) / (self.constant * mean_deviation)
        return cci
