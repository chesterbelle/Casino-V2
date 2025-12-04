"""
AdaptiveRSI Sensor (V3).
Logic: Adaptive RSI with dynamic overbought/oversold levels.

Uses volatility to adjust RSI thresholds dynamically.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class AdaptiveRSIV3(SensorV3):
    @property
    def name(self) -> str:
        return "AdaptiveRSI"

    def __init__(self, rsi_period=14, base_oversold=30, base_overbought=70, volatility_period=20):
        """
        Args:
            rsi_period: Period for RSI calculation
            base_oversold: Base oversold level (adjusted by volatility)
            base_overbought: Base overbought level (adjusted by volatility)
            volatility_period: Period for volatility adjustment
        """
        self.rsi_period = rsi_period
        self.base_oversold = base_oversold
        self.base_overbought = base_overbought
        self.volatility_period = volatility_period

        self.closes = deque(maxlen=max(rsi_period, volatility_period) + 10)
        self.gains = deque(maxlen=rsi_period)
        self.losses = deque(maxlen=rsi_period)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.closes.append(candle["close"])

        if len(self.closes) < self.rsi_period + 1:
            return None

        # Calculate price change
        change = self.closes[-1] - self.closes[-2]
        gain = max(change, 0)
        loss = abs(min(change, 0))

        self.gains.append(gain)
        self.losses.append(loss)

        if len(self.gains) < self.rsi_period:
            return None

        # Calculate RSI
        avg_gain = np.mean(self.gains)
        avg_loss = np.mean(self.losses)

        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Calculate adaptive thresholds based on volatility
        oversold, overbought = self._calculate_adaptive_levels()

        # Generate signals
        if rsi < oversold:
            return {
                "side": "LONG",
                "score": (oversold - rsi) / oversold,
                "metadata": {
                    "rsi": rsi,
                    "oversold_level": oversold,
                    "adaptive": True,
                },
            }

        if rsi > overbought:
            return {
                "side": "SHORT",
                "score": (rsi - overbought) / (100 - overbought),
                "metadata": {
                    "rsi": rsi,
                    "overbought_level": overbought,
                    "adaptive": True,
                },
            }

        return None

    def _calculate_adaptive_levels(self):
        """Calculate adaptive OB/OS levels based on volatility."""
        if len(self.closes) < self.volatility_period:
            return self.base_oversold, self.base_overbought

        closes = list(self.closes)[-self.volatility_period :]
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * 100  # As percentage

        # Higher volatility = wider bands
        adjustment = min(volatility * 5, 15)  # Max 15 point adjustment

        oversold = max(10, self.base_oversold - adjustment)
        overbought = min(90, self.base_overbought + adjustment)

        return oversold, overbought
