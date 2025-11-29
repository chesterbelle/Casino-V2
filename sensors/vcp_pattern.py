"""
VCPPattern Sensor (V3).
Tier 3: Good.
Logic: Volatility Contraction Pattern.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VCPPatternV3(SensorV3):
    @property
    def name(self) -> str:
        return "VCPPattern"

    def __init__(self, contractions=3):
        self.contractions = contractions
        self.candles = deque(maxlen=contractions)

    def calculate(self, candle: dict) -> dict:
        self.candles.append(candle)
        if len(self.candles) < self.contractions:
            return None

        # Check if ranges are decreasing
        ranges = []
        for c in self.candles:
            ranges.append(c["high"] - c["low"])

        is_contracting = True
        for i in range(len(ranges) - 1):
            if ranges[i + 1] >= ranges[i]:
                is_contracting = False
                break

        if not is_contracting:
            return None

        # Check Volume decreasing (optional but good)
        if self.candles[-1]["volume"] >= self.candles[0]["volume"]:
            return None

        signal = None

        # Determine bias based on close trend
        first_close = self.candles[0]["close"]
        last_close = self.candles[-1]["close"]

        if last_close > first_close:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"pattern": "vcp_bullish"}}
        else:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"pattern": "vcp_bearish"}}

        return signal
