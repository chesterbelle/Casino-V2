"""
📉 Z-Score Mean Reversion
--------------------------
Mide cuántas desviaciones estándar está el precio de su media.
Muy efectivo para detectar extremos estadísticos.

Lógica:
- Z-Score > +2.0 → Precio muy alto → SHORT
- Z-Score < -2.0 → Precio muy bajo → LONG

Fórmula:
Z = (Precio - Media) / Desviación Estándar

Ventaja sobre otros:
- Normalizado estadísticamente
- Adaptativo a la volatilidad
- Menos falsos positivos
"""

from __future__ import annotations

import numpy as np
from collections import deque


class ZScoreReversion:
    def __init__(
        self,
        period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ):
        """
        Args:
            period: Periodo para calcular media y std
            entry_threshold: Z-score mínimo para señal (típico: 2.0)
            exit_threshold: Z-score para salir (opcional, futuro)
        """
        self.period = period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        
        self.closes = deque(maxlen=period)
    
    def _compute_zscore(self) -> float:
        """Calcula Z-Score del precio actual"""
        if len(self.closes) < self.period:
            return 0.0
        
        closes_array = np.array(self.closes)
        
        mean = np.mean(closes_array)
        std = np.std(closes_array)
        
        if std == 0:
            return 0.0
        
        current_price = self.closes[-1]
        zscore = (current_price - mean) / std
        
        return zscore
    
    def check_signal(self, candle: dict):
        close = float(candle["close"])
        
        self.closes.append(close)
        
        if len(self.closes) < self.period:
            return None
        
        zscore = self._compute_zscore()
        
        # Z-score muy negativo → Precio bajo → LONG
        if zscore < -self.entry_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": int(abs(zscore)),  # Más extremo = más score
                "features": {
                    "zscore": zscore,
                    "std_devs": abs(zscore),
                    "state": "extreme_low"
                }
            }
        
        # Z-score muy positivo → Precio alto → SHORT
        if zscore > self.entry_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": int(abs(zscore)),
                "features": {
                    "zscore": zscore,
                    "std_devs": abs(zscore),
                    "state": "extreme_high"
                }
            }
        
        return None
