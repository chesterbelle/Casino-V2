"""
Volume Delta - Buy vs Sell Pressure

Approximates buy and sell volume to detect underlying pressure
before price moves significantly.

This is a proxy for order flow delta without tick data.
"""

from collections import deque
from typing import Dict, Optional


class VolumeDelta:
    """
    Calculates volume delta (buy volume - sell volume) to detect pressure.

    Uses candle structure to approximate:
    - Buy volume: portion of volume when price moved up
    - Sell volume: portion of volume when price moved down
    """

    def __init__(self, lookback: int = 10, delta_threshold: float = 0.6):
        """
        Args:
            lookback: Number of candles to accumulate delta (default 10)
            delta_threshold: Cumulative delta threshold to trigger signal (default 0.6)
        """
        self.lookback = lookback
        self.delta_threshold = delta_threshold
        self.candle_buffer = deque(maxlen=lookback + 1)

    def _calculate_candle_delta(self, candle: dict) -> float:
        """
        Approximate buy/sell volume for a single candle.

        Buy volume ≈ volume × (close - low) / (high - low)
        Sell volume ≈ volume × (high - close) / (high - low)
        Delta = buy_volume - sell_volume
        """
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle["volume"]

        candle_range = high - low

        if candle_range == 0:
            # Flat candle - no delta
            return 0.0

        # Approximate buy and sell volume
        buy_volume = volume * (close - low) / candle_range
        sell_volume = volume * (high - close) / candle_range

        # Delta (positive = buying pressure, negative = selling pressure)
        delta = buy_volume - sell_volume

        return delta

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """
        Calculate cumulative volume delta and generate signals.

        Args:
            candle: Current candle dict with OHLCV data

        Returns:
            Signal dict if delta threshold exceeded, None otherwise
        """
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < self.lookback + 1:
            return None

        # Calculate delta for each candle in buffer
        deltas = [self._calculate_candle_delta(c) for c in self.candle_buffer]

        # Calculate cumulative delta
        cumulative_delta = sum(deltas)

        # Calculate total volume for normalization
        total_volume = sum(c["volume"] for c in self.candle_buffer)

        if total_volume == 0:
            return None

        # Normalize delta by total volume
        normalized_delta = cumulative_delta / total_volume

        # Get current candle delta for context
        current_delta = self._calculate_candle_delta(candle)

        # Generate signals based on cumulative delta
        if normalized_delta > self.delta_threshold:
            # Strong buying pressure
            return {
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "cumulative_delta": float(cumulative_delta),
                    "normalized_delta": float(normalized_delta),
                    "current_delta": float(current_delta),
                    "lookback": self.lookback,
                    "state": "buying_pressure",
                },
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
            }

        elif normalized_delta < -self.delta_threshold:
            # Strong selling pressure
            return {
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "cumulative_delta": float(cumulative_delta),
                    "normalized_delta": float(normalized_delta),
                    "current_delta": float(current_delta),
                    "lookback": self.lookback,
                    "state": "selling_pressure",
                },
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
            }

        return None
