"""
VolumeImbalance Sensor (V3).
Logic: Buying/selling pressure imbalance detection.
"""
import logging
from collections import deque
import numpy as np
from .base import SensorV3

logger = logging.getLogger(__name__)

class VolumeImbalanceV3(SensorV3):
    @property
    def name(self) -> str:
        return "VolumeImbalance"

    def __init__(self, volume_period=20, imbalance_ratio=3.0):
        self.volume_period = volume_period
        self.imbalance_ratio = imbalance_ratio
        self.volumes = deque(maxlen=volume_period)

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]
        open_p = candle["open"]
        volume = candle["volume"]
        
        self.volumes.append(volume)
        
        if len(self.volumes) < self.volume_period:
            return None
            
        avg_volume = np.mean(self.volumes)
        
        if volume < avg_volume:
            return None
            
        buying_pressure = close - low
        selling_pressure = high - close
        
        if selling_pressure == 0:
            selling_pressure = 0.000001
        if buying_pressure == 0:
            buying_pressure = 0.000001
            
        signal = None
        
        if buying_pressure > (selling_pressure * self.imbalance_ratio):
            if close > open_p:
                signal = {"side": "LONG", "score": 1.0, "metadata": {"vol_ratio": volume/avg_volume}}
        elif selling_pressure > (buying_pressure * self.imbalance_ratio):
            if close < open_p:
                signal = {"side": "SHORT", "score": 1.0, "metadata": {"vol_ratio": volume/avg_volume}}
                
        return signal
