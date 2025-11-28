"""
📊 VSA Reversal (Lite)
----------------------
Volume Spread Analysis simplificado.
Detecta absorción institucional: Alto Volumen + Vela Pequeña (Spread bajo) = Giro inminente.
"""

from collections import deque

import numpy as np


class VSAReversal:
    def __init__(self, volume_period: int = 50, volume_threshold_pct: float = 90.0, spread_threshold_pct: float = 20.0):
        self.volume_period = volume_period
        self.volume_threshold_pct = volume_threshold_pct  # Percentil de volumen (ej: Top 10%)
        self.spread_threshold_pct = spread_threshold_pct  # Spread relativo al rango promedio

        self.volumes = deque(maxlen=volume_period)
        self.highs = deque(maxlen=volume_period)
        self.lows = deque(maxlen=volume_period)

    def check_signal(self, candle: dict):
        volume = float(candle["volume"])
        high = float(candle["high"])
        low = float(candle["low"])
        open_p = float(candle["open"])
        close = float(candle["close"])

        self.volumes.append(volume)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.volumes) < self.volume_period:
            return None

        # 1. Análisis de Volumen
        # ¿Es un volumen ultra alto? (Climático)
        vol_percentile = np.percentile(self.volumes, self.volume_threshold_pct)
        if volume < vol_percentile:
            return None  # No hay esfuerzo institucional suficiente

        # 2. Análisis de Spread (Cuerpo de la vela)
        # Spread = abs(close - open)
        # Range = high - low
        spread = abs(close - open_p)
        candle_range = high - low

        if candle_range == 0:
            return None

        spread_ratio = (spread / candle_range) * 100

        # Señal: Volumen Alto + Spread Pequeño (< 20% del rango)
        # Significa mucha lucha pero poco avance -> Absorción
        if spread_ratio > self.spread_threshold_pct:
            return None  # El precio avanzó libremente, no es absorción

        # 3. Dirección del Giro
        # Si la vela tiene mecha superior larga -> Absorción de compras (Bearish)
        # Si la vela tiene mecha inferior larga -> Absorción de ventas (Bullish)

        upper_wick = high - max(open_p, close)
        lower_wick = min(open_p, close) - low

        signal = None

        # Giro Alcista (Hammer / Pinbar alcista)
        # Mecha inferior domina
        if lower_wick > upper_wick and lower_wick > spread:
            signal = {"side": "LONG", "type": "stopping_volume_bullish"}

        # Giro Bajista (Shooting Star / Pinbar bajista)
        # Mecha superior domina
        if upper_wick > lower_wick and upper_wick > spread:
            signal = {"side": "SHORT", "type": "stopping_volume_bearish"}

        if signal:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": signal["side"],
                "range_score": 2,  # Señal fuerte de volumen
                "features": {
                    "volume_ratio": volume / np.mean(self.volumes),
                    "spread_ratio": spread_ratio,
                    "vsa_type": signal["type"],
                },
            }

        return None
