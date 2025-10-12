"""Sensor Momentum / Trend-Following: Cruce de medias exponenciales (EMA)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


def _compute_ema(previous: Optional[float], close: float, period: int, seed_values: List[float]) -> float:
    """Calcula EMA incrementalmente. Usa media simple si no hay EMA previa."""

    if previous is None:
        if len(seed_values) < period:
            return sum(seed_values) / len(seed_values)
        return sum(seed_values[-period:]) / period

    k = 2 / (period + 1)
    return close * k + previous * (1 - k)


def _compute_adx(highs: List[float], lows: List[float], closes: List[float], period: int) -> Optional[float]:
    """Calcula ADX aproximado usando los últimos `period` valores."""

    if len(highs) < period + 1:
        return None

    trs: List[float] = []
    plus_dm: List[float] = []
    minus_dm: List[float] = []

    start = len(highs) - period
    for idx in range(start, len(highs)):
        if idx == 0:
            continue
        hi, lo, close = highs[idx], lows[idx], closes[idx]
        prev_hi, prev_lo, prev_close = highs[idx - 1], lows[idx - 1], closes[idx - 1]

        up_move = hi - prev_hi
        down_move = prev_lo - lo

        plus = up_move if up_move > down_move and up_move > 0 else 0.0
        minus = down_move if down_move > up_move and down_move > 0 else 0.0
        tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))

        trs.append(tr)
        plus_dm.append(plus)
        minus_dm.append(minus)

    sum_tr = sum(trs)
    if sum_tr <= 0:
        return 0.0

    plus_di = 100 * sum(plus_dm) / sum_tr
    minus_di = 100 * sum(minus_dm) / sum_tr
    denominator = plus_di + minus_di
    if denominator <= 0:
        return 0.0

    dx = abs(plus_di - minus_di) / denominator * 100
    return dx


@dataclass
class EMACrossover:
    short_period: int = 12
    long_period: int = 26
    adx_period: int = 14
    adx_threshold: float = 20.0

    def __post_init__(self) -> None:
        if self.short_period >= self.long_period:
            raise ValueError("short_period debe ser menor que long_period")

        self.closes: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []

        self._short_ema: Optional[float] = None
        self._long_ema: Optional[float] = None
        self._prev_diff: Optional[float] = None

    def check_signal(self, candle: dict) -> Optional[dict]:
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        if len(self.closes) < self.long_period:
            return None

        prev_diff = self._prev_diff

        short_ema = _compute_ema(self._short_ema, close, self.short_period, self.closes)
        long_ema = _compute_ema(self._long_ema, close, self.long_period, self.closes)

        diff = short_ema - long_ema

        adx = _compute_adx(self.highs, self.lows, self.closes, self.adx_period)

        self._short_ema = short_ema
        self._long_ema = long_ema
        self._prev_diff = diff

        if adx is None or adx < self.adx_threshold:
            return None

        side: Optional[str] = None
        if prev_diff is not None:
            if diff > 0 and prev_diff <= 0:
                side = "LONG"
            elif diff < 0 and prev_diff >= 0:
                side = "SHORT"

        if side is None:
            return None

        distance = abs(diff) / close if close else 0.0

        features = {
            "ema_short": short_ema,
            "ema_long": long_ema,
            "distance_ema": distance,
            "adx": adx,
        }

        return {
            "timestamp": candle["timestamp"],
            "symbol": candle.get("symbol", "UNKNOWN"),
            "side": side,
            "range_score": 1,
            "features": features,
        }
