"""
BollingerTouch Sensor (V3).
Logic: Price touches Bollinger Bands (mean reversion).
"""
import logging
from collections import deque
import numpy as np
from .base import SensorV3

logger = logging.getLogger(__name__)

class BollingerTouchV3(SensorV3):
    @property
    def name(self) -> str:
        return "BollingerTouch"

    def __init__(self, window=20, std_dev=2.5):
        self.window = window
        self.std_dev = std_dev
        self.closes = deque(maxlen=window)

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        self.closes.append(close)
        
        if len(self.closes) < self.window:
            return None
            
        closes_arr = np.array(self.closes)
        ma = np.mean(closes_arr)
        std = np.std(closes_arr, ddof=0)
        
        upper = ma + self.std_dev * std
        lower = ma - self.std_dev * std
        
        signal = None
        
        if close <= lower:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"bb_lower": lower}}
        elif close >= upper:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"bb_upper": upper}}
            
        return signal
