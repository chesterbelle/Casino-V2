"""
VWAPBreakout Sensor (V3).
Logic: Detects breakouts from VWAP with volume confirmation.

VWAP acts as dynamic support/resistance for institutional traders.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class VWAPBreakoutV3(SensorV3):
    @property
    def name(self) -> str:
        return "VWAPBreakout"

    def __init__(self, std_dev_mult=1.0, volume_factor=1.2, lookback=50):
        """
        Args:
            std_dev_mult: Standard deviation bands around VWAP
            volume_factor: Min volume ratio for confirmation
            lookback: Period for VWAP calculation
        """
        self.std_dev_mult = std_dev_mult
        self.volume_factor = volume_factor
        self.lookback = lookback

        self.candles = deque(maxlen=lookback + 10)
        self.volumes = deque(maxlen=lookback + 10)
        self.typical_prices = deque(maxlen=lookback + 10)
        self.cum_tp_vol = 0
        self.cum_vol = 0

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle.get("volume", 1)

        typical_price = (high + low + close) / 3

        self.candles.append(candle)
        self.volumes.append(volume)
        self.typical_prices.append(typical_price)

        # Update cumulative values
        self.cum_tp_vol += typical_price * volume
        self.cum_vol += volume

        if len(self.candles) < 20:
            return None

        # Calculate VWAP
        if self.cum_vol == 0:
            return None

        vwap = self.cum_tp_vol / self.cum_vol

        # Calculate standard deviation for bands
        tps = list(self.typical_prices)
        std = np.std(tps) if len(tps) > 1 else 0

        upper_band = vwap + (self.std_dev_mult * std)
        lower_band = vwap - (self.std_dev_mult * std)

        # Check volume confirmation
        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else 1
        volume_confirmed = volume > avg_volume * self.volume_factor

        open_price = candle["open"]

        # Bullish breakout: Close above upper band with volume
        if close > upper_band and close > open_price and volume_confirmed:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "pattern": "vwap_breakout_up",
                    "vwap": vwap,
                    "upper_band": upper_band,
                    "volume_ratio": volume / avg_volume,
                },
            }

        # Bearish breakout: Close below lower band with volume
        if close < lower_band and close < open_price and volume_confirmed:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "pattern": "vwap_breakout_down",
                    "vwap": vwap,
                    "lower_band": lower_band,
                    "volume_ratio": volume / avg_volume,
                },
            }

        return None
