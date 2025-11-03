"""
💰 MFI Reversion (Money Flow Index)
------------------------------------
Similar a RSI pero incorpora volumen.
Mide la presión de compra/venta con volumen ponderado.

Lógica:
- MFI < 20 → Oversold con bajo flujo de dinero → LONG
- MFI > 80 → Overbought con alto flujo de dinero → SHORT

Fórmula:
Typical Price = (H + L + C) / 3
Raw Money Flow = Typical Price * Volume
Money Ratio = Positive Flow / Negative Flow
MFI = 100 - (100 / (1 + Money Ratio))
"""

from __future__ import annotations

from collections import deque

import numpy as np


class MFIReversion:
    def __init__(self, period: int = 14, oversold: float = 20.0, overbought: float = 80.0):
        """
        Args:
            period: Periodo para calcular MFI
            oversold: Nivel oversold (típico: 20)
            overbought: Nivel overbought (típico: 80)
        """
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

        self.typical_prices = deque(maxlen=period + 1)
        self.volumes = deque(maxlen=period + 1)

    def _compute_mfi(self) -> float:
        """Calcula Money Flow Index"""
        if len(self.typical_prices) < self.period + 1:
            return 50.0

        positive_flow = 0.0
        negative_flow = 0.0

        for i in range(1, len(self.typical_prices)):
            typical_price = self.typical_prices[i]
            prev_typical_price = self.typical_prices[i - 1]
            volume = self.volumes[i]

            raw_money_flow = typical_price * volume

            if typical_price > prev_typical_price:
                positive_flow += raw_money_flow
            elif typical_price < prev_typical_price:
                negative_flow += raw_money_flow

        if negative_flow == 0:
            return 100.0

        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))

        return mfi

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        volume = float(candle.get("volume", 0))

        # Typical Price
        typical_price = (high + low + close) / 3

        self.typical_prices.append(typical_price)
        self.volumes.append(volume)

        if len(self.typical_prices) < self.period + 1:
            return None

        mfi = self._compute_mfi()

        # Oversold → LONG
        if mfi < self.oversold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 2,  # Volume-weighted = más confiable
                "features": {"mfi": mfi, "state": "oversold"},
            }

        # Overbought → SHORT
        if mfi > self.overbought:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 2,
                "features": {"mfi": mfi, "state": "overbought"},
            }

        return None
