"""
Supertrend Sensor (V3).
Logic: Trend flip detection using ATR bands.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class SupertrendV3(SensorV3):
    @property
    def name(self) -> str:
        return "Supertrend"

    def __init__(self, atr_period=10, multiplier=3.0):
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.highs = deque(maxlen=atr_period + 1)
        self.lows = deque(maxlen=atr_period + 1)
        self.closes = deque(maxlen=atr_period + 1)
        self.last_supertrend = None
        self.last_direction = None  # 1 = uptrend, -1 = downtrend

    def calculate(self, candle: dict) -> dict:
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        if len(self.closes) < self.atr_period:
            return None

        supertrend, direction = self._compute_supertrend()

        if supertrend is None or direction is None:
            return None

        signal = None

        # Detect flip (trend change)
        if self.last_direction is not None and direction != self.last_direction:
            if direction == 1:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"supertrend": supertrend}}
            else:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"supertrend": supertrend}}

        self.last_supertrend = supertrend
        self.last_direction = direction
        return signal

    def _compute_supertrend(self):
        if len(self.closes) < self.atr_period:
            return None, None

        high = self.highs[-1]
        low = self.lows[-1]
        close = self.closes[-1]

        hl_avg = (high + low) / 2
        atr = self._compute_atr()

        if atr == 0:
            return None, None

        upper_band = hl_avg + (self.multiplier * atr)
        lower_band = hl_avg - (self.multiplier * atr)

        if self.last_supertrend is None or self.last_direction is None:
            if close > upper_band:
                direction = 1
                supertrend = lower_band
            elif close < lower_band:
                direction = -1
                supertrend = upper_band
            else:
                direction = 1
                supertrend = lower_band
        else:
            if self.last_direction == 1:
                if close < self.last_supertrend:
                    direction = -1
                    supertrend = upper_band
                else:
                    direction = 1
                    supertrend = max(lower_band, self.last_supertrend)
            else:
                if close > self.last_supertrend:
                    direction = 1
                    supertrend = lower_band
                else:
                    direction = -1
                    supertrend = min(upper_band, self.last_supertrend)

        return supertrend, direction

    def _compute_atr(self):
        if len(self.closes) < 2:
            return 0.0

        tr_values = []
        for i in range(1, len(self.closes)):
            h = self.highs[i]
            low_val = self.lows[i]
            prev_c = self.closes[i - 1]
            tr = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))
            tr_values.append(tr)

        return np.mean(tr_values[-self.atr_period :]) if tr_values else 0.0
