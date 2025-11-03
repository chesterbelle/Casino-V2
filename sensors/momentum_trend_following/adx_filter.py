"""
📊 ADX Filter (Average Directional Index)
------------------------------------------
NO genera señales de entrada, sino que FILTRA sideways markets.
Esencial para evitar operar cuando no hay tendencia clara.

Lógica:
- ADX > threshold → Tendencia fuerte (permite operar)
- ADX < threshold → Sideways (bloquea otras señales)

Puede usarse solo como filtro o combinado con DI+ / DI- para señales direccionales.

ADX mide la FUERZA de la tendencia (no la dirección):
- ADX < 20 → Sin tendencia (sideways)
- ADX 20-40 → Tendencia moderada
- ADX > 40 → Tendencia fuerte
"""

from __future__ import annotations

from collections import deque

import numpy as np


class ADXFilter:
    def __init__(self, period: int = 14, adx_threshold: float = 25.0, use_directional: bool = True):
        """
        Args:
            period: Periodo para calcular DI+, DI-, ADX
            adx_threshold: Umbral mínimo de ADX para considerar tendencia
            use_directional: Si True, genera señales LONG/SHORT con DI+/DI-
                           Si False, solo valida que hay tendencia (no direccional)
        """
        self.period = period
        self.adx_threshold = adx_threshold
        self.use_directional = use_directional

        self.highs = deque(maxlen=period + 1)
        self.lows = deque(maxlen=period + 1)
        self.closes = deque(maxlen=period + 1)

        self.dx_values = deque(maxlen=period)

    def _compute_dm_tr(self) -> tuple[list, list, list]:
        """
        Calcula +DM, -DM y TR (True Range).

        Returns:
            (plus_dm, minus_dm, tr)
        """
        if len(self.highs) < 2:
            return [], [], []

        plus_dm = []
        minus_dm = []
        tr_values = []

        for i in range(1, len(self.highs)):
            high = self.highs[i]
            low = self.lows[i]
            prev_high = self.highs[i - 1]
            prev_low = self.lows[i - 1]
            prev_close = self.closes[i - 1]

            # +DM y -DM
            up_move = high - prev_high
            down_move = prev_low - low

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
                minus_dm.append(0)
            elif down_move > up_move and down_move > 0:
                plus_dm.append(0)
                minus_dm.append(down_move)
            else:
                plus_dm.append(0)
                minus_dm.append(0)

            # True Range
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        return plus_dm, minus_dm, tr_values

    def _compute_di(self) -> tuple[float, float]:
        """
        Calcula DI+ y DI- (Directional Indicators).

        Returns:
            (di_plus, di_minus)
        """
        plus_dm, minus_dm, tr = self._compute_dm_tr()

        if not tr or len(tr) < self.period:
            return None, None

        # Suavizado de +DM, -DM, TR
        smoothed_plus_dm = np.mean(plus_dm[-self.period :])
        smoothed_minus_dm = np.mean(minus_dm[-self.period :])
        smoothed_tr = np.mean(tr[-self.period :])

        if smoothed_tr == 0:
            return None, None

        # DI+ y DI-
        di_plus = (smoothed_plus_dm / smoothed_tr) * 100
        di_minus = (smoothed_minus_dm / smoothed_tr) * 100

        return di_plus, di_minus

    def _compute_adx(self, di_plus: float, di_minus: float) -> float:
        """
        Calcula ADX (Average Directional Index).

        ADX = suavizado de DX
        DX = |DI+ - DI-| / (DI+ + DI-) * 100
        """
        if di_plus is None or di_minus is None:
            return None

        di_sum = di_plus + di_minus
        if di_sum == 0:
            return 0.0

        dx = (abs(di_plus - di_minus) / di_sum) * 100
        self.dx_values.append(dx)

        if len(self.dx_values) < self.period:
            return None

        # ADX = promedio de DX
        adx = np.mean(self.dx_values)
        return adx

    def check_signal(self, candle: dict):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)

        # Calcular DI+ y DI-
        di_plus, di_minus = self._compute_di()
        if di_plus is None or di_minus is None:
            return None

        # Calcular ADX
        adx = self._compute_adx(di_plus, di_minus)
        if adx is None:
            return None

        # Filtrar: solo señal si ADX > threshold (hay tendencia)
        if adx < self.adx_threshold:
            # Sideways market - no operar
            return None

        # Si use_directional=False, no generamos señal direccional
        # (se usa solo como filtro en combinación con otros sensores)
        if not self.use_directional:
            return None

        # Generar señal direccional con DI+/DI-
        # DI+ > DI- → Uptrend → LONG
        # DI- > DI+ → Downtrend → SHORT

        if di_plus > di_minus:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "LONG",
                "range_score": 2,  # Señal fuerte si ADX alto
                "features": {
                    "adx": adx,
                    "di_plus": di_plus,
                    "di_minus": di_minus,
                    "trend_strength": "strong" if adx > 40 else "moderate",
                },
            }
        else:
            return {
                "timestamp": candle.get("timestamp"),
                "symbol": candle.get("symbol", "UNKNOWN"),
                "timeframe": candle.get("timeframe", "UNKNOWN"),
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "adx": adx,
                    "di_plus": di_plus,
                    "di_minus": di_minus,
                    "trend_strength": "strong" if adx > 40 else "moderate",
                },
            }
