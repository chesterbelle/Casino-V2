"""Sensor de Volumen y Flujo de Capital basado en OBV."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OBVBreakout:
    short_period: int = 20
    long_period: int = 50

    def __post_init__(self) -> None:
        if self.short_period >= self.long_period:
            raise ValueError("short_period debe ser menor que long_period")

        self.closes: List[float] = []
        self.volumes: List[float] = []
        self._obv_values: List[float] = []
        self._prev_diff: Optional[float] = None

    def _compute_ma(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        window = values[-period:]
        return sum(window) / period

    def check_signal(self, candle: dict):
        close = float(candle["close"])
        volume = float(candle.get("volume", 0.0))

        self.closes.append(close)
        self.volumes.append(volume)

        if not self._obv_values:
            obv = volume
        else:
            prev_close = self.closes[-2]
            prev_obv = self._obv_values[-1]
            if close > prev_close:
                obv = prev_obv + volume
            elif close < prev_close:
                obv = prev_obv - volume
            else:
                obv = prev_obv

        self._obv_values.append(obv)

        ma_short = self._compute_ma(self._obv_values, self.short_period)
        ma_long = self._compute_ma(self._obv_values, self.long_period)

        if ma_short is None or ma_long is None:
            return None

        diff = ma_short - ma_long
        side = None
        if self._prev_diff is not None:
            if diff > 0 and self._prev_diff <= 0:
                side = "LONG"
            elif diff < 0 and self._prev_diff >= 0:
                side = "SHORT"

        self._prev_diff = diff

        if side is None:
            return None

        features = {
            "obv": obv,
            "ma_short": ma_short,
            "ma_long": ma_long,
            "obv_diff": diff,
        }

        return {
            "timestamp": candle["timestamp"],
            "symbol": candle.get("symbol", "UNKNOWN"),
            "side": side,
            "range_score": 1,
            "features": features,
        }
