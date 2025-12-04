"""
MACDCrossover Sensor (V3).
Logic: MACD histogram crosses zero line.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class MACDCrossoverV3(SensorV3):
    @property
    def name(self) -> str:
        return "MACDCrossover"

    def __init__(self, short_period=12, long_period=26, signal_period=9):
        self.short_period = short_period
        self.long_period = long_period
        self.signal_period = signal_period
        self.closes = deque(maxlen=long_period + signal_period)
        self.ema_short = None
        self.ema_long = None
        self.signal_line = None
        self.prev_hist = None
        self.macd_values = deque(maxlen=signal_period)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        close = candle["close"]
        self.closes.append(close)

        if len(self.closes) < self.long_period:
            return None

        # Calculate EMAs
        self.ema_short = self._compute_ema(self.ema_short, close, self.short_period, list(self.closes))
        self.ema_long = self._compute_ema(self.ema_long, close, self.long_period, list(self.closes))

        macd_line = self.ema_short - self.ema_long
        self.macd_values.append(macd_line)

        if len(self.macd_values) < self.signal_period:
            return None

        self.signal_line = self._compute_ema(self.signal_line, macd_line, self.signal_period, list(self.macd_values))
        histogram = macd_line - self.signal_line

        signal = None

        if self.prev_hist is not None:
            if histogram > 0 and self.prev_hist <= 0:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"histogram": histogram}}
            elif histogram < 0 and self.prev_hist >= 0:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"histogram": histogram}}

        self.prev_hist = histogram
        return signal

    def _compute_ema(self, previous, value, period, seed):
        if previous is None:
            if not seed or len(seed) < period:
                return value
            return sum(seed[-period:]) / period

        k = 2 / (period + 1)
        return value * k + previous * (1 - k)
