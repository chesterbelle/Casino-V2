"""
WilliamsRReversion Sensor (V3).
Logic: Williams %R oversold/overbought.
"""
import logging
from collections import deque
from .base import SensorV3

logger = logging.getLogger(__name__)

class WilliamsRReversionV3(SensorV3):
    @property
    def name(self) -> str:
        return "WilliamsRReversion"

    def __init__(self, period=14, oversold=-80.0, overbought=-20.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.highs = deque(maxlen=period)
        self.lows = deque(maxlen=period)
        self.closes = deque(maxlen=period)

    def calculate(self, candle: dict) -> dict:
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])
        
        if len(self.closes) < self.period:
            return None
            
        williams_r = self._compute_williams_r()
        signal = None
        
        if williams_r < self.oversold:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"williams_r": williams_r}}
        elif williams_r > self.overbought:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"williams_r": williams_r}}
            
        return signal

    def _compute_williams_r(self):
        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        current_close = self.closes[-1]
        
        if highest_high == lowest_low:
            return -50.0
            
        williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
        return williams_r
