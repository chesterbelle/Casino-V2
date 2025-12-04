"""
KeltnerReversion Sensor (V3).
Logic: Price extends beyond Keltner Channels (mean reversion).
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class KeltnerReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "KeltnerReversion"

    def __init__(self, window=20, multiplier=2.0):
        self.window = window
        self.multiplier = multiplier
        self.highs = deque(maxlen=window)
        self.lows = deque(maxlen=window)
        self.closes = deque(maxlen=window)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        if len(self.closes) < self.window:
            return None

        # Calculate EMA of typical price
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(self.highs, self.lows, self.closes)]
        ema = self._ema(typical_prices)

        # Calculate ATR
        atr = self._atr()

        upper = ema + self.multiplier * atr
        lower = ema - self.multiplier * atr
        close = self.closes[-1]

        signal = None

        if close < lower:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"atr": atr}}
        elif close > upper:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"atr": atr}}

        return signal

    def _ema(self, values):
        alpha = 2 / (self.window + 1)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    def _atr(self):
        trs = []
        for i in range(1, len(self.closes)):
            h = self.highs[i]
            low_val = self.lows[i]
            prev_c = self.closes[i - 1]
            tr = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))
            trs.append(tr)
        return np.mean(trs) if trs else 0.0
