"""
Aggressive Volume Detection - Order Flow Proxy

Detects aggressive market participants (institutional/whale activity)
by identifying volume spikes with directional bias.

This is a proxy for order flow analysis without Level 2 data.
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class AggressiveVolume:
    """
    Detects aggressive buying or selling based on volume and price action.

    Aggressive buying: High volume + bullish candle (close > open)
    Aggressive selling: High volume + bearish candle (close < open)
    """

    def __init__(self, volume_multiplier: float = 2.0, min_body_pct: float = 0.002):
        """
        Args:
            volume_multiplier: Volume must be X times average (default 2.0)
            min_body_pct: Minimum candle body size as % of price (default 0.2%)
        """
        self.volume_multiplier = volume_multiplier
        self.min_body_pct = min_body_pct
        self.candle_buffer = deque(maxlen=21)

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """
        Detect aggressive volume with directional bias.

        Args:
            candle: Current candle dict with OHLCV data

        Returns:
            Signal dict if aggressive volume detected, None otherwise
        """
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 21:  # Need 20 candles for average
            return None

        # Get current and recent candles
        current = candle
        recent = list(self.candle_buffer)[:-1]  # Last 20 candles (excluding current)

        # Calculate average volume
        avg_volume = np.mean([c["volume"] for c in recent])

        # Check if current volume is significant
        if current["volume"] < avg_volume * self.volume_multiplier:
            return None

        # Calculate candle metrics
        body = abs(current["close"] - current["open"])
        candle_range = current["high"] - current["low"]

        if candle_range == 0 or current["close"] == 0:
            return None

        body_pct = body / current["close"]

        # Require minimum body size (filter out dojis with high volume)
        if body_pct < self.min_body_pct:
            return None

        # Determine direction
        is_bullish = current["close"] > current["open"]

        # Calculate volume ratio
        volume_ratio = current["volume"] / avg_volume

        # Generate signal
        if is_bullish:
            return {
                "side": "LONG",
                "range_score": 2,  # High confidence - institutional activity
                "features": {
                    "volume_ratio": float(volume_ratio),
                    "body_pct": float(body_pct * 100),
                    "avg_volume": float(avg_volume),
                    "current_volume": float(current["volume"]),
                    "state": "aggressive_buying",
                },
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
            }
        else:
            return {
                "side": "SHORT",
                "range_score": 2,  # High confidence - institutional activity
                "features": {
                    "volume_ratio": float(volume_ratio),
                    "body_pct": float(body_pct * 100),
                    "avg_volume": float(avg_volume),
                    "current_volume": float(current["volume"]),
                    "state": "aggressive_selling",
                },
                "timestamp": candle["timestamp"],
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
            }
