"""
MomentumBurst Sensor (V3).
Logic: Sudden RSI acceleration (burst detection).
"""
import logging
from collections import deque
import numpy as np
from .base import SensorV3

logger = logging.getLogger(__name__)

class MomentumBurstV3(SensorV3):
    @property
    def name(self) -> str:
        return "MomentumBurst"

    def __init__(self, rsi_period=14, burst_threshold=15.0):
        self.rsi_period = rsi_period
        self.burst_threshold = burst_threshold
        self.closes = deque(maxlen=rsi_period + 1)
        self.gains = deque(maxlen=rsi_period)
        self.losses = deque(maxlen=rsi_period)
        self.prev_rsi = None

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        self.closes.append(close)
        
        if len(self.closes) < self.rsi_period:
            return None
            
        current_rsi = self._calculate_rsi(close)
        
        if self.prev_rsi is None:
            self.prev_rsi = current_rsi
            return None
            
        rsi_delta = current_rsi - self.prev_rsi
        self.prev_rsi = current_rsi
        
        signal = None
        
        if abs(rsi_delta) > self.burst_threshold:
            if rsi_delta > 0 and current_rsi < 60:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"rsi_delta": rsi_delta}}
            elif rsi_delta < 0 and current_rsi > 40:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"rsi_delta": rsi_delta}}
                
        return signal

    def _calculate_rsi(self, current_close):
        if len(self.closes) < 2:
            return 50.0
            
        delta = current_close - self.closes[-2]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))
        
        self.gains.append(gain)
        self.losses.append(loss)
        
        if len(self.gains) < self.rsi_period:
            return 50.0
            
        avg_gain = np.mean(self.gains)
        avg_loss = np.mean(self.losses)
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
