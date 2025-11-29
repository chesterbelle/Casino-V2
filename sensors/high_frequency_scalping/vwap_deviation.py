"""
VWAP Deviation Sensor - Professional Scalping

Volume-Weighted Average Price (VWAP) is the #1 indicator for institutional traders.
It represents the "fair value" of an asset based on both price and volume.

Strategy:
- Price significantly below VWAP → LONG (oversold vs fair value)
- Price significantly above VWAP → SHORT (overbought vs fair value)

This is a mean reversion strategy used by professional scalpers.
"""

import pandas as pd


class VWAPDeviation:
    """
    VWAP Deviation Sensor for scalping.

    Generates signals when price deviates significantly from VWAP,
    expecting mean reversion to fair value.
    """

    def __init__(self, deviation_threshold: float = 0.003, session_reset: bool = True):
        """
        Args:
            deviation_threshold: % deviation from VWAP to trigger signal (default 0.3%)
            session_reset: Whether to reset VWAP at session start (default True)
        """
        self.deviation_threshold = deviation_threshold

        self.session_reset = session_reset
        self.vwap_cumulative = None
        self.volume_cumulative = None
        self.price_volume_cumulative = None
        self.last_session_date = None

    def _reset_vwap(self):
        """Reset VWAP calculation for new session."""
        self.vwap_cumulative = None
        self.volume_cumulative = 0
        self.price_volume_cumulative = 0

    def _calculate_vwap(self, df: pd.DataFrame) -> float:
        """
        Calculate VWAP for current session.

        VWAP = Σ(Typical Price × Volume) / Σ(Volume)
        Typical Price = (High + Low + Close) / 3
        """
        if len(df) == 0:
            return None

        # Get current candle
        current = df.iloc[-1]

        # Check if new session (new day)
        if self.session_reset and hasattr(current, "timestamp"):
            current_date = pd.to_datetime(current["timestamp"]).date()
            if self.last_session_date != current_date:
                self._reset_vwap()
                self.last_session_date = current_date

        # Calculate typical price
        typical_price = (current["high"] + current["low"] + current["close"]) / 3
        volume = current["volume"]

        # Update cumulative values
        self.price_volume_cumulative += typical_price * volume
        self.volume_cumulative += volume

        # Calculate VWAP
        if self.volume_cumulative > 0:
            vwap = self.price_volume_cumulative / self.volume_cumulative
        else:
            vwap = current["close"]

        return vwap

    def analyze(self, df: pd.DataFrame) -> dict | None:
        """
        Analyze price deviation from VWAP.

        Returns:
            Signal dict if deviation threshold exceeded, None otherwise
        """
        if len(df) < 2:
            return None

        # Calculate VWAP
        vwap = self._calculate_vwap(df)
        if vwap is None:
            return None

        # Get current price
        current_price = df.iloc[-1]["close"]

        # Calculate deviation
        deviation = (current_price - vwap) / vwap

        # Generate signals based on deviation
        signal = None

        if deviation < -self.deviation_threshold:
            # Price significantly below VWAP → oversold → LONG
            signal = {
                "side": "LONG",
                "range_score": 2,  # High confidence for mean reversion
                "features": {
                    "vwap": float(vwap),
                    "current_price": float(current_price),
                    "deviation_pct": float(deviation * 100),
                    "threshold": float(self.deviation_threshold * 100),
                    "state": "oversold_vs_vwap",
                },
            }

        elif deviation > self.deviation_threshold:
            # Price significantly above VWAP → overbought → SHORT
            signal = {
                "side": "SHORT",
                "range_score": 2,  # High confidence for mean reversion
                "features": {
                    "vwap": float(vwap),
                    "current_price": float(current_price),
                    "deviation_pct": float(deviation * 100),
                    "threshold": float(self.deviation_threshold * 100),
                    "state": "overbought_vs_vwap",
                },
            }

        return signal
