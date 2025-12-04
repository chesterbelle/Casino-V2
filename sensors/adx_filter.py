"""
ADXFilter Sensor (V3).
Logic: ADX trend strength filter with directional signals.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class ADXFilterV3(SensorV3):
    @property
    def name(self) -> str:
        return "ADXFilter"

    def __init__(self, period=14, adx_threshold=25.0, use_directional=True):
        self.period = period
        self.adx_threshold = adx_threshold
        self.use_directional = use_directional
        self.highs = deque(maxlen=period + 1)
        self.lows = deque(maxlen=period + 1)
        self.closes = deque(maxlen=period + 1)
        self.dx_values = deque(maxlen=period)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        di_plus, di_minus = self._compute_di()
        if di_plus is None or di_minus is None:
            return None

        adx = self._compute_adx(di_plus, di_minus)
        if adx is None or adx < self.adx_threshold:
            return None

        if not self.use_directional:
            return None

        signal = None

        if di_plus > di_minus:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"adx": adx, "di_plus": di_plus, "di_minus": di_minus}}
        else:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"adx": adx, "di_plus": di_plus, "di_minus": di_minus}}

        return signal

    def _compute_di(self):
        plus_dm, minus_dm, tr = self._compute_dm_tr()

        if not tr or len(tr) < self.period:
            return None, None

        smoothed_plus_dm = np.mean(plus_dm[-self.period :])
        smoothed_minus_dm = np.mean(minus_dm[-self.period :])
        smoothed_tr = np.mean(tr[-self.period :])

        if smoothed_tr == 0:
            return None, None

        di_plus = (smoothed_plus_dm / smoothed_tr) * 100
        di_minus = (smoothed_minus_dm / smoothed_tr) * 100
        return di_plus, di_minus

    def _compute_dm_tr(self):
        if len(self.highs) < 2:
            return [], [], []

        plus_dm = []
        minus_dm = []
        tr_values = []

        for i in range(1, len(self.highs)):
            high = self.highs[i]
            low = self.lows[i]
            prev_high = self.highs[i - 1]
            prev_low = self.lows[i - 1]
            prev_close = self.closes[i - 1]

            up_move = high - prev_high
            down_move = prev_low - low

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
                minus_dm.append(0)
            elif down_move > up_move and down_move > 0:
                plus_dm.append(0)
                minus_dm.append(down_move)
            else:
                plus_dm.append(0)
                minus_dm.append(0)

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        return plus_dm, minus_dm, tr_values

    def _compute_adx(self, di_plus, di_minus):
        if di_plus is None or di_minus is None:
            return None

        di_sum = di_plus + di_minus
        if di_sum == 0:
            return 0.0

        dx = (abs(di_plus - di_minus) / di_sum) * 100
        self.dx_values.append(dx)

        if len(self.dx_values) < self.period:
            return None

        adx = np.mean(self.dx_values)
        return adx
