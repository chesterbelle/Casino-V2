"""
📉 Keltner Reversion
--------------------
Detecta reversiones cuando el precio toca los canales de Keltner.
"""

import pandas as pd
import numpy as np

class KeltnerReversion:
    def __init__(self, window=20, multiplier=1.25):
        self.window = window
        self.multiplier = multiplier
        self.highs, self.lows, self.closes = [], [], []

    def check_signal(self, candle: dict):
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])

        if len(self.closes) < self.window:
            return None

        df = pd.DataFrame({"high": self.highs[-self.window:],
                           "low": self.lows[-self.window:],
                           "close": self.closes[-self.window:]})

        typical = (df["high"] + df["low"] + df["close"]) / 3
        ema = typical.ewm(span=self.window, adjust=False).mean().iloc[-1]
        tr = np.maximum(df["high"] - df["low"],
                        abs(df["high"] - df["close"].shift(1)),
                        abs(df["low"] - df["close"].shift(1)))
        atr = tr.mean()

        upper = ema + self.multiplier * atr
        lower = ema - self.multiplier * atr
        close = self.closes[-1]

        if close < lower:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {"atr": atr}
            }
        elif close > upper:
            return {
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {"atr": atr}
            }
        return None

