from collections import deque
from typing import Dict, Optional

import numpy as np


class LongTailDistribution:
    """Detects a 'long tail' event: a series of small candles followed by a massive one.

    This sensor tracks the cumulative range of the last `n_small` candles. If the
    next candle's range exceeds this cumulative range by a factor of `factor`,
    it indicates a potential exhaustion or significant volatility expansion.
    """

    def __init__(self, n_small: int = 5, factor: float = 3.0, buffer_size: int = 20):
        self.n_small = n_small
        self.factor = factor
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.n_small + 1:
            return None

        # Get the 'n_small' candles before the current one
        small_candles = candles[-(self.n_small + 1) : -1]

        # Calculate ranges (high - low)
        ranges = small_candles[:, 2] - small_candles[:, 3]
        cumulative_range = np.sum(ranges)

        # Check current candle
        cur = candles[-1]
        cur_range = cur[2] - cur[3]

        if cur_range > cumulative_range * self.factor:
            # Determine direction
            side = "LONG" if cur[4] > cur[1] else "SHORT"
            return {
                "side": side,
                "features": {
                    "cur_range": cur_range,
                    "cumulative_range": cumulative_range,
                    "ratio": cur_range / (cumulative_range + 1e-9),
                },
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
        if len(self.candle_buffer) < self.n_small + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
