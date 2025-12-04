"""
VolatilityWakeup Sensor (V3).
Logic: Detects volatility expansion after compression.

When volatility (ATR) expands significantly from a low base,
it often signals the start of a directional move.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VolatilityWakeupV3(SensorV3):
    @property
    def name(self) -> str:
        return "VolatilityWakeup"

    def __init__(self, atr_period=14, expansion_factor=1.5, compression_lookback=10):
        """
        Args:
            atr_period: Period for ATR calculation
            expansion_factor: ATR must expand by this factor
            compression_lookback: Period to measure compression
        """
        self.atr_period = atr_period
        self.expansion_factor = expansion_factor
        self.compression_lookback = compression_lookback

        self.trs = deque(maxlen=atr_period + compression_lookback + 10)
        self.candles = deque(maxlen=atr_period + compression_lookback + 10)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)

        # Calculate True Range
        tr = self._calculate_tr(candle)
        self.trs.append(tr)

        if len(self.trs) < self.atr_period + self.compression_lookback:
            return None

        signal = self._check_wakeup(candle)
        return signal

    def _calculate_tr(self, candle):
        """Calculate True Range."""
        high = candle["high"]
        low = candle["low"]

        if len(self.candles) < 2:
            return high - low

        prev_close = self.candles[-2]["close"]
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def _check_wakeup(self, candle):
        """Check for volatility expansion."""
        trs = list(self.trs)

        # Current ATR
        current_atr = np.mean(trs[-self.atr_period :])

        # ATR during compression period
        compression_trs = trs[-(self.atr_period + self.compression_lookback) : -self.atr_period]
        compression_atr = np.mean(compression_trs) if compression_trs else current_atr

        if compression_atr == 0:
            return None

        # Check for expansion
        expansion_ratio = current_atr / compression_atr
        if expansion_ratio < self.expansion_factor:
            return None

        # Determine direction from current candle
        close = candle["close"]
        open_price = candle["open"]

        if close > open_price:
            return {
                "side": "LONG",
                "score": min(expansion_ratio / 2, 1.0),
                "metadata": {
                    "expansion_ratio": expansion_ratio,
                    "current_atr": current_atr,
                    "compression_atr": compression_atr,
                },
            }
        elif close < open_price:
            return {
                "side": "SHORT",
                "score": min(expansion_ratio / 2, 1.0),
                "metadata": {
                    "expansion_ratio": expansion_ratio,
                    "current_atr": current_atr,
                    "compression_atr": compression_atr,
                },
            }

        return None
