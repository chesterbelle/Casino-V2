"""
BollingerRejection Sensor (V3).
Logic: Detects price rejection at Bollinger Band edges.

A rejection occurs when price touches or exceeds a band
but closes back inside, indicating reversal potential.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class BollingerRejectionV3(SensorV3):
    @property
    def name(self) -> str:
        return "BollingerRejection"

    def __init__(self, period=20, std_dev=2.0, rejection_threshold=0.002):
        """
        Args:
            period: Period for Bollinger Bands
            std_dev: Standard deviation multiplier
            rejection_threshold: Min % to confirm rejection
        """
        self.period = period
        self.std_dev = std_dev
        self.rejection_threshold = rejection_threshold

        self.closes = deque(maxlen=period + 10)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.closes.append(candle["close"])

        if len(self.closes) < self.period:
            return None

        # Calculate Bollinger Bands
        closes = list(self.closes)[-self.period :]
        sma = np.mean(closes)
        std = np.std(closes)

        upper_band = sma + (self.std_dev * std)
        lower_band = sma - (self.std_dev * std)

        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        open_price = candle["open"]

        # Lower band rejection (bullish)
        if low < lower_band:
            rejection_pct = (close - low) / low if low > 0 else 0
            closed_inside = close > lower_band
            bullish = close > open_price

            if closed_inside and rejection_pct > self.rejection_threshold and bullish:
                return {
                    "side": "LONG",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "lower_band_rejection",
                        "lower_band": lower_band,
                        "low": low,
                        "rejection_pct": rejection_pct,
                    },
                }

        # Upper band rejection (bearish)
        if high > upper_band:
            rejection_pct = (high - close) / high if high > 0 else 0
            closed_inside = close < upper_band
            bearish = close < open_price

            if closed_inside and rejection_pct > self.rejection_threshold and bearish:
                return {
                    "side": "SHORT",
                    "score": 1.0,
                    "metadata": {
                        "pattern": "upper_band_rejection",
                        "upper_band": upper_band,
                        "high": high,
                        "rejection_pct": rejection_pct,
                    },
                }

        return None
