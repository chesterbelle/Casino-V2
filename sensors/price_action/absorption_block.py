from collections import deque
from typing import Dict, Optional

import numpy as np


class AbsorptionBlock:
    """Detects Absorption or Stopping Volume.

    Absorption occurs when high volume enters the market but price fails to progress
    significantly (small body). This indicates that the opposing force (buyers or sellers)
    is absorbing the aggressive orders.
    """

    def __init__(self, volume_factor: float = 2.0, body_factor: float = 0.3, buffer_size: int = 50):
        self.volume_factor = volume_factor  # Volume must be X times average
        self.body_factor = body_factor  # Body must be smaller than X times average range
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < 20:
            return None

        # History for averages
        history = candles[:-1]
        avg_volume = np.mean(history[:, 5])
        avg_range = np.mean(history[:, 2] - history[:, 3])

        # Current candle
        cur = candles[-1]
        cur_volume = cur[5]
        # cur_range = cur[2] - cur[3]
        cur_body = abs(cur[4] - cur[1])

        # Criteria 1: High Volume
        if cur_volume < avg_volume * self.volume_factor:
            return None

        # Criteria 2: Small Body (relative to average range or its own range)
        # Here we check if body is small compared to average range
        if cur_body > avg_range * self.body_factor:
            return None

        # Criteria 3: Location (Swing High or Low)
        # Simple check: Is it a local extremum?
        # Check last 5 candles
        recent_highs = candles[-5:, 2]
        recent_lows = candles[-5:, 3]

        is_high = cur[2] >= np.max(recent_highs)
        is_low = cur[3] <= np.min(recent_lows)

        if is_low:
            # Stopping Volume / Absorption at Low -> Bullish
            # Long wick at bottom is a plus
            return {
                "side": "LONG",
                "features": {
                    "type": "absorption_buy",
                    "volume_ratio": cur_volume / (avg_volume + 1e-9),
                    "body_size": cur_body,
                },
            }

        if is_high:
            # Stopping Volume / Absorption at High -> Bearish
            # Long wick at top is a plus
            return {
                "side": "SHORT",
                "features": {
                    "type": "absorption_sell",
                    "volume_ratio": cur_volume / (avg_volume + 1e-9),
                    "body_size": cur_body,
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
        if len(self.candle_buffer) < 20:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
