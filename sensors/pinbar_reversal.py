"""
PinBarReversal Sensor (V3).
Tier 1: 76% Win Rate.
Logic: Wick > 2x Body + Close in top/bottom 30%.
"""

import logging

from .base import SensorV3

logger = logging.getLogger(__name__)


class PinBarReversalV3(SensorV3):
    @property
    def name(self) -> str:
        return "PinBarReversal"

    def __init__(self, wick_ratio=2.0, position_threshold=0.3):
        self.wick_ratio = wick_ratio
        self.position_threshold = position_threshold

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        open_p = candle["open"]
        close_p = candle["close"]
        high_p = candle["high"]
        low_p = candle["low"]

        body_size = abs(close_p - open_p)
        total_range = high_p - low_p

        if total_range == 0:
            return None

        # Calculate Wicks
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p

        signal = None

        # Bearish Pin Bar (Long Upper Wick)
        if upper_wick > (body_size * self.wick_ratio):
            # Close near bottom
            close_pos = (close_p - low_p) / total_range
            if close_pos < self.position_threshold:
                signal = {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {"wick_ratio": upper_wick / body_size if body_size else 99},
                }

        # Bullish Pin Bar (Long Lower Wick)
        elif lower_wick > (body_size * self.wick_ratio):
            # Close near top
            close_pos = (close_p - low_p) / total_range
            if close_pos > (1 - self.position_threshold):
                signal = {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {"wick_ratio": lower_wick / body_size if body_size else 99},
                }

        return signal
