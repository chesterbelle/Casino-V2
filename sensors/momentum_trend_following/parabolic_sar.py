"""
🎯 Parabolic SAR (Stop and Reverse)
------------------------------------
Indicador de tendencia que muestra puntos de stop/entrada.
Muy visual y efectivo para trailing stops.

Lógica:
- Precio cruza SAR desde abajo → LONG (flip alcista)
- Precio cruza SAR desde arriba → SHORT (flip bajista)

Características:
- SAR sigue el precio con aceleración
- Ideal para tendencias fuertes
- Malo en sideways (muchos whipsaws)
"""

from __future__ import annotations

from collections import deque

import numpy as np


class ParabolicSAR:
    def __init__(self, af_start: float = 0.02, af_increment: float = 0.02, af_max: float = 0.20):
        """
        Args:
            af_start: Acceleration Factor inicial (típico: 0.02)
            af_increment: Incremento de AF (típico: 0.02)
            af_max: AF máximo (típico: 0.20)
        """
        self.af_start = af_start
        self.af_increment = af_increment
        self.af_max = af_max

        self.highs = deque(maxlen=100)
        self.lows = deque(maxlen=100)

        self.sar = None
        self.ep = None  # Extreme Point
        self.af = af_start
        self.is_long = True  # Dirección actual

    def _initialize_sar(self):
        """Inicializa SAR con las primeras velas"""
        if len(self.highs) < 2:
            return

        # Determinar dirección inicial
        if self.highs[-1] > self.highs[-2]:
            self.is_long = True
            self.sar = min(self.lows[-2], self.lows[-1])
            self.ep = max(self.highs[-2], self.highs[-1])
        else:
            self.is_long = False
            self.sar = max(self.highs[-2], self.highs[-1])
            self.ep = min(self.lows[-2], self.lows[-1])

        self.af = self.af_start

    def _update_sar(self, high: float, low: float):
        """Actualiza SAR para nueva vela"""
        if self.sar is None:
            return None, None

        prev_sar = self.sar
        prev_is_long = self.is_long

        # Calcular nuevo SAR
        self.sar = prev_sar + self.af * (self.ep - prev_sar)

        # Reversal check
        if self.is_long:
            # En long, SAR no puede estar arriba del low anterior
            self.sar = min(self.sar, self.lows[-1] if len(self.lows) > 0 else low)

            # Check reversal (precio toca SAR)
            if low < self.sar:
                self.is_long = False
                self.sar = self.ep  # SAR salta al EP anterior
                self.ep = low
                self.af = self.af_start
                return "SHORT", self.sar

            # Actualizar EP si nuevo high
            if high > self.ep:
                self.ep = high
                self.af = min(self.af + self.af_increment, self.af_max)

        else:  # Short
            # En short, SAR no puede estar abajo del high anterior
            self.sar = max(self.sar, self.highs[-1] if len(self.highs) > 0 else high)

            # Check reversal (precio toca SAR)
            if high > self.sar:
                self.is_long = True
                self.sar = self.ep  # SAR salta al EP anterior
                self.ep = high
                self.af = self.af_start
                return "LONG", self.sar

            # Actualizar EP si nuevo low
            if low < self.ep:
                self.ep = low
                self.af = min(self.af + self.af_increment, self.af_max)

        return None, self.sar

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        self.highs.append(high)
        self.lows.append(low)

        # Inicializar si es primera vez
        if self.sar is None:
            if len(self.highs) >= 2:
                self._initialize_sar()
            return None

        # Actualizar SAR y detectar reversal
        reversal_side, sar_value = self._update_sar(high, low)

        if reversal_side:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": reversal_side,
                "range_score": 2,
                "features": {"sar": sar_value, "ep": self.ep, "af": self.af, "reversal": True},
            }

        return None
