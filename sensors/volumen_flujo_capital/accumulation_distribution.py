"""
📈 Accumulation/Distribution (A/D Line)
---------------------------------------
Mide el flujo acumulado de dinero entrando/saliendo.
Divergencias con precio son señales potentes.

Lógica:
- A/D subiendo + Precio bajando → Divergencia alcista → LONG
- A/D bajando + Precio subiendo → Divergencia bajista → SHORT

Fórmula:
Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
Money Flow Volume = Money Flow Multiplier * Volume
A/D = Suma acumulada de Money Flow Volume
"""

from __future__ import annotations

from collections import deque

import numpy as np


class AccumulationDistribution:
    def __init__(self, lookback: int = 14, divergence_threshold: float = 0.02):  # 2% divergencia mínima
        """
        Args:
            lookback: Periodo para detectar divergencias
            divergence_threshold: Mínima divergencia para señal
        """
        self.lookback = lookback
        self.divergence_threshold = divergence_threshold

        self.ad_line = 0.0  # Acumulativo
        self.ad_values = deque(maxlen=lookback)
        self.closes = deque(maxlen=lookback)

    def _compute_ad_value(self, high: float, low: float, close: float, volume: float) -> float:
        """Calcula el valor A/D para una vela"""
        if high == low:
            return 0.0

        # Money Flow Multiplier
        mfm = ((close - low) - (high - close)) / (high - low)

        # Money Flow Volume
        mfv = mfm * volume

        return mfv

    def _detect_divergence(self) -> str:
        """
        Detecta divergencias entre precio y A/D line.

        Returns:
            "bullish" - Divergencia alcista
            "bearish" - Divergencia bajista
            None - Sin divergencia
        """
        if len(self.ad_values) < self.lookback or len(self.closes) < self.lookback:
            return None

        ad_array = np.array(self.ad_values)
        closes_array = np.array(self.closes)

        # Tendencia de A/D (pendiente lineal)
        ad_slope = np.polyfit(range(len(ad_array)), ad_array, 1)[0]

        # Tendencia de Precio
        price_slope = np.polyfit(range(len(closes_array)), closes_array, 1)[0]

        # Normalizar por valores
        ad_trend = ad_slope / (np.mean(ad_array) if np.mean(ad_array) != 0 else 1)
        price_trend = price_slope / (np.mean(closes_array) if np.mean(closes_array) != 0 else 1)

        # Divergencia alcista: A/D sube, Precio baja
        if ad_trend > self.divergence_threshold and price_trend < -self.divergence_threshold:
            return "bullish"

        # Divergencia bajista: A/D baja, Precio sube
        if ad_trend < -self.divergence_threshold and price_trend > self.divergence_threshold:
            return "bearish"

        return None

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        volume = float(candle.get("volume", 0))

        # Calcular A/D value para esta vela
        ad_value = self._compute_ad_value(high, low, close, volume)

        # Acumular
        self.ad_line += ad_value

        # Guardar para divergencias
        self.ad_values.append(self.ad_line)
        self.closes.append(close)

        if len(self.ad_values) < self.lookback:
            return None

        # Detectar divergencia
        divergence = self._detect_divergence()

        if divergence == "bullish":
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 3,  # Divergencia = señal fuerte
                "features": {"ad_line": self.ad_line, "divergence": "bullish", "type": "accumulation"},
            }

        elif divergence == "bearish":
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 3,
                "features": {"ad_line": self.ad_line, "divergence": "bearish", "type": "distribution"},
            }

        return None
