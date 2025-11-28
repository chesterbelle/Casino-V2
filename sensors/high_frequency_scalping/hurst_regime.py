"""
🌀 Hurst Regime Filter (Chaos Theory)
-------------------------------------
Usa el Exponente de Hurst (H) para clasificar científicamente el mercado.
- H < 0.5: Mean Reverting (Rango/Ruido) -> Activa estrategias de reversión.
- H > 0.5: Trending (Persistencia) -> Activa estrategias de tendencia.
- H ~ 0.5: Random Walk (Impredecible) -> No operar.
"""

from collections import deque

import numpy as np


class HurstRegime:
    def __init__(self, window_size: int = 100, threshold_reversion: float = 0.45, threshold_trend: float = 0.55):
        self.window_size = window_size
        self.threshold_reversion = threshold_reversion
        self.threshold_trend = threshold_trend

        self.closes = deque(maxlen=window_size)

    def _calculate_hurst(self, series):
        """
        Calcula el Exponente de Hurst simplificado usando R/S Analysis.
        """
        series = np.array(series)
        if len(series) < 20:
            return 0.5

        # Crear rango de lags (tau)
        lags = range(2, 20)
        tau = []
        lagvec = []

        # Calcular varianza de diferencias para cada lag
        for lag in lags:
            # Price difference (returns)
            pp = np.subtract(series[lag:], series[:-lag])
            lagvec.append(lag)
            tau.append(np.std(pp))

        # Regresión lineal de log(tau) vs log(lag)
        # H es la pendiente
        try:
            m = np.polyfit(np.log(lagvec), np.log(tau), 1)
            hurst = m[0]
            return hurst
        except Exception:
            return 0.5

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        self.closes.append(close)

        if len(self.closes) < self.window_size:
            return None

        # Calcular Hurst
        h = self._calculate_hurst(list(self.closes))

        # Interpretar Régimen
        regime = "random"
        if h < self.threshold_reversion:
            regime = "mean_reverting"
        elif h > self.threshold_trend:
            regime = "trending"

        # Este sensor actúa más como un "Filtro Maestro" o generador de contexto
        # Pero para encajar en la arquitectura actual, emitirá señales de "Confirmación de Régimen"
        # que pueden usarse para ponderar otras señales.

        # Por ahora, emitiremos una señal "neutra" informativa o direccional si hay momentum fuerte
        # Para simplificar: Si es Trending (H > 0.55), miramos la tendencia reciente.

        if regime == "trending":
            # Tendencia Alcista o Bajista?
            # Miramos retorno simple de la ventana
            ret = self.closes[-1] - self.closes[0]
            side = "LONG" if ret > 0 else "SHORT"

            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": side,
                "range_score": 1,
                "features": {"hurst": h, "regime": "trending", "trend_strength": abs(ret)},
            }

        # Si es Mean Reverting, podríamos emitir señal contraria a la vela actual (scalping puro)
        # Pero es arriesgado sin más filtros. Lo dejaremos como detector de tendencia por ahora.

        return None
