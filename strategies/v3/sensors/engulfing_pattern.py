"""
EngulfingPattern Sensor (V3).
Tier 3: Good.
Logic: Engulfing candle with volume confirmation.
"""
import logging
from collections import deque
import numpy as np
from .base import SensorV3

logger = logging.getLogger(__name__)

class EngulfingPatternV3(SensorV3):
    @property
    def name(self) -> str:
        return "EngulfingPattern"

    def __init__(self, volume_multiplier=1.5, min_body_pct=0.002):
        self.volume_multiplier = volume_multiplier
        self.min_body_pct = min_body_pct
        self.volumes = deque(maxlen=10)
        self.prev_candle = None

    def calculate(self, candle: dict) -> dict:
        volume = candle["volume"]
        self.volumes.append(volume)
        
        if not self.prev_candle or len(self.volumes) < 10:
            self.prev_candle = candle
            return None
            
        curr = candle
        prev = self.prev_candle
        
        curr_open = curr["open"]
        curr_close = curr["close"]
        curr_body = curr_close - curr_open
        curr_body_size = abs(curr_body)
        
        prev_open = prev["open"]
        prev_close = prev["close"]
        prev_body = prev_close - prev_open
        prev_body_size = abs(prev_body)
        
        # Check min body size
        if curr_body_size / curr_close < self.min_body_pct:
            self.prev_candle = curr
            return None
            
        # Check Volume
        avg_vol = np.mean(list(self.volumes)[:-1]) # Exclude current
        if volume < avg_vol * self.volume_multiplier:
            self.prev_candle = curr
            return None
            
        signal = None
        
        # Bullish Engulfing
        if (prev_body < 0 and curr_body > 0 and
            curr_open <= prev_close and curr_close >= prev_open and
            curr_body_size > prev_body_size):
            signal = {"side": "LONG", "score": 1.0, "metadata": {"pattern": "bullish_engulfing"}}
            
        # Bearish Engulfing
        elif (prev_body > 0 and curr_body < 0 and
              curr_open >= prev_close and curr_close <= prev_open and
              curr_body_size > prev_body_size):
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"pattern": "bearish_engulfing"}}
            
        self.prev_candle = curr
        return signal
