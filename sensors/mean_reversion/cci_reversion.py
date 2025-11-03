"""
📉 CCI Reversion (Commodity Channel Index)
-------------------------------------------
Mide la desviación del precio respecto a su media.
Útil para detectar extremos de precio.

Lógica:
- CCI > +100 → Overbought → SHORT
- CCI < -100 → Oversold → LONG

Fórmula:
CCI = (Typical Price - SMA) / (0.015 * Mean Deviation)
Typical Price = (High + Low + Close) / 3
"""

from __future__ import annotations

from collections import deque

import numpy as np


class CCIReversion:
    def __init__(self, period: int = 20, oversold: float = -100.0, overbought: float = 100.0, constant: float = 0.015):
        """
        Args:
            period: Periodo para SMA y mean deviation
            oversold: Nivel oversold (típico: -100)
            overbought: Nivel overbought (típico: +100)
            constant: Constante de Lambert (típico: 0.015)
        """
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.constant = constant

        self.typical_prices = deque(maxlen=period)

    def _compute_cci(self) -> float:
        """Calcula CCI"""
        if len(self.typical_prices) < self.period:
            return 0.0

        tp_array = np.array(self.typical_prices)

        # SMA de Typical Price
        sma_tp = np.mean(tp_array)

        # Mean Deviation
        mean_deviation = np.mean(np.abs(tp_array - sma_tp))

        if mean_deviation == 0:
            return 0.0

        # CCI
        current_tp = self.typical_prices[-1]
        cci = (current_tp - sma_tp) / (self.constant * mean_deviation)

        return cci

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        # Typical Price
        typical_price = (high + low + close) / 3
        self.typical_prices.append(typical_price)

        if len(self.typical_prices) < self.period:
            return None

        cci = self._compute_cci()

        # Oversold → LONG
        if cci < self.oversold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {"cci": cci, "state": "oversold"},
            }

        # Overbought → SHORT
        if cci > self.overbought:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {"cci": cci, "state": "overbought"},
            }

        return None
