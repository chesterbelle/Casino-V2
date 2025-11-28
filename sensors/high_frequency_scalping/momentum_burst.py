"""
🚀 Momentum Burst
-----------------
Detecta aceleraciones repentinas en el precio midiendo cambios bruscos en el RSI en una sola vela.
Ideal para scalping de momentum: entrar cuando el movimiento explota.
"""

from collections import deque

import numpy as np


class MomentumBurst:
    def __init__(self, rsi_period: int = 14, burst_threshold: float = 15.0):
        self.rsi_period = rsi_period
        self.burst_threshold = burst_threshold

        self.closes = deque(maxlen=rsi_period + 1)
        self.gains = deque(maxlen=rsi_period)
        self.losses = deque(maxlen=rsi_period)

        self.prev_rsi = None

    def _calculate_rsi(self, current_close: float) -> float:
        if len(self.closes) < 2:
            return 50.0

        delta = current_close - self.closes[-2]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))

        self.gains.append(gain)
        self.losses.append(loss)

        if len(self.gains) < self.rsi_period:
            return 50.0

        avg_gain = np.mean(self.gains)
        avg_loss = np.mean(self.losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        self.closes.append(close)

        if len(self.closes) < self.rsi_period:
            return None

        current_rsi = self._calculate_rsi(close)

        if self.prev_rsi is None:
            self.prev_rsi = current_rsi
            return None

        # Calcular el cambio de RSI en esta vela
        rsi_delta = current_rsi - self.prev_rsi
        self.prev_rsi = current_rsi

        # Lógica de Burst
        # Si RSI salta mucho hacia arriba (> 15 puntos)
        if abs(rsi_delta) > self.burst_threshold:

            # Caso LONG: RSI estaba bajo (< 50) y explota hacia arriba
            # Significa inicio de rebote fuerte
            if rsi_delta > 0 and current_rsi < 60:  # < 60 para dar margen
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "LONG",
                    "range_score": 2,  # Señal fuerte
                    "features": {"rsi": current_rsi, "rsi_delta": rsi_delta, "type": "bullish_burst"},
                }

            # Caso SHORT: RSI estaba alto (> 50) y explota hacia abajo
            # Significa inicio de caída fuerte
            if rsi_delta < 0 and current_rsi > 40:  # > 40 para dar margen
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "SHORT",
                    "range_score": 2,  # Señal fuerte
                    "features": {"rsi": current_rsi, "rsi_delta": rsi_delta, "type": "bearish_burst"},
                }

            # Opcional: Blow-off top (RSI ya estaba muy alto y sube más -> Exhaustion)
            # Por ahora nos quedamos con la inercia inicial.

        return None
