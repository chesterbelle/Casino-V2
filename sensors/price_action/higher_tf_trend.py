from collections import deque
from typing import Dict, Optional

import numpy as np


class HigherTFTrendConfirm:
    """Detects trend confirmation on a higher timeframe EMA.

    The sensor maintains a short‑term buffer of 1‑minute candles. It computes an
    EMA over the last `ema_period` closes to approximate a higher‑timeframe EMA
    (e.g., 5‑minute). When the current candle closes above that EMA we emit a
    LONG signal, otherwise a SHORT signal.
    """

    def __init__(self, higher_tf: int = 5, ema_period: int = 20, buffer_size: int = 50):
        self.higher_tf = higher_tf
        self.ema_period = ema_period
        self.candle_buffer = deque(maxlen=buffer_size)

    def _ema(self, closes: np.ndarray) -> float:
        """Calculate EMA of the provided close series.

        Uses the standard smoothing factor `alpha = 2 / (period + 1)`.
        """
        alpha = 2.0 / (self.ema_period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < max(self.ema_period, self.higher_tf) + 2:
            return None
        # Use the most recent `ema_period` closes for EMA calculation
        # We need EMA for previous candle too to check crossover
        # Simple approximation: Calculate EMA on history, assume it doesn't change drastically in 1 bar for the check
        # Or better: Calculate EMA series.

        closes = candles[:, 4]
        # Calculate EMA for the last 2 points
        # This is expensive to do full loop every time.
        # Optimization: Just calculate EMA for the last point using previous EMA?
        # But we re-calculate from scratch here.

        # Let's calculate EMA for the whole buffer to get prev and cur EMA values
        alpha = 2.0 / (self.ema_period + 1)
        ema_values = np.zeros_like(closes)
        ema_values[0] = closes[0]
        for i in range(1, len(closes)):
            ema_values[i] = alpha * closes[i] + (1 - alpha) * ema_values[i - 1]

        cur_ema = ema_values[-1]
        prev_ema = ema_values[-2]

        cur_close = closes[-1]
        prev_close = closes[-2]

        # Check Crossover
        # LONG: Price crosses above EMA
        if prev_close < prev_ema and cur_close > cur_ema:
            return {
                "side": "LONG",
                "features": {"higher_tf": self.higher_tf, "ema": float(cur_ema), "type": "crossover"},
            }

        # SHORT: Price crosses below EMA
        if prev_close > prev_ema and cur_close < cur_ema:
            return {
                "side": "SHORT",
                "features": {"higher_tf": self.higher_tf, "ema": float(cur_ema), "type": "crossover"},
            }

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Add candle to buffer and evaluate the higher‑TF trend.

        Expected `candle` keys: timestamp, open, high, low, close, volume, symbol,
        timeframe.
        """
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
        if len(self.candle_buffer) < max(self.ema_period, self.higher_tf) + 1:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
