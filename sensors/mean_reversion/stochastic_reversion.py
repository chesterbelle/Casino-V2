"""
📉 Stochastic Reversion
-----------------------
Detecta condiciones extremas usando el oscilador estocástico.
Similar a RSI pero considera el rango high-low, no solo closes.

Lógica:
- %K < 20 (oversold) → LONG
- %K > 80 (overbought) → SHORT
- Usa smoothing (slow stochastic) para reducir ruido
"""

from __future__ import annotations

import numpy as np
from collections import deque


class StochasticReversion:
    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        low_threshold: float = 20.0,
        high_threshold: float = 80.0
    ):
        """
        Args:
            k_period: Periodo para calcular %K
            d_period: Periodo para suavizar %K → %D
            low_threshold: Nivel oversold (default 20)
            high_threshold: Nivel overbought (default 80)
        """
        self.k_period = k_period
        self.d_period = d_period
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        
        self.highs = deque(maxlen=k_period)
        self.lows = deque(maxlen=k_period)
        self.closes = deque(maxlen=k_period)
        self.k_values = deque(maxlen=d_period)
    
    def _compute_k(self) -> float:
        """Calcula %K = (close - lowest_low) / (highest_high - lowest_low) * 100"""
        if len(self.closes) < self.k_period:
            return 50.0
        
        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        current_close = self.closes[-1]
        
        if highest_high == lowest_low:
            return 50.0
        
        k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        return k
    
    def _compute_d(self) -> float:
        """%D = SMA de %K (slow stochastic)"""
        if len(self.k_values) < self.d_period:
            return 50.0
        return np.mean(self.k_values)
    
    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        # Calcular %K
        k = self._compute_k()
        self.k_values.append(k)
        
        # Calcular %D (suavizado)
        d = self._compute_d()
        
        # Necesitamos datos suficientes
        if len(self.k_values) < self.d_period:
            return None
        
        # Señal LONG: oversold
        if k < self.low_threshold and d < self.low_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "stoch_k": k,
                    "stoch_d": d,
                    "stoch_state": "oversold"
                }
            }
        
        # Señal SHORT: overbought
        if k > self.high_threshold and d > self.high_threshold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "stoch_k": k,
                    "stoch_d": d,
                    "stoch_state": "overbought"
                }
            }
        
        return None
