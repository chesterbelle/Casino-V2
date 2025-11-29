"""
ParabolicSAR Sensor (V3).
Logic: SAR trend reversal detection.
"""
import logging
from collections import deque
from .base import SensorV3

logger = logging.getLogger(__name__)

class ParabolicSARV3(SensorV3):
    @property
    def name(self) -> str:
        return "ParabolicSAR"

    def __init__(self, af_start=0.02, af_increment=0.02, af_max=0.20):
        self.af_start = af_start
        self.af_increment = af_increment
        self.af_max = af_max
        self.highs = deque(maxlen=100)
        self.lows = deque(maxlen=100)
        self.sar = None
        self.ep = None
        self.af = af_start
        self.is_long = True

    def calculate(self, candle: dict) -> dict:
        high = candle["high"]
        low = candle["low"]
        
        self.highs.append(high)
        self.lows.append(low)
        
        if self.sar is None:
            if len(self.highs) >= 2:
                self._initialize_sar()
            return None
            
        reversal_side = self._update_sar(high, low)
        
        if reversal_side:
            return {"side": reversal_side, "score": 1.0, "metadata": {"sar": self.sar}}
            
        return None

    def _initialize_sar(self):
        if self.highs[-1] > self.highs[-2]:
            self.is_long = True
            self.sar = min(self.lows[-2], self.lows[-1])
            self.ep = max(self.highs[-2], self.highs[-1])
        else:
            self.is_long = False
            self.sar = max(self.highs[-2], self.highs[-1])
            self.ep = min(self.lows[-2], self.lows[-1])
        self.af = self.af_start

    def _update_sar(self, high, low):
        prev_sar = self.sar
        self.sar = prev_sar + self.af * (self.ep - prev_sar)
        
        if self.is_long:
            self.sar = min(self.sar, self.lows[-1] if len(self.lows) > 0 else low)
            if low < self.sar:
                self.is_long = False
                self.sar = self.ep
                self.ep = low
                self.af = self.af_start
                return "SHORT"
            if high > self.ep:
                self.ep = high
                self.af = min(self.af + self.af_increment, self.af_max)
        else:
            self.sar = max(self.sar, self.highs[-1] if len(self.highs) > 0 else high)
            if high > self.sar:
                self.is_long = True
                self.sar = self.ep
                self.ep = high
                self.af = self.af_start
                return "LONG"
            if low < self.ep:
                self.ep = low
                self.af = min(self.af + self.af_increment, self.af_max)
        return None
