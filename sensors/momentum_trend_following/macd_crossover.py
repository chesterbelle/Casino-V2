"""Sensor Momentum / Trend-Following basado en cruces de MACD."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


def _compute_ema(previous: Optional[float], value: float, period: int, seed: List[float]) -> float:
    """EMA incremental; usa promedio simple como semilla."""
    if previous is None:
        if not seed:
            return value
        if len(seed) < period:
            return sum(seed) / len(seed)
        return sum(seed[-period:]) / period

    k = 2 / (period + 1)
    return value * k + previous * (1 - k)


@dataclass
class MACDCrossover:
    short_period: int = 12
    long_period: int = 26
    signal_period: int = 9

    def __post_init__(self) -> None:
        if self.short_period >= self.long_period:
            raise ValueError("short_period debe ser menor que long_period")

        self.closes: List[float] = []
        self._ema_short: Optional[float] = None
        self._ema_long: Optional[float] = None
        self._macd: Optional[float] = None
        self._signal: Optional[float] = None
        self._prev_hist: Optional[float] = None
        self._macd_values: List[float] = []

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        self.closes.append(close)

        if len(self.closes) < self.long_period:
            return None

        ema_short = _compute_ema(self._ema_short, close, self.short_period, self.closes)
        ema_long = _compute_ema(self._ema_long, close, self.long_period, self.closes)
        macd_line = ema_short - ema_long
        if self._signal is None and len(self.closes) < self.long_period + self.signal_period:
            # No hay datos suficientes para el signal aún
            macd_line = ema_short - ema_long
            self._ema_short = ema_short
            self._ema_long = ema_long
            self._macd = macd_line
            return None

        self._macd_values.append(macd_line)
        signal_line = _compute_ema(self._signal, macd_line, self.signal_period, self._macd_values)
        histogram = macd_line - signal_line

        side = None
        if self._prev_hist is not None:
            if histogram > 0 and self._prev_hist <= 0:
                side = "LONG"
            elif histogram < 0 and self._prev_hist >= 0:
                side = "SHORT"

        self._ema_short = ema_short
        self._ema_long = ema_long
        self._macd = macd_line
        self._signal = signal_line
        self._prev_hist = histogram

        if side is None:
            return None

        features = {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
            "ema_short": ema_short,
            "ema_long": ema_long,
        }

        return {
            "timestamp": candle["timestamp"],
            "symbol": candle.get("symbol", "UNKNOWN"),
            "side": side,
            "range_score": 1,
            "features": features,
        }
