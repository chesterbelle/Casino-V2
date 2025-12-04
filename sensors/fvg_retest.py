"""
FVGRetest Sensor (V3).
Logic: Fair Value Gap retest detection.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class FVGRetestV3(SensorV3):
    @property
    def name(self) -> str:
        return "FVGRetest"

    def __init__(self, min_gap_pct=0.001):
        self.min_gap_pct = min_gap_pct
        self.candles = deque(maxlen=100)
        self.active_fvgs = []

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.candles.append([candle["open"], candle["high"], candle["low"], candle["close"]])

        if len(self.candles) < 4:
            return None

        # Detect new FVGs
        if len(self.candles) >= 4:
            c1 = self.candles[-4]
            c3 = self.candles[-2]

            # Bullish FVG
            if c1[1] < c3[2]:
                gap_size = (c3[2] - c1[1]) / c1[1]
                if gap_size > self.min_gap_pct:
                    self.active_fvgs.append({"type": "bullish", "top": c3[2], "bottom": c1[1], "filled": False})

            # Bearish FVG
            if c1[2] > c3[1]:
                gap_size = (c1[2] - c3[1]) / c3[1]
                if gap_size > self.min_gap_pct:
                    self.active_fvgs.append({"type": "bearish", "top": c1[2], "bottom": c3[1], "filled": False})

        if len(self.active_fvgs) > 5:
            self.active_fvgs.pop(0)

        cur_low = candle["low"]
        cur_high = candle["high"]

        for fvg in self.active_fvgs:
            if fvg["filled"] or fvg.get("signaled"):
                continue

            if fvg["type"] == "bullish":
                if cur_low <= fvg["top"] and cur_low >= fvg["bottom"]:
                    fvg["signaled"] = True
                    return {"side": "LONG", "score": 1.0, "metadata": {"fvg_type": "bullish"}}
            elif fvg["type"] == "bearish":
                if cur_high >= fvg["bottom"] and cur_high <= fvg["top"]:
                    fvg["signaled"] = True
                    return {"side": "SHORT", "score": 1.0, "metadata": {"fvg_type": "bearish"}}

        return None
