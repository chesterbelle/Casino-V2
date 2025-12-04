"""
KeltnerBreakout Sensor (V3).
Logic: Detects breakouts from Keltner Channel.

Keltner Channels use ATR instead of standard deviation,
making them more responsive to volatility.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class KeltnerBreakoutV3(SensorV3):
    @property
    def name(self) -> str:
        return "KeltnerBreakout"

    def __init__(self, ema_period=20, atr_period=10, atr_multiplier=2.0):
        """
        Args:
            ema_period: Period for center EMA
            atr_period: Period for ATR calculation
            atr_multiplier: Multiplier for channel width
        """
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

        self.closes = deque(maxlen=max(ema_period, atr_period) + 10)
        self.trs = deque(maxlen=atr_period + 10)
        self.candles = deque(maxlen=atr_period + 10)

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        self.closes.append(candle["close"])
        self.candles.append(candle)

        # Calculate True Range
        tr = self._calculate_tr(candle)
        self.trs.append(tr)

        if len(self.closes) < self.ema_period or len(self.trs) < self.atr_period:
            return None

        # Calculate Keltner Channel
        closes = list(self.closes)
        ema = self._calculate_ema(closes, self.ema_period)
        atr = np.mean(list(self.trs)[-self.atr_period :])

        upper_channel = ema + (self.atr_multiplier * atr)
        lower_channel = ema - (self.atr_multiplier * atr)

        close = candle["close"]
        open_price = candle["open"]

        # Bullish breakout: Close above upper channel
        if close > upper_channel and close > open_price:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "pattern": "keltner_breakout_up",
                    "upper_channel": upper_channel,
                    "ema": ema,
                    "atr": atr,
                },
            }

        # Bearish breakout: Close below lower channel
        if close < lower_channel and close < open_price:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "pattern": "keltner_breakout_down",
                    "lower_channel": lower_channel,
                    "ema": ema,
                    "atr": atr,
                },
            }

        return None

    def _calculate_tr(self, candle):
        """Calculate True Range."""
        high = candle["high"]
        low = candle["low"]

        if len(self.candles) < 2:
            return high - low

        prev_close = self.candles[-2]["close"]
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def _calculate_ema(self, data, period):
        """Calculate EMA."""
        if len(data) < period:
            return np.mean(data)

        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
