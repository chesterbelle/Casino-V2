"""
🌪️ Keltner Channel Breakout
---------------------------
Estrategia de Volatilidad usando ATR.
A diferencia de Bollinger (Desviación Estándar), Keltner usa ATR, lo que filtra mejor el ruido.
Señal: Rompimiento del canal con confirmación de tendencia (ADX).
"""

from collections import deque

import numpy as np


class KeltnerBreakout:
    def __init__(
        self, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0, adx_threshold: float = 20.0
    ):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.adx_threshold = adx_threshold

        self.closes = deque(maxlen=max(ema_period, atr_period * 2))
        self.highs = deque(maxlen=atr_period * 2)
        self.lows = deque(maxlen=atr_period * 2)

        # ADX State
        self.prev_tr = None
        self.prev_dm_plus = None
        self.prev_dm_minus = None
        self.prev_adx = None

        # EMA State
        self.ema_val = None

    def _calculate_adx(self, high, low, close) -> float:
        # (Reusing simplified ADX logic)
        if len(self.closes) < 2:
            return 0.0
        prev_close = self.closes[-2]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        up_move = high - self.highs[-2]
        down_move = self.lows[-2] - low
        dm_plus = up_move if up_move > down_move and up_move > 0 else 0
        dm_minus = down_move if down_move > up_move and down_move > 0 else 0

        if self.prev_tr is None:
            self.prev_tr = tr
            self.prev_dm_plus = dm_plus
            self.prev_dm_minus = dm_minus
            return 0.0

        alpha = 1.0 / 14  # Hardcoded 14 for ADX standard
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

    def _update_ema(self, close):
        k = 2 / (self.ema_period + 1)
        if self.ema_val is None:
            self.ema_val = close
        else:
            self.ema_val = (close * k) + (self.ema_val * (1 - k))

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.closes) < self.ema_period:
            self._update_ema(close)
            return None

        # 1. Calcular Indicadores
        adx = self._calculate_adx(high, low, close)
        self._update_ema(close)

        # Calcular ATR (Simple average of TR for last N periods)
        # Necesitamos iterar para calcular TRs recientes
        tr_values = []
        c_list = list(self.closes)
        h_list = list(self.highs)
        l_list = list(self.lows)

        start_idx = len(c_list) - self.atr_period
        if start_idx < 1:
            return None

        for i in range(start_idx, len(c_list)):
            prev_c = c_list[i - 1]
            h = h_list[i]
            low_val = l_list[i]
            tr = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))
            tr_values.append(tr)

        atr = np.mean(tr_values)

        # 2. Calcular Canales Keltner
        upper = self.ema_val + (atr * self.multiplier)
        lower = self.ema_val - (atr * self.multiplier)

        # 3. Señal de Breakout
        # Solo si hay fuerza de tendencia (ADX > Threshold)
        if adx < self.adx_threshold:
            return None

        # Breakout Alcista
        if close > upper:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "LONG",
                "range_score": 2,
                "features": {"adx": adx, "breakout_type": "keltner_upper"},
            }

        # Breakout Bajista
        if close < lower:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "SHORT",
                "range_score": 2,
                "features": {"adx": adx, "breakout_type": "keltner_lower"},
            }

        return None
