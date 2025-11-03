"""
📉 RSI Reversion (subcarpeta de Sensores de Reversión)
------------------------------------------------------
Detecta condiciones extremas de sobrecompra/sobreventa
utilizando un RSI de periodo corto suavizado.
"""

from __future__ import annotations

import numpy as np


class RSIReversion:
    def __init__(self, period: int = 2, low: float = 10.0, high: float = 90.0):
        self.period = period
        self.low = low
        self.high = high
        self.prices: list[float] = []

    def compute_rsi(self) -> float:
        if len(self.prices) < self.period + 1:
            return 50.0
        delta = np.diff(self.prices)
        gains = np.maximum(delta, 0)
        losses = np.abs(np.minimum(delta, 0))
        avg_gain = np.mean(gains[-self.period :])
        avg_loss = np.mean(losses[-self.period :])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def check_signal(self, candle: dict):
        close = candle["close"]
        self.prices.append(close)
        if len(self.prices) > 250:
            self.prices.pop(0)

        rsi = self.compute_rsi()

        if rsi < self.low:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {"rsi2": rsi, "bbw": 0.0},
            }
        if rsi > self.high:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {"rsi2": rsi, "bbw": 0.0},
            }
        return None
