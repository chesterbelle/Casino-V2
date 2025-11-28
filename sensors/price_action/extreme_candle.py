from collections import deque
from typing import Dict, Optional

import numpy as np


class ExtremeCandleRatio:
    """Detects an extreme candle size relative to recent history.

    This sensor tracks the distribution of candle body sizes over a lookback period.
    If the current candle's body is larger than the `percentile` threshold of the
    historical distribution, it signals a potential exhaustion or breakout.
    """

    def __init__(self, lookback: int = 30, percentile: float = 0.95, buffer_size: int = 50):
        self.lookback = lookback
        self.percentile = percentile
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.lookback + 1:
            return None

        # Calculate body sizes for the lookback period (excluding current candle)
        history_candles = candles[-(self.lookback + 1) : -1]
        history_bodies = np.abs(history_candles[:, 4] - history_candles[:, 1])

        # Calculate the threshold value at the given percentile
        threshold = np.percentile(history_bodies, self.percentile * 100)

        # Check current candle
        cur = candles[-1]
        cur_body = abs(cur[4] - cur[1])

        if cur_body > threshold:
            # Determine direction
            side = "LONG" if cur[4] > cur[1] else "SHORT"
            return {
                "side": side,
                "features": {"body_size": cur_body, "threshold": threshold, "ratio": cur_body / (threshold + 1e-9)},
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Wrapper called by SensorManager."""
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
        if len(self.candle_buffer) < self.lookback + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
