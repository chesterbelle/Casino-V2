"""
💥 Bollinger Squeeze (Volatility Breakout)
-------------------------------------------
Detecta periodos de baja volatilidad (squeeze) seguidos de expansión.
Muy efectivo para capturar movimientos explosivos después de consolidación.

Lógica:
1. Squeeze: Bollinger Bands muy estrechas (BBW < threshold)
2. Breakout: Precio rompe banda superior/inferior con expansión

Fases:
- Compresión (squeeze): BBW bajo → Esperar
- Expansión (breakout): Precio + volumen → Señal

BBW (Bollinger Band Width) = (Upper - Lower) / Middle
"""

from __future__ import annotations

from collections import deque

import numpy as np


class BollingerSqueeze:
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        squeeze_threshold: float = 0.02,  # BBW < 2% = squeeze
        volume_factor: float = 1.2,  # Volumen > 1.2x promedio
    ):
        """
        Args:
            period: Periodo para Bollinger Bands
            std_dev: Desviaciones estándar (típico: 2)
            squeeze_threshold: BBW mínimo para considerar squeeze
            volume_factor: Multiplicador de volumen para confirmar breakout
        """
        self.period = period
        self.std_dev = std_dev
        self.squeeze_threshold = squeeze_threshold
        self.volume_factor = volume_factor

        self.closes = deque(maxlen=period)
        self.volumes = deque(maxlen=period)

        self.in_squeeze = False
        self.last_bbw = None

    def _compute_bollinger(self) -> tuple[float, float, float, float]:
        """
        Calcula Bollinger Bands.

        Returns:
            (middle, upper, lower, bbw)
        """
        if len(self.closes) < self.period:
            return None, None, None, None

        closes_array = np.array(self.closes)

        middle = np.mean(closes_array)
        std = np.std(closes_array)

        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)

        # BBW (Bandwidth)
        if middle > 0:
            bbw = (upper - lower) / middle
        else:
            bbw = 0.0

        return middle, upper, lower, bbw

    def _check_squeeze(self, bbw: float) -> bool:
        """Detecta si estamos en squeeze (baja volatilidad)"""
        return bbw < self.squeeze_threshold

    def _check_volume_spike(self) -> bool:
        """Confirma con volumen elevado"""
        if len(self.volumes) < self.period:
            return False

        avg_volume = np.mean(list(self.volumes)[:-1])  # Promedio sin última vela
        current_volume = self.volumes[-1]

        return current_volume > (avg_volume * self.volume_factor)

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        volume = float(candle.get("volume", 0))

        self.closes.append(close)
        self.volumes.append(volume)

        # Calcular Bollinger Bands
        middle, upper, lower, bbw = self._compute_bollinger()

        if middle is None:
            return None

        # Detectar squeeze
        is_squeezed = self._check_squeeze(bbw)

        # Actualizar estado de squeeze
        if is_squeezed:
            self.in_squeeze = True
            self.last_bbw = bbw
            return None  # Esperando breakout

        # Si NO estamos en squeeze, no hay señal
        if not self.in_squeeze:
            self.last_bbw = bbw
            return None

        # Estábamos en squeeze y ahora hay expansión → Buscar breakout
        has_volume_spike = self._check_volume_spike()

        signal = None

        # Breakout alcista: precio > banda superior
        if close > upper:
            if has_volume_spike:
                signal = {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol", "UNKNOWN"),
                    "timeframe": candle.get("timeframe", "UNKNOWN"),
                    "side": "LONG",
                    "range_score": 3,  # Señal muy fuerte
                    "features": {
                        "bbw": bbw,
                        "bb_upper": upper,
                        "bb_lower": lower,
                        "bb_middle": middle,
                        "breakout": "bullish",
                        "volume_spike": True,
                        "squeeze_exit": True,
                    },
                }
            # Reset squeeze
            self.in_squeeze = False

        # Breakout bajista: precio < banda inferior
        elif close < lower:
            if has_volume_spike:
                signal = {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol", "UNKNOWN"),
                    "timeframe": candle.get("timeframe", "UNKNOWN"),
                    "side": "SHORT",
                    "range_score": 3,
                    "features": {
                        "bbw": bbw,
                        "bb_upper": upper,
                        "bb_lower": lower,
                        "bb_middle": middle,
                        "breakout": "bearish",
                        "volume_spike": True,
                        "squeeze_exit": True,
                    },
                }
            # Reset squeeze
            self.in_squeeze = False

        self.last_bbw = bbw
        return signal
