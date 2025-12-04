"""
InsideBarBreakout Sensor (V3).
Tier 3: Good.
Logic: Inside bar followed by breakout.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class InsideBarBreakoutV3(SensorV3):
    @property
    def name(self) -> str:
        return "InsideBarBreakout"

    def __init__(self, max_inside_range_pct=0.005, breakout_confirmation=True):
        self.max_inside_range_pct = max_inside_range_pct
        self.breakout_confirmation = breakout_confirmation
        self.candles = deque(maxlen=3)
        self.inside_bar_detected = False
        self.inside_bar_high = None
        self.inside_bar_low = None

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append(candle)
        if len(self.candles) < 3:
            return None

        curr = self.candles[-1]
        prev = self.candles[-2]
        prev_prev = self.candles[-3]

        curr_high = curr["high"]
        curr_low = curr["low"]
        curr_close = curr["close"]

        prev_high = prev["high"]
        prev_low = prev["low"]

        prev_prev_high = prev_prev["high"]
        prev_prev_low = prev_prev["low"]

        # Check for Inside Bar (Previous candle inside Prev-Prev)
        is_inside_bar = prev_high < prev_prev_high and prev_low > prev_prev_low

        if is_inside_bar:
            inside_range = prev_high - prev_low
            price = curr_close
            inside_range_pct = inside_range / price if price else 0

            if inside_range_pct <= self.max_inside_range_pct:
                self.inside_bar_detected = True
                self.inside_bar_high = prev_high
                self.inside_bar_low = prev_low

        signal = None

        # Check Breakout
        if self.inside_bar_detected:
            # Bullish Breakout
            if curr_high > self.inside_bar_high:
                if not self.breakout_confirmation or curr_close > self.inside_bar_high:
                    self.inside_bar_detected = False
                    signal = {"side": "LONG", "score": 1.0, "metadata": {"pattern": "inside_bar_breakout"}}

            # Bearish Breakout
            elif curr_low < self.inside_bar_low:
                if not self.breakout_confirmation or curr_close < self.inside_bar_low:
                    self.inside_bar_detected = False
                    signal = {"side": "SHORT", "score": 1.0, "metadata": {"pattern": "inside_bar_breakout"}}

        return signal
