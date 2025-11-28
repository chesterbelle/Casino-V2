from collections import deque
from typing import Dict, Optional

import numpy as np


class VolumeSpikeReversal:
    """Detects a reversal candle with a significant volume spike.

    The sensor looks at a short-term trend (average close of the last N candles).
    If the current candle moves opposite to that trend, has a body larger than
    `min_body_pct` of its range, and its volume exceeds the recent average
    volume by `volume_multiplier`, a signal is emitted.
    """

    def __init__(
        self,
        volume_multiplier: float = 3.0,
        min_body_pct: float = 0.004,
        trend_lookback: int = 5,
        buffer_size: int = 20,
    ):
        self.volume_multiplier = volume_multiplier
        self.min_body_pct = min_body_pct
        self.trend_lookback = trend_lookback
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 5) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.trend_lookback + 1:
            return None
        # recent trend based on closes excluding current candle
        recent_closes = candles[-(self.trend_lookback + 1) : -1, 4]
        trend = np.mean(recent_closes)
        # current candle
        cur = candles[-1]
        open_price, high, low, close, volume = cur[1], cur[2], cur[3], cur[4], cur[5]
        body = abs(close - open_price)
        range_ = high - low if high != low else 1e-9
        body_pct = body / range_
        # average volume of lookback period
        avg_vol = np.mean(candles[-(self.trend_lookback + 1) : -1, 5])
        # Determine direction opposite to trend
        direction = "LONG" if close > open_price else "SHORT"
        opposite = (trend > close and direction == "SHORT") or (trend < close and direction == "LONG")
        if opposite and body_pct >= self.min_body_pct and volume > avg_vol * self.volume_multiplier:
            return {
                "side": direction,
                "features": {"volume_multiplier": self.volume_multiplier, "body_pct": body_pct, "trend": float(trend)},
            }
        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Wrapper called by SensorManager. Adds candle to buffer and runs detection."""
        # Expected candle dict keys: timestamp, open, high, low, close, volume, symbol, timeframe
        self.candle_buffer.append(
            [
                candle.get("timestamp"),
                float(candle["open"]),
                float(candle["high"]),
                float(candle["low"]),
                float(candle["close"]),
                float(candle.get("volume", 0)),
            ]
        )
        if len(self.candle_buffer) < self.trend_lookback + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
