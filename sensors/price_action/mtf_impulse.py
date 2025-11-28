from collections import deque
from typing import Dict, Optional

import numpy as np


class MultiTimeframeImpulse:
    """Detects momentum alignment across multiple timeframes (1m, 5m, 15m).

    Since we only receive 1m candles, we internally aggregate them to form
    5m and 15m candles. We then check if price is above/below EMA(20) on
    ALL three timeframes to confirm a strong trend impulse.
    """

    def __init__(self, ema_period: int = 20, buffer_size: int = 300):
        self.ema_period = ema_period
        # Buffer needs to be large enough to calculate EMA on 15m
        # 15m EMA(20) requires ~20 * 15 = 300 minutes of data
        self.buffer_size = max(buffer_size, ema_period * 15 + 10)
        self.candle_buffer = deque(maxlen=self.buffer_size)

    def _aggregate_candles(self, candles_1m: np.ndarray, timeframe_minutes: int) -> np.ndarray:
        """Aggregates 1m candles into higher timeframe candles."""
        n = len(candles_1m)
        if n < timeframe_minutes:
            return np.array([])

        # We need to align to the timeframe boundaries (e.g. 5m candles start at :00, :05, etc.)
        # But for simplicity and rolling window, we can just group every X candles.
        # However, true alignment is better.
        # Let's assume simple rolling aggregation for trend check is sufficient,
        # or just take every Nth candle? No, we need proper OHLC.

        # Let's do simple non-overlapping chunks from the end
        # e.g. last 5 candles = current 5m candle

        num_candles = n // timeframe_minutes
        if num_candles < self.ema_period:
            return np.array([])

        aggregated = []
        # Start from the end and go backwards in chunks
        for i in range(num_candles):
            start_idx = n - (i + 1) * timeframe_minutes
            end_idx = n - i * timeframe_minutes
            chunk = candles_1m[start_idx:end_idx]

            # Aggregate
            ts = chunk[0, 0]
            op = chunk[0, 1]
            hi = np.max(chunk[:, 2])
            lo = np.min(chunk[:, 3])
            cl = chunk[-1, 4]
            vol = np.sum(chunk[:, 5])

            aggregated.insert(0, [ts, op, hi, lo, cl, vol])

        return np.array(aggregated)

    def _calculate_ema(self, closes: np.ndarray) -> float:
        if len(closes) < self.ema_period:
            return 0.0
        alpha = 2.0 / (self.ema_period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.ema_period:
            return None

        # 1. Check 1m Trend
        ema_1m = self._calculate_ema(candles[:, 4])
        cur_close = candles[-1, 4]
        trend_1m = 1 if cur_close > ema_1m else -1

        # 2. Check 5m Trend
        candles_5m = self._aggregate_candles(candles, 5)
        if len(candles_5m) < self.ema_period:
            return None
        ema_5m = self._calculate_ema(candles_5m[:, 4])
        trend_5m = 1 if cur_close > ema_5m else -1  # Compare current close to 5m EMA

        # 3. Check 15m Trend
        candles_15m = self._aggregate_candles(candles, 15)
        if len(candles_15m) < self.ema_period:
            return None
        ema_15m = self._calculate_ema(candles_15m[:, 4])
        trend_15m = 1 if cur_close > ema_15m else -1

        # Alignment Check
        current_alignment = 0
        if trend_1m == 1 and trend_5m == 1 and trend_15m == 1:
            current_alignment = 1
        elif trend_1m == -1 and trend_5m == -1 and trend_15m == -1:
            current_alignment = -1

        # Only signal if alignment CHANGED from previous state
        # We need to store previous state. Since _detect is stateless per call,
        # we need to rely on the buffer or store state in the class.
        # But _detect is called with full buffer. We can re-calculate prev state.

        # Calculate prev state (at index -2)
        # This is expensive. Alternatively, we can store `self.last_alignment` in the class.
        # Let's use self.last_alignment.

        if not hasattr(self, "last_alignment"):
            self.last_alignment = 0

        signal = None
        if current_alignment != 0 and current_alignment != self.last_alignment:
            if current_alignment == 1:
                signal = {
                    "side": "LONG",
                    "features": {"type": "mtf_alignment_start", "ema_1m": ema_1m, "ema_5m": ema_5m, "ema_15m": ema_15m},
                }
            elif current_alignment == -1:
                signal = {
                    "side": "SHORT",
                    "features": {"type": "mtf_alignment_start", "ema_1m": ema_1m, "ema_5m": ema_5m, "ema_15m": ema_15m},
                }

        self.last_alignment = current_alignment
        return signal

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
        if len(self.candle_buffer) < self.ema_period:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
