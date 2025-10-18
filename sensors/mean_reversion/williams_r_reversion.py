"""
📉 Williams %R Reversion
------------------------
Similar a Stochastic pero invertido (valores negativos).
Oscilador momentum que mide oversold/overbought.

Lógica:
- %R > -20 (muy cerca de high) → Overbought → SHORT
- %R < -80 (muy cerca de low) → Oversold → LONG

Fórmula:
%R = (Highest High - Close) / (Highest High - Lowest Low) * -100
"""

from __future__ import annotations

import numpy as np
from collections import deque


class WilliamsRReversion:
    def __init__(
        self,
        period: int = 14,
        oversold: float = -80.0,
        overbought: float = -20.0
    ):
        """
        Args:
            period: Periodo de lookback
            oversold: Nivel oversold (típico: -80)
            overbought: Nivel overbought (típico: -20)
        """
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        
        self.highs = deque(maxlen=period)
        self.lows = deque(maxlen=period)
        self.closes = deque(maxlen=period)
    
    def _compute_williams_r(self) -> float:
        """Calcula Williams %R"""
        if len(self.closes) < self.period:
            return -50.0
        
        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        current_close = self.closes[-1]
        
        if highest_high == lowest_low:
            return -50.0
        
        williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
        return williams_r
    
    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        if len(self.closes) < self.period:
            return None
        
        williams_r = self._compute_williams_r()
        
        # Oversold → LONG
        if williams_r < self.oversold:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 1,
                "features": {
                    "williams_r": williams_r,
                    "state": "oversold"
                }
            }
        
        # Overbought → SHORT
        if williams_r > self.overbought:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 1,
                "features": {
                    "williams_r": williams_r,
                    "state": "overbought"
                }
            }
        
        return None
