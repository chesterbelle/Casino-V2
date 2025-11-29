"""
Wick Rejection Pattern - Micro Price Action

Detects strong wick rejections that indicate failed breakout attempts
and potential reversals.

Used by professional scalpers to identify exhaustion points.
"""

from collections import deque
from typing import Dict, Optional


class WickRejection:
    """
    Detects wick rejection patterns for scalping.

    Bullish rejection: Long lower wick, close near high (buyers rejected sellers)
    Bearish rejection: Long upper wick, close near low (sellers rejected buyers)
    """

    def __init__(self, wick_to_body_ratio: float = 2.0, min_wick_pct: float = 0.003):
        """
        Args:
            wick_to_body_ratio: Wick must be X times body size (default 2.0)
            min_wick_pct: Minimum wick size as % of price (default 0.3%)
        """
        self.wick_to_body_ratio = wick_to_body_ratio
        self.min_wick_pct = min_wick_pct
        self.candle_buffer = deque(maxlen=10)

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """
        Check for wick rejection signal.

        Args:
            candle: Current candle dict with OHLCV data

        Returns:
            Signal dict if rejection pattern found, None otherwise
        """
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 2:
            return None

        current = candle

        # Calculate candle components
        open_price = current["open"]
        close = current["close"]
        high = current["high"]
        low = current["low"]

        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low

        # Calculate wick sizes as % of price
        upper_wick_pct = upper_wick / close if close > 0 else 0
        lower_wick_pct = lower_wick / close if close > 0 else 0

        # Bullish rejection: Long lower wick, close near high
        if lower_wick_pct >= self.min_wick_pct and lower_wick >= body * self.wick_to_body_ratio:

            # Verify close is in upper portion of candle
            candle_range = high - low
            if candle_range > 0:
                close_position = (close - low) / candle_range

                if close_position >= 0.7:  # Close in upper 30%
                    return {
                        "side": "LONG",
                        "range_score": 2,
                        "features": {
                            "lower_wick_pct": float(lower_wick_pct * 100),
                            "wick_to_body": float(lower_wick / body) if body > 0 else float("inf"),
                            "close_position": float(close_position),
                            "pattern": "bullish_rejection",
                        },
                        "timestamp": candle["timestamp"],
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                    }

        # Bearish rejection: Long upper wick, close near low
        elif upper_wick_pct >= self.min_wick_pct and upper_wick >= body * self.wick_to_body_ratio:

            # Verify close is in lower portion of candle
            candle_range = high - low
            if candle_range > 0:
                close_position = (close - low) / candle_range

                if close_position <= 0.3:  # Close in lower 30%
                    return {
                        "side": "SHORT",
                        "range_score": 2,
                        "features": {
                            "upper_wick_pct": float(upper_wick_pct * 100),
                            "wick_to_body": float(upper_wick / body) if body > 0 else float("inf"),
                            "close_position": float(close_position),
                            "pattern": "bearish_rejection",
                        },
                        "timestamp": candle["timestamp"],
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                    }

        return None
