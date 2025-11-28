from collections import deque
from typing import Dict, Optional

import numpy as np


class DecelerationCandles:
    """Detects momentum deceleration (exhaustion).

    Deceleration is identified by a sequence of candles (default 3) where the body size
    progressively shrinks, indicating that the dominant force is losing steam.
    Ideally, this happens approaching a key level, but here we detect the pattern itself.
    """

    def __init__(self, sequence_length: int = 3, buffer_size: int = 20):
        self.sequence_length = sequence_length
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.sequence_length:
            return None

        # Get the sequence
        seq = candles[-self.sequence_length :]

        # Calculate bodies and directions
        bodies = np.abs(seq[:, 4] - seq[:, 1])
        directions = np.sign(seq[:, 4] - seq[:, 1])  # 1 for Bullish, -1 for Bearish

        # Check 1: All candles must be same direction (or at least dominant)
        # Strict version: All same direction
        if not np.all(directions == directions[0]):
            return None

        direction = "LONG" if directions[0] == 1 else "SHORT"

        # Check 2: Bodies must be shrinking
        # Body(N) < Body(N-1) < Body(N-2) ...
        # We iterate from index 0 to length-2
        for i in range(self.sequence_length - 1):
            if bodies[i + 1] >= bodies[i]:
                return None

        # If we are here, we have deceleration
        # Bullish Deceleration (Green candles getting smaller) -> Potential SHORT signal (Reversal)
        # Bearish Deceleration (Red candles getting smaller) -> Potential LONG signal (Reversal)

        if direction == "LONG":
            return {
                "side": "SHORT",  # Reversal
                "features": {"type": "deceleration_bullish", "sequence_length": self.sequence_length},
            }
        else:
            return {
                "side": "LONG",  # Reversal
                "features": {"type": "deceleration_bearish", "sequence_length": self.sequence_length},
            }

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
        if len(self.candle_buffer) < self.sequence_length:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
