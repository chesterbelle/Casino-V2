"""
📊 VWAP Deviation
-----------------
Volume Weighted Average Price - Precio promedio ponderado por volumen.
Muy usado por institucionales como referencia de "precio justo".

Lógica:
- Precio muy por debajo de VWAP → Comprar barato → LONG
- Precio muy por encima de VWAP → Vender caro → SHORT

VWAP se resetea cada sesión (intraday), pero para crypto usamos rolling.

Fórmula:
VWAP = Σ(Precio Típico * Volumen) / Σ(Volumen)
"""

from __future__ import annotations

from collections import deque

import numpy as np


class VWAPDeviation:
    def __init__(self, period: int = 20, deviation_threshold: float = 0.015):  # 1.5%
        """
        Args:
            period: Periodo rolling para VWAP
            deviation_threshold: % de desviación para señal
        """
        self.period = period
        self.deviation_threshold = deviation_threshold

        self.typical_prices = deque(maxlen=period)
        self.volumes = deque(maxlen=period)

    def _compute_vwap(self) -> float:
        """Calcula VWAP"""
        if not self.typical_prices or not self.volumes:
            return 0.0

        tp_array = np.array(self.typical_prices)
        vol_array = np.array(self.volumes)

        total_volume = np.sum(vol_array)
        if total_volume == 0:
            return 0.0

        vwap = np.sum(tp_array * vol_array) / total_volume
        return vwap

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        volume = float(candle.get("volume", 0))

        # Typical Price
        typical_price = (high + low + close) / 3

        self.typical_prices.append(typical_price)
        self.volumes.append(volume)

        if len(self.typical_prices) < self.period:
            return None

        vwap = self._compute_vwap()
        if vwap == 0:
            return None

        # Desviación porcentual
        deviation = (close - vwap) / vwap

        # Precio muy por debajo de VWAP → LONG (comprar barato)
        if deviation < -self.deviation_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "vwap": vwap,
                    "price": close,
                    "deviation": deviation,
                    "deviation_pct": deviation * 100,
                    "state": "below_vwap",
                },
            }

        # Precio muy por encima de VWAP → SHORT (vender caro)
        if deviation > self.deviation_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "vwap": vwap,
                    "price": close,
                    "deviation": deviation,
                    "deviation_pct": deviation * 100,
                    "state": "above_vwap",
                },
            }

        return None
