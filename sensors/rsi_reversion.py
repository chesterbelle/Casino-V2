"""
📉 RSI Reversion
----------------
Detecta condiciones extremas de sobrecompra/sobreventa.
"""

import pandas as pd
import numpy as np

class RSIReversion:
    def __init__(self, period=2, low=15, high=85):
        self.period = period
        self.low = low
        self.high = high
        self.prices = []

    def compute_rsi(self):
        if len(self.prices) < self.period + 1:
            return 50
        delta = np.diff(self.prices)
        gains = np.maximum(delta, 0)
        losses = np.abs(np.minimum(delta, 0))
        avg_gain = np.mean(gains[-self.period:])
        avg_loss = np.mean(losses[-self.period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def check_signal(self, candle: dict):
        close = candle["close"]
        self.prices.append(close)
        if len(self.prices) > 200:
            self.prices.pop(0)

        rsi = self.compute_rsi()

        if rsi < self.low:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "origin": "RSIReversion",
                "range_score": 1,
                "features": {"rsi2": rsi, "bbw": 0.0}
            }
        elif rsi > self.high:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "origin": "RSIReversion",
                "range_score": 1,
                "features": {"rsi2": rsi, "bbw": 0.0}
            }
        return None
