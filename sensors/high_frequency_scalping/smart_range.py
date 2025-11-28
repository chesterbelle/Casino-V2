"""
🦀 Smart Range Scalper
----------------------
Estrategia especializada en mercados laterales (Rango).
Solo opera cuando no hay tendencia definida (ADX bajo) y la volatilidad es estable.
Compra en soporte (Banda Inferior) y Vende en resistencia (Banda Superior).
"""

from collections import deque

import numpy as np


class SmartRangeScalper:
    def __init__(self, adx_period: int = 14, adx_threshold: float = 25.0, bb_window: int = 20, bb_std: float = 2.0):
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.bb_window = bb_window
        self.bb_std = bb_std

        # Data buffers
        self.highs = deque(maxlen=adx_period * 2)  # Need more for ADX smoothing
        self.lows = deque(maxlen=adx_period * 2)
        self.closes = deque(maxlen=max(adx_period * 2, bb_window))

        # ADX Calculation state
        self.prev_tr = None
        self.prev_dm_plus = None
        self.prev_dm_minus = None
        self.prev_adx = None

    def _calculate_adx(self, high, low, close) -> float:
        # Simplified ADX calculation for streaming data
        if len(self.closes) < 2:
            return 0.0

        prev_close = self.closes[-2]

        # True Range
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))

        # Directional Movement
        up_move = high - self.highs[-2]
        down_move = self.lows[-2] - low

        dm_plus = up_move if up_move > down_move and up_move > 0 else 0
        dm_minus = down_move if down_move > up_move and down_move > 0 else 0

        # Smoothing (Wilder's Smoothing)
        if self.prev_tr is None:
            self.prev_tr = tr
            self.prev_dm_plus = dm_plus
            self.prev_dm_minus = dm_minus
            return 0.0

        alpha = 1.0 / self.adx_period
        smooth_tr = self.prev_tr * (1 - alpha) + tr
        smooth_dm_plus = self.prev_dm_plus * (1 - alpha) + dm_plus
        smooth_dm_minus = self.prev_dm_minus * (1 - alpha) + dm_minus

        self.prev_tr = smooth_tr
        self.prev_dm_plus = smooth_dm_plus
        self.prev_dm_minus = smooth_dm_minus

        if smooth_tr == 0:
            return 0.0

        di_plus = (smooth_dm_plus / smooth_tr) * 100
        di_minus = (smooth_dm_minus / smooth_tr) * 100

        dx = (abs(di_plus - di_minus) / (di_plus + di_minus)) * 100 if (di_plus + di_minus) > 0 else 0

        if self.prev_adx is None:
            self.prev_adx = dx
            return dx

        adx = self.prev_adx * (1 - alpha) + dx * alpha
        self.prev_adx = adx

        return adx

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.closes) < self.bb_window:
            return None

        # 1. Calcular ADX (Filtro de Tendencia)
        adx = self._calculate_adx(high, low, close)

        # Si hay tendencia fuerte (ADX > Threshold), NO operamos rango.
        # Queremos mercado "aburrido" o lateral.
        if adx > self.adx_threshold:
            return None

        # 2. Calcular Bandas de Bollinger
        closes_slice = list(self.closes)[-self.bb_window :]
        sma = np.mean(closes_slice)
        std = np.std(closes_slice)
        upper = sma + (std * self.bb_std)
        lower = sma - (std * self.bb_std)

        # 3. Señales de Rango
        # Comprar si toca/rompe banda inferior (Soporte)
        if low <= lower:
            # Filtro extra: Que la vela cierre dentro o cerca (rechazo) para no atrapar un crash
            if close > lower:
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "LONG",
                    "range_score": 1,
                    "features": {"adx": adx, "bb_position": "lower_band", "regime": "ranging"},
                }

        # Vender si toca/rompe banda superior (Resistencia)
        if high >= upper:
            if close < upper:
                return {
                    "timestamp": candle.get("timestamp"),
                    "symbol": candle.get("symbol"),
                    "timeframe": candle.get("timeframe"),
                    "side": "SHORT",
                    "range_score": 1,
                    "features": {"adx": adx, "bb_position": "upper_band", "regime": "ranging"},
                }

        return None
