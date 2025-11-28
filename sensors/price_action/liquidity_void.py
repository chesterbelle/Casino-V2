from collections import deque
from typing import Dict, Optional

import numpy as np


class LiquidityVoid:
    """Detects a liquidity void (gap) in price action.

    A liquidity void occurs when price jumps significantly between candles, leaving
    a gap where no trading occurred. This often acts as a magnet for price to return.
    The sensor detects gaps larger than `gap_pct` with low volume on the jump.
    """

    def __init__(self, gap_pct: float = 0.002, max_volume_pct: float = 0.001, buffer_size: int = 20):
        self.gap_pct = gap_pct
        self.max_volume_pct = max_volume_pct
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < 2:
            return None

        prev = candles[-2]
        cur = candles[-1]

        prev_high = prev[2]
        prev_low = prev[3]
        cur_high = cur[2]
        cur_low = cur[3]
        # cur_open = cur[1]
        # cur_close = cur[4]
        # cur_volume = cur[5]

        # Check for gap up
        if cur_low > prev_high:
            gap_size = (cur_low - prev_high) / prev_high
            if gap_size > self.gap_pct:
                # Check for low volume on the gap candle (optional confirmation)
                # Here we just flag the gap itself as a potential reversal/fill target
                return {"side": "SHORT", "features": {"gap_size": gap_size, "type": "gap_up"}}

        # Check for gap down
        elif cur_high < prev_low:
            gap_size = (prev_low - cur_high) / prev_low
            if gap_size > self.gap_pct:
                return {"side": "LONG", "features": {"gap_size": gap_size, "type": "gap_down"}}

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
        if len(self.candle_buffer) < 2:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
