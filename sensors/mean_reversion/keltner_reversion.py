"""
📉 Keltner Reversion (Sensores de Reversión)
-------------------------------------------
Detecta reversiones cuando el precio se extiende más allá
de los canales de Keltner.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class KeltnerReversion:
    def __init__(self, window: int = 20, multiplier: float = 2.0):
        self.window = window
        self.multiplier = multiplier
        self.highs: list[float] = []
        self.lows: list[float] = []
        self.closes: list[float] = []

    def check_signal(self, candle: dict):
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        if len(self.closes) < self.window:
            return None

        df = pd.DataFrame(
            {
                "high": self.highs[-self.window :],
                "low": self.lows[-self.window :],
                "close": self.closes[-self.window :],
            }
        )

        typical = (df["high"] + df["low"] + df["close"]) / 3
        ema = typical.ewm(span=self.window, adjust=False).mean().iloc[-1]

        prev_close = df["close"].shift(1)
        tr = np.maximum(
            df["high"] - df["low"], np.maximum((df["high"] - prev_close).abs(), (df["low"] - prev_close).abs())
        )
        atr = tr.mean()

        upper = ema + self.multiplier * atr
        lower = ema - self.multiplier * atr
        close = self.closes[-1]

        features = {"atr": float(atr)}

        if close < lower:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": features,
            }
        if close > upper:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": features,
            }
        return None
