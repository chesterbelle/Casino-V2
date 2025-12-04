"""
RailsPattern Sensor (V3).
Tier 1: 69% Win Rate.
Logic: Two consecutive candles with similar range but opposite direction.
"""

import logging

from .base import SensorV3

logger = logging.getLogger(__name__)


class RailsPatternV3(SensorV3):
    @property
    def name(self) -> str:
        return "RailsPattern"

    def __init__(self, max_diff_pct=0.1):
        self.max_diff_pct = max_diff_pct
        self.prev_candle = None

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        if not self.prev_candle:
            self.prev_candle = candle
            return None

        prev = self.prev_candle
        curr = candle

        prev_open = prev["open"]
        prev_close = prev["close"]
        curr_open = curr["open"]
        curr_close = curr["close"]

        prev_body = abs(prev_close - prev_open)
        curr_body = abs(curr_close - curr_open)

        signal = None

        # Check if bodies are similar size
        if prev_body > 0:
            diff_pct = abs(prev_body - curr_body) / prev_body
            if diff_pct < self.max_diff_pct:
                # Bullish Rails: Red then Green
                if (prev_close < prev_open) and (curr_close > curr_open):
                    signal = {"side": "LONG", "score": 1.0, "metadata": {"diff_pct": diff_pct}}

                # Bearish Rails: Green then Red
                elif (prev_close > prev_open) and (curr_close < curr_open):
                    signal = {"side": "SHORT", "score": 1.0, "metadata": {"diff_pct": diff_pct}}

        self.prev_candle = curr
        return signal
