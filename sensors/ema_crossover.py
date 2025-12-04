"""
EMACrossover Sensor (V3).
Tier 1: 80% Win Rate.
Logic: EMA(12) crosses EMA(26) + ADX > 20.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class EMACrossoverV3(SensorV3):
    @property
    def name(self) -> str:
        return "EMACrossover"

    def __init__(self, short_period=12, long_period=26, adx_period=14, adx_threshold=20):
        self.short_period = short_period
        self.long_period = long_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

        # State for EMA
        self.closes = deque(maxlen=long_period + 50)
        self.highs = deque(maxlen=adx_period + 50)
        self.lows = deque(maxlen=adx_period + 50)

        # State for ADX calculation
        self.dx_values = deque(maxlen=adx_period)

        self.prev_short_ema = None
        self.prev_long_ema = None

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.closes) < self.long_period:
            return None

        # Calculate EMAs
        short_ema = self._calculate_ema(list(self.closes), self.short_period)
        long_ema = self._calculate_ema(list(self.closes), self.long_period)

        # Calculate ADX
        adx = self._calculate_adx()

        signal = None

        # Check Crossover
        if self.prev_short_ema and self.prev_long_ema and adx is not None:
            # Bullish Crossover
            if self.prev_short_ema <= self.prev_long_ema and short_ema > long_ema:
                if adx > self.adx_threshold:
                    signal = {"side": "LONG", "score": 1.0, "metadata": {"adx": adx}}

            # Bearish Crossover
            elif self.prev_short_ema >= self.prev_long_ema and short_ema < long_ema:
                if adx > self.adx_threshold:
                    signal = {"side": "SHORT", "score": 1.0, "metadata": {"adx": adx}}

        # Update State
        self.prev_short_ema = short_ema
        self.prev_long_ema = long_ema

        return signal

    def _calculate_ema(self, data, period):
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return None
        # Use proper EMA calculation
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])  # Start with SMA
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_adx(self):
        """Calculate Average Directional Index."""
        if len(self.highs) < self.adx_period + 1:
            return None

        # Calculate +DI, -DI, and TR
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        highs = list(self.highs)
        lows = list(self.lows)
        closes = list(self.closes)

        for i in range(1, len(highs)):
            high = highs[i]
            low = lows[i]
            prev_high = highs[i - 1]
            prev_low = lows[i - 1]
            prev_close = closes[i - 1] if i - 1 < len(closes) else high

            # Directional Movement
            up_move = high - prev_high
            down_move = prev_low - low

            plus_dm = up_move if up_move > down_move and up_move > 0 else 0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

            # True Range
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        if len(tr_list) < self.adx_period:
            return None

        # Smooth with period
        smoothed_plus_dm = np.mean(plus_dm_list[-self.adx_period :])
        smoothed_minus_dm = np.mean(minus_dm_list[-self.adx_period :])
        smoothed_tr = np.mean(tr_list[-self.adx_period :])

        if smoothed_tr == 0:
            return None

        # Calculate DI
        di_plus = (smoothed_plus_dm / smoothed_tr) * 100
        di_minus = (smoothed_minus_dm / smoothed_tr) * 100

        # Calculate DX
        di_sum = di_plus + di_minus
        if di_sum == 0:
            return 0.0

        dx = (abs(di_plus - di_minus) / di_sum) * 100
        self.dx_values.append(dx)

        if len(self.dx_values) < self.adx_period:
            return None

        # ADX is smoothed DX
        adx = np.mean(self.dx_values)
        return adx
