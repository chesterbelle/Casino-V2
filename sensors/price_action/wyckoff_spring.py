from collections import deque
from typing import Dict, Optional

import numpy as np


class WyckoffSpring:
    """Detects a Wyckoff Spring (Bullish) or Upthrust (Bearish).

    A Spring occurs when price breaks below a support level but then closes back
    above it, often on high volume, indicating a "bear trap" or liquidity grab.
    An Upthrust is the bearish equivalent (bull trap).
    """

    def __init__(self, lookback: int = 20, volume_factor: float = 1.5, buffer_size: int = 50):
        self.lookback = lookback
        self.volume_factor = volume_factor
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.lookback + 1:
            return None

        # Current candle
        cur = candles[-1]
        # cur_open = cur[1]
        cur_high = cur[2]
        cur_low = cur[3]
        cur_close = cur[4]
        cur_volume = cur[5]

        # Previous candles for support/resistance
        history = candles[-(self.lookback + 1) : -1]

        # Calculate support (lowest low) and resistance (highest high) of history
        support = np.min(history[:, 3])
        resistance = np.max(history[:, 2])

        # Calculate average volume of history
        avg_volume = np.mean(history[:, 5])

        # Check for Spring (Bullish)
        # 1. Low breaks support
        # 2. Close is back above support
        # 3. Volume is high (optional but recommended)
        if cur_low < support and cur_close > support:
            if cur_volume > avg_volume * self.volume_factor:
                return {
                    "side": "LONG",
                    "features": {
                        "type": "spring",
                        "support": support,
                        "volume_ratio": cur_volume / (avg_volume + 1e-9),
                    },
                }

        # Check for Upthrust (Bearish)
        # 1. High breaks resistance
        # 2. Close is back below resistance
        # 3. Volume is high
        if cur_high > resistance and cur_close < resistance:
            if cur_volume > avg_volume * self.volume_factor:
                return {
                    "side": "SHORT",
                    "features": {
                        "type": "upthrust",
                        "resistance": resistance,
                        "volume_ratio": cur_volume / (avg_volume + 1e-9),
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
        if len(self.candle_buffer) < self.lookback + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
