"""
📉 Adaptive RSI Scalper
-----------------------
RSI que ajusta dinámicamente sus umbrales basándose en la volatilidad (ATR).
- Baja Volatilidad: Umbrales más estrechos (40/60) para capturar rebotes en rango.
- Alta Volatilidad: Umbrales más amplios (20/80) para evitar falsas señales en tendencias.
"""

from collections import deque

import numpy as np


class AdaptiveRSIScalper:
    def __init__(self, period: int = 14, atr_period: int = 14, base_low: float = 30.0, base_high: float = 70.0):
        self.period = period
        self.atr_period = atr_period
        self.base_low = base_low
        self.base_high = base_high

        self.closes = deque(maxlen=period + 1)
        self.highs = deque(maxlen=atr_period)
        self.lows = deque(maxlen=atr_period)
        self.close_history_atr = deque(maxlen=atr_period + 1)  # Para ATR necesitamos closes previos

        # Historial de ganancias y pérdidas para RSI
        self.gains = deque(maxlen=period)
        self.losses = deque(maxlen=period)

    def _calculate_rsi(self, current_close: float) -> float:
        if len(self.closes) < 2:
            return 50.0

        delta = current_close - self.closes[-2]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))

        self.gains.append(gain)
        self.losses.append(loss)

        if len(self.gains) < self.period:
            return 50.0

        avg_gain = np.mean(self.gains)
        avg_loss = np.mean(self.losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_atr(self) -> float:
        if len(self.highs) < self.atr_period:
            return 0.0

        tr_values = []
        for i in range(len(self.highs)):
            # TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
            # Simplificación: Usamos high-low promedio si no tenemos prev_close alineado perfectamente
            # Para precisión real necesitaríamos iterar sincronizados.
            # Asumiremos High-Low como proxy rápido para volatilidad en scalping
            tr = self.highs[i] - self.lows[i]
            tr_values.append(tr)

        return np.mean(tr_values)

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        self.close_history_atr.append(close)

        if len(self.closes) < self.period:
            return None

        rsi = self._calculate_rsi(close)
        atr = self._calculate_atr()

        # Lógica Adaptativa
        # Si ATR es bajo (mercado quieto), estrechamos bandas.
        # Si ATR es alto (mercado movido), ampliamos bandas.
        # Umbral dinámico simple:
        # Normalizamos ATR respecto al precio (ATR %)
        atr_pct = (atr / close) * 100 if close > 0 else 0

        # Ajuste: Si ATR% < 0.1% (muy bajo), bandas 40/60
        # Si ATR% > 0.3% (alto), bandas 20/80
        # Interpolación lineal o escalones

        current_low = self.base_low
        current_high = self.base_high

        if atr_pct < 0.1:  # Baja volatilidad
            current_low = 40
            current_high = 60
        elif atr_pct > 0.3:  # Alta volatilidad
            current_low = 20
            current_high = 80

        # Señales
        if rsi < current_low:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "rsi": rsi,
                    "atr_pct": atr_pct,
                    "threshold_low": current_low,
                    "state": "oversold_adaptive",
                },
            }

        if rsi > current_high:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "rsi": rsi,
                    "atr_pct": atr_pct,
                    "threshold_high": current_high,
                    "state": "overbought_adaptive",
                },
            }

        return None
