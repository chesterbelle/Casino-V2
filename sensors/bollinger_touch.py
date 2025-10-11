"""
📊 Bollinger Touch
------------------
Detecta toques en bandas de Bollinger (reversión a la media).
"""

import pandas as pd
import numpy as np

class BollingerTouch:
    def __init__(self, window=20, std_dev=2):
        self.window = window
        self.std_dev = std_dev
        self.data = []

    def check_signal(self, candle: dict):
        close = candle["close"]
        self.data.append(close)
        if len(self.data) < self.window:
            return None

        series = pd.Series(self.data[-self.window:])
        ma = series.mean()
        std = series.std()
        upper = ma + self.std_dev * std
        lower = ma - self.std_dev * std

        if close <= lower:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "origin": "BollingerTouch",
                "range_score": 1,
                "features": {"bbw": (upper - lower) / ma}
            }
        elif close >= upper:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "origin": "BollingerTouch",
                "range_score": 1,
                "features": {"bbw": (upper - lower) / ma}
            }
        return None
