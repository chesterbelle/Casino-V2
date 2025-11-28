"""
🌋 Volatility Wakeup
--------------------
Estrategia de Breakout.
Detecta cuando el mercado "despierta" de un periodo de baja volatilidad (Squeeze).
Señal: Rompimiento de Bandas de Bollinger con Volumen Climático.
"""

from collections import deque

import numpy as np


class VolatilityWakeup:
    def __init__(
        self, bb_window: int = 20, bb_std: float = 2.0, squeeze_threshold: float = 0.05, volume_factor: float = 1.5
    ):
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.squeeze_threshold = squeeze_threshold  # BBW debe ser menor a esto para considerar "Squeeze"
        self.volume_factor = volume_factor  # Volumen actual debe ser X veces el promedio

        self.closes = deque(maxlen=bb_window)
        self.volumes = deque(maxlen=bb_window)

        self.in_squeeze = False
        self.squeeze_duration = 0

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        volume = float(candle["volume"])

        self.closes.append(close)
        self.volumes.append(volume)

        if len(self.closes) < self.bb_window:
            return None

        # 1. Calcular Bandas y BBW
        sma = np.mean(self.closes)
        std = np.std(self.closes)
        upper = sma + (std * self.bb_std)
        lower = sma - (std * self.bb_std)

        bbw = (upper - lower) / sma

        # 2. Detectar Estado de Squeeze (Compresión)
        if bbw < self.squeeze_threshold:
            self.in_squeeze = True
            self.squeeze_duration += 1
            return None  # Mientras estamos comprimiendo, esperamos
        else:
            # Si salimos del squeeze, verificamos si es un breakout válido
            was_in_squeeze = self.in_squeeze
            self.in_squeeze = False

            if not was_in_squeeze or self.squeeze_duration < 5:
                # Si no veníamos de un squeeze real (al menos 5 velas), ignoramos
                self.squeeze_duration = 0
                return None

            # 3. Validar Breakout con Volumen
            avg_volume = np.mean(self.volumes)
            if volume < avg_volume * self.volume_factor:
                # Rompimiento sin volumen = Falso Breakout
                self.squeeze_duration = 0
                return None

            # 4. Señal de Breakout
            # Rompimiento Alcista
            if close > upper:
                self.squeeze_duration = 0
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "LONG",
                    "range_score": 2,  # Breakouts suelen ser explosivos
                    "features": {"bbw": bbw, "volume_ratio": volume / avg_volume, "regime": "breakout"},
                }

            # Rompimiento Bajista
            if close < lower:
                self.squeeze_duration = 0
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "SHORT",
                    "range_score": 2,
                    "features": {"bbw": bbw, "volume_ratio": volume / avg_volume, "regime": "breakout"},
                }

            self.squeeze_duration = 0
            return None
