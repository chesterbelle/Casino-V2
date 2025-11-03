"""
📊 Bollinger Touch (Sensores de Reversión)
-----------------------------------------
Detecta toques o rupturas en las bandas de Bollinger
para anticipar posibles movimientos de reversión.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class BollingerTouch:
    def __init__(self, window: int = 20, std_dev: float = 2.5):
        self.window = window
        self.std_dev = std_dev
        self.data: list[float] = []

    def check_signal(self, candle: dict):
        close = candle["close"]
        self.data.append(close)
        if len(self.data) < self.window:
            return None

        series = pd.Series(self.data[-self.window :])
        ma = series.mean()
        std = series.std(ddof=0)
        upper = ma + self.std_dev * std
        lower = ma - self.std_dev * std

        bbw = (upper - lower) / ma if ma else 0.0

        if close <= lower:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {"bbw": bbw},
            }
        if close >= upper:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {"bbw": bbw},
            }
        return None
