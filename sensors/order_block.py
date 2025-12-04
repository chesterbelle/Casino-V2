"""
OrderBlock Sensor (V3).
Logic: Breakout from tight consolidation block.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class OrderBlockV3(SensorV3):
    @property
    def name(self) -> str:
        return "OrderBlock"

    def __init__(self, block_size=3, max_range_pct=0.001, breakout_pct=0.003):
        self.block_size = block_size
        self.max_range_pct = max_range_pct
        self.breakout_pct = breakout_pct
        self.candles = deque(maxlen=20)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        self.candles.append([candle["open"], candle["high"], candle["low"], candle["close"]])

        if len(self.candles) < self.block_size + 1:
            return None

        block_candles = list(self.candles)[-(self.block_size + 1) : -1]
        block_highs = [c[1] for c in block_candles]
        block_lows = [c[2] for c in block_candles]
        block_high = max(block_highs)
        block_low = min(block_lows)

        avg_price = np.mean([c[3] for c in block_candles])
        block_range_pct = (block_high - block_low) / avg_price

        if block_range_pct > self.max_range_pct:
            return None

        close = candle["close"]
        signal = None

        if close > block_high * (1 + self.breakout_pct):
            signal = {"side": "LONG", "score": 1.0, "metadata": {"block_range_pct": block_range_pct}}
        elif close < block_low * (1 - self.breakout_pct):
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"block_range_pct": block_range_pct}}

        return signal
