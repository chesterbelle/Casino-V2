"""
LiquidityVoid Sensor (V3).
Logic: Detects liquidity voids (gaps) that price may revisit.

A liquidity void is a gap with low volume, often gets filled
as price returns to collect liquidity.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class LiquidityVoidV3(SensorV3):
    @property
    def name(self) -> str:
        return "LiquidityVoid"

    def __init__(self, gap_pct=0.002, max_volume_pct=0.5, lookback=20):
        """
        Args:
            gap_pct: Min gap size as % of price
            max_volume_pct: Max volume ratio for void (low volume gap)
            lookback: Period for tracking voids
        """
        self.gap_pct = gap_pct
        self.max_volume_pct = max_volume_pct
        self.lookback = lookback

        self.candles = deque(maxlen=lookback + 5)
        self.volumes = deque(maxlen=lookback + 5)
        self.voids = []  # List of (top, bottom, direction) tuples

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)
        self.volumes.append(candle.get("volume", 0))

        if len(self.candles) < 2:
            return None

        # Check for new void
        self._detect_void()

        # Check for void fill setup
        signal = self._check_void_fill(candle)
        return signal

    def _detect_void(self):
        """Detect new liquidity void between candles."""
        if len(self.candles) < 2:
            return

        prev = self.candles[-2]
        curr = self.candles[-1]
        volume = curr.get("volume", 0)

        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else 1
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1

        # Only low volume gaps create voids
        if volume_ratio > self.max_volume_pct:
            return

        avg_price = (prev["close"] + curr["open"]) / 2

        # Gap up void
        if curr["low"] > prev["high"]:
            gap_size = (curr["low"] - prev["high"]) / avg_price
            if gap_size > self.gap_pct:
                self.voids.append({"top": curr["low"], "bottom": prev["high"], "direction": "up"})

        # Gap down void
        if curr["high"] < prev["low"]:
            gap_size = (prev["low"] - curr["high"]) / avg_price
            if gap_size > self.gap_pct:
                self.voids.append({"top": prev["low"], "bottom": curr["high"], "direction": "down"})

        # Keep only recent voids
        if len(self.voids) > 5:
            self.voids = self.voids[-5:]

    def _check_void_fill(self, candle):
        """Check if price is approaching a void to fill."""
        if not self.voids:
            return None

        close = candle["close"]

        for void in self.voids:
            void_top = void["top"]
            void_bottom = void["bottom"]

            # Price approaching unfilled gap up void from above = short opportunity
            if void["direction"] == "up":
                distance_pct = (close - void_top) / close if close > 0 else 1
                if 0 < distance_pct < 0.01:  # Within 1% of void
                    return {
                        "side": "SHORT",
                        "score": 0.8,
                        "metadata": {
                            "pattern": "void_fill_down",
                            "void_top": void_top,
                            "void_bottom": void_bottom,
                            "distance_pct": distance_pct,
                        },
                    }

            # Price approaching unfilled gap down void from below = long opportunity
            if void["direction"] == "down":
                distance_pct = (void_bottom - close) / close if close > 0 else 1
                if 0 < distance_pct < 0.01:  # Within 1% of void
                    return {
                        "side": "LONG",
                        "score": 0.8,
                        "metadata": {
                            "pattern": "void_fill_up",
                            "void_top": void_top,
                            "void_bottom": void_bottom,
                            "distance_pct": distance_pct,
                        },
                    }

        return None
