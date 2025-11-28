"""
📈 Micro Trend Pullback
-----------------------
Estrategia especializada en mercados con tendencia (Trend).
Solo opera cuando hay tendencia definida (ADX alto) y las EMAs están alineadas.
Compra retrocesos (Pullbacks) a la media (EMA20).
"""

from collections import deque


class MicroTrendPullback:
    def __init__(self, adx_period: int = 14, adx_threshold: float = 25.0, ema_fast: int = 9, ema_slow: int = 20):
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.ema_fast_period = ema_fast
        self.ema_slow_period = ema_slow

        self.closes = deque(maxlen=max(adx_period * 2, ema_slow * 2))
        self.highs = deque(maxlen=adx_period * 2)
        self.lows = deque(maxlen=adx_period * 2)

        # State
        self.prev_tr = None
        self.prev_dm_plus = None
        self.prev_dm_minus = None
        self.prev_adx = None
        self.ema_fast_val = None
        self.ema_slow_val = None

    def _calculate_adx(self, high, low, close) -> float:
        # (Reusing simplified ADX logic - ideally this should be a shared utility)
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

    def _update_emas(self, close):
        k_fast = 2 / (self.ema_fast_period + 1)
        k_slow = 2 / (self.ema_slow_period + 1)

        if self.ema_fast_val is None:
            self.ema_fast_val = close
            self.ema_slow_val = close
        else:
            self.ema_fast_val = (close * k_fast) + (self.ema_fast_val * (1 - k_fast))
            self.ema_slow_val = (close * k_slow) + (self.ema_slow_val * (1 - k_slow))

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.closes) < self.ema_slow_period:
            self._update_emas(close)
            return None

        # 1. Actualizar Indicadores
        adx = self._calculate_adx(high, low, close)
        self._update_emas(close)

        # 2. Filtro de Régimen: Tendencia Fuerte
        if adx < self.adx_threshold:
            return None  # Mercado lateral, no operar pullbacks aquí

        # 3. Lógica de Pullback

        # TENDENCIA ALCISTA (EMA9 > EMA20)
        if self.ema_fast_val > self.ema_slow_val:
            # Precio retrocede a la EMA20 (zona de valor)
            # Low toca o perfora EMA20, pero Close se mantiene cerca o encima
            if low <= self.ema_slow_val:
                # Confirmación: El precio no se ha desplomado (Close > EMA20 * 0.995)
                # Y la vela es alcista o de rechazo (Close > Open o Close > Low + rango/3)
                if close > self.ema_slow_val * 0.998:
                    return {
                        "timestamp": candle.get("timestamp"),
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                        "side": "LONG",
                        "range_score": 2,  # Alta probabilidad en tendencia
                        "features": {"adx": adx, "pullback_to": "ema20", "regime": "trending_bullish"},
                    }

        # TENDENCIA BAJISTA (EMA9 < EMA20)
        if self.ema_fast_val < self.ema_slow_val:
            # Precio sube a la EMA20
            if high >= self.ema_slow_val:
                if close < self.ema_slow_val * 1.002:
                    return {
                        "timestamp": candle.get("timestamp"),
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                        "side": "SHORT",
                        "range_score": 2,
                        "features": {"adx": adx, "pullback_to": "ema20", "regime": "trending_bearish"},
                    }

        return None
