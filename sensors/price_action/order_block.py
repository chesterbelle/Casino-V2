from collections import deque
from typing import Dict, Optional

import numpy as np


class OrderBlockBreakout:
    """Detects a breakout from a tight consolidation block (Order Block).

    The sensor identifies a sequence of candles with low volatility (range < max_range_pct).
    If a subsequent candle breaks out of this block's high/low with strong momentum,
    a signal is emitted.
    """

    def __init__(
        self, block_size: int = 3, max_range_pct: float = 0.001, breakout_pct: float = 0.003, buffer_size: int = 20
    ):
        self.block_size = block_size
        self.max_range_pct = max_range_pct
        self.breakout_pct = breakout_pct
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.block_size + 1:
            return None

        # Check if the previous 'block_size' candles form a tight range
        block_candles = candles[-(self.block_size + 1) : -1]
        block_highs = block_candles[:, 2]
        block_lows = block_candles[:, 3]
        block_high = np.max(block_highs)
        block_low = np.min(block_lows)

        # Calculate block range percentage relative to price
        avg_price = np.mean(block_candles[:, 4])
        block_range_pct = (block_high - block_low) / avg_price

        if block_range_pct > self.max_range_pct:
            return None

        # Check current candle for breakout
        cur = candles[-1]
        close = cur[4]

        # Breakout logic
        if close > block_high * (1 + self.breakout_pct):
            return {
                "side": "LONG",
                "features": {"block_range_pct": block_range_pct, "breakout_pct": (close - block_high) / block_high},
            }
        elif close < block_low * (1 - self.breakout_pct):
            return {
                "side": "SHORT",
                "features": {"block_range_pct": block_range_pct, "breakout_pct": (block_low - close) / block_low},
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
        if len(self.candle_buffer) < self.block_size + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
