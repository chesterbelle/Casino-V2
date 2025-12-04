"""
EMA50Support Sensor (V3).
Tier 2: Excellent.
Logic: Bounces off EMA50 in trend.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class EMA50SupportV3(SensorV3):
    @property
    def name(self) -> str:
        return "EMA50Support"

    def __init__(self, ema_period=50, tolerance_pct=0.001):
        self.ema_period = ema_period
        self.tolerance_pct = tolerance_pct
        self.closes = deque(maxlen=ema_period + 10)
        self.ema_val = None

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]
        open_p = candle["open"]

        self.closes.append(close)
        self._update_ema(close)

        if self.ema_val is None or len(self.closes) < self.ema_period:
            return None

        touch_threshold = self.ema_val * self.tolerance_pct
        signal = None

        # LONG: Low touches EMA, Close respects it
        if low <= (self.ema_val + touch_threshold):
            if close >= (self.ema_val * 0.999):
                is_bullish = close > open_p
                lower_wick = min(close, open_p) - low
                body = abs(close - open_p)
                is_hammer = lower_wick > body

                if is_bullish or is_hammer:
                    signal = {"side": "LONG", "score": 1.0, "metadata": {"ema": self.ema_val}}

        # SHORT: High touches EMA, Close respects it
        elif high >= (self.ema_val - touch_threshold):
            if close <= (self.ema_val * 1.001):
                is_bearish = close < open_p
                upper_wick = high - max(close, open_p)
                body = abs(close - open_p)
                is_shooting_star = upper_wick > body

                if is_bearish or is_shooting_star:
                    signal = {"side": "SHORT", "score": 1.0, "metadata": {"ema": self.ema_val}}

        return signal

    def _update_ema(self, close: float):
        k = 2 / (self.ema_period + 1)
        if self.ema_val is None:
            self.ema_val = close
        else:
            self.ema_val = (close * k) + (self.ema_val * (1 - k))
