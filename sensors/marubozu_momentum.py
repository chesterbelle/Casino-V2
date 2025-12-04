"""
MarubozuMomentum Sensor (V3).
Tier 2: Excellent.
Logic: Strong directional candles with minimal wicks.
"""

import logging

from .base import SensorV3

logger = logging.getLogger(__name__)


class MarubozuMomentumV3(SensorV3):
    @property
    def name(self) -> str:
        return "MarubozuMomentum"

    def __init__(self, min_body_to_range=0.8, min_body_size_pct=0.004):
        self.min_body_to_range = min_body_to_range
        self.min_body_size_pct = min_body_size_pct

    def calculate(self, context: dict) -> dict:
        candle = context["1m"]
        open_p = candle["open"]
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        total_range = high - low
        if total_range == 0:
            return None

        body = abs(close - open_p)
        body_to_range = body / total_range

        if body_to_range < self.min_body_to_range:
            return None

        body_pct = body / close
        if body_pct < self.min_body_size_pct:
            return None

        signal = None

        # Bullish
        if close > open_p:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"body_pct": body_pct}}

        # Bearish
        elif close < open_p:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"body_pct": body_pct}}

        return signal
