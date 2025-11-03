"""
📈 Supertrend
-------------
Indicador de tendencia basado en ATR que genera señales claras.
Muy popular por su simplicidad y efectividad.

Lógica:
- Precio > Supertrend → LONG (tendencia alcista)
- Precio < Supertrend → SHORT (tendencia bajista)
- Flip de dirección = señal de entrada

El Supertrend se calcula como:
- Upper Band = (High + Low) / 2 + multiplier * ATR
- Lower Band = (High + Low) / 2 - multiplier * ATR
"""

from __future__ import annotations

from collections import deque

import numpy as np


class Supertrend:
    def __init__(self, atr_period: int = 10, multiplier: float = 3.0):
        """
        Args:
            atr_period: Periodo para calcular ATR
            multiplier: Multiplicador del ATR (típico: 2-4)
        """
        self.atr_period = atr_period
        self.multiplier = multiplier

        self.highs = deque(maxlen=atr_period + 1)
        self.lows = deque(maxlen=atr_period + 1)
        self.closes = deque(maxlen=atr_period + 1)

        self.last_supertrend = None
        self.last_direction = None  # 1 = uptrend, -1 = downtrend

    def _compute_atr(self) -> float:
        """Calcula ATR (Average True Range)"""
        if len(self.closes) < 2:
            return 0.0

        tr_values = []
        for i in range(1, len(self.closes)):
            high = self.highs[i]
            low = self.lows[i]
            prev_close = self.closes[i - 1]

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        if not tr_values:
            return 0.0

        return np.mean(tr_values[-self.atr_period :])

    def _compute_supertrend(self) -> tuple[float, int]:
        """
        Calcula Supertrend y dirección.

        Returns:
            (supertrend_value, direction)
            direction: 1 = uptrend, -1 = downtrend
        """
        if len(self.closes) < self.atr_period:
            return None, None

        high = self.highs[-1]
        low = self.lows[-1]
        close = self.closes[-1]

        # Basic price (HL/2)
        hl_avg = (high + low) / 2

        # ATR
        atr = self._compute_atr()
        if atr == 0:
            return None, None

        # Bandas
        upper_band = hl_avg + (self.multiplier * atr)
        lower_band = hl_avg - (self.multiplier * atr)

        # Determinar dirección
        if self.last_supertrend is None or self.last_direction is None:
            # Primera vez: determinar por posición del precio
            if close > upper_band:
                direction = 1
                supertrend = lower_band
            elif close < lower_band:
                direction = -1
                supertrend = upper_band
            else:
                direction = 1
                supertrend = lower_band
        else:
            # Continuación o cambio de tendencia
            if self.last_direction == 1:
                # Estábamos en uptrend
                if close < self.last_supertrend:
                    # Flip a downtrend
                    direction = -1
                    supertrend = upper_band
                else:
                    # Continúa uptrend
                    direction = 1
                    supertrend = max(lower_band, self.last_supertrend)
            else:
                # Estábamos en downtrend
                if close > self.last_supertrend:
                    # Flip a uptrend
                    direction = 1
                    supertrend = lower_band
                else:
                    # Continúa downtrend
                    direction = -1
                    supertrend = min(upper_band, self.last_supertrend)

        return supertrend, direction

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)

        # Calcular Supertrend
        supertrend, direction = self._compute_supertrend()

        if supertrend is None or direction is None:
            return None

        # Detectar FLIP (cambio de dirección)
        signal = None

        if self.last_direction is not None and direction != self.last_direction:
            # Cambio de tendencia = señal
            if direction == 1:
                # Flip a uptrend → LONG
                signal = {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol", "UNKNOWN"),
                    "timeframe": candle.get("timeframe", "UNKNOWN"),
                    "side": "LONG",
                    "range_score": 2,  # Señal fuerte
                    "features": {
                        "supertrend": supertrend,
                        "direction": "uptrend",
                        "atr": self._compute_atr(),
                        "flip": True,
                    },
                }
            else:
                # Flip a downtrend → SHORT
                signal = {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol", "UNKNOWN"),
                    "timeframe": candle.get("timeframe", "UNKNOWN"),
                    "side": "SHORT",
                    "range_score": 2,
                    "features": {
                        "supertrend": supertrend,
                        "direction": "downtrend",
                        "atr": self._compute_atr(),
                        "flip": True,
                    },
                }

        # Actualizar estado
        self.last_supertrend = supertrend
        self.last_direction = direction

        return signal
