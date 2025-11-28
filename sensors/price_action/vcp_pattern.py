from collections import deque
from typing import Dict, Optional

import numpy as np


class VCPPattern:
    """Detects a Volatility Contraction Pattern (VCP).

    VCP is characterized by a series of contractions where the price range (High-Low)
    gets smaller and smaller, often accompanied by decreasing volume. This indicates
    supply absorption and often precedes a strong breakout.
    """

    def __init__(self, contractions: int = 3, buffer_size: int = 50):
        self.contractions = contractions
        self.buffer_size = buffer_size
        self.candle_buffer = deque(maxlen=buffer_size)

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < self.contractions * 2:  # Need enough candles to see waves
            return None

        # VCP is complex to detect perfectly on 1m candles without swing detection.
        # Simplified logic:
        # Check if the range (High-Low) of recent candles is decreasing.
        # But VCP is about *swings*, not just single candles.
        # Let's try a "Micro VCP" on single candles for HFT context:
        # Sequence of N candles where Range(i) < Range(i-1).
        # This is similar to Deceleration but specifically focuses on Range contraction.

        # Better approach for VCP:
        # Look for "Inside Bars" nested? Or just decreasing volatility.
        # Let's use standard deviation of price over sliding windows?
        # Or simply: Range(Current) < Range(Prev) < Range(PrevPrev) ...

        # Let's implement the "Decreasing Range" logic for `contractions` count.

        seq = candles[-self.contractions :]
        ranges = seq[:, 2] - seq[:, 3]
        volumes = seq[:, 5]

        # Check 1: Ranges are decreasing
        for i in range(self.contractions - 1):
            if ranges[i + 1] >= ranges[i]:
                return None

        # Check 2: Volume is decreasing (optional but typical for VCP)
        # We'll be lenient and just check if current volume is lower than start of pattern
        if volumes[-1] >= volumes[0]:
            return None

        # If we have VCP, we expect a breakout.
        # Direction is usually continuation of prior trend, or we wait for breakout.
        # Since this is a sensor, we signal "Volatility Contraction" and maybe bias?
        # Let's check the trend of the Close prices in the sequence.

        closes = seq[:, 4]
        if closes[-1] > closes[0]:
            # Consolidating upwards?
            return {"side": "LONG", "features": {"type": "vcp_bullish", "contractions": self.contractions}}
        else:
            return {"side": "SHORT", "features": {"type": "vcp_bearish", "contractions": self.contractions}}

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
        if len(self.candle_buffer) < self.contractions:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
