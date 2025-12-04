"""
MorningStar Sensor (V3).
Logic: Morning Star / Evening Star 3-candle reversal.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class MorningStarV3(SensorV3):
    @property
    def name(self) -> str:
        return "MorningStar"

    def __init__(self, min_large_body_pct=0.004, max_star_body_pct=0.002):
        self.min_large_body_pct = min_large_body_pct
        self.max_star_body_pct = max_star_body_pct
        self.candles = deque(maxlen=10)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)

        if len(self.candles) < 3:
            return None

        c1 = self.candles[-3]
        c2 = self.candles[-2]
        c3 = self.candles[-1]

        c1_body = abs(c1["close"] - c1["open"])
        c2_body = abs(c2["close"] - c2["open"])
        c3_body = abs(c3["close"] - c3["open"])

        price = c3["close"]
        c1_body_pct = c1_body / price
        c2_body_pct = c2_body / price
        c3_body_pct = c3_body / price

        if (
            c1_body_pct < self.min_large_body_pct
            or c2_body_pct > self.max_star_body_pct
            or c3_body_pct < self.min_large_body_pct
        ):
            return None

        signal = None

        # Morning Star
        if c1["close"] < c1["open"] and c3["close"] > c3["open"]:
            c1_midpoint = (c1["open"] + c1["close"]) / 2
            if c3["close"] > c1_midpoint:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"pattern": "morning_star"}}

        # Evening Star
        elif c1["close"] > c1["open"] and c3["close"] < c3["open"]:
            c1_midpoint = (c1["open"] + c1["close"]) / 2
            if c3["close"] < c1_midpoint:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"pattern": "evening_star"}}

        return signal
