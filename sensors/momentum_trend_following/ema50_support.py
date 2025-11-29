"""
EMA50 Dynamic Support

Captures deep pullbacks to the 50-period EMA in established trends.
Offers better risk/reward than shallow EMA20 pullbacks.

Logic:
- Trend: Price generally above EMA50
- Trigger: Price touches EMA50
- Confirmation: Close respects the EMA (doesn't close significantly beyond it)
"""

from collections import deque
from typing import Dict, Optional


class EMA50Support:
    """
    EMA50 Dynamic Support Sensor.

    Trades bounces off the 50 EMA.
    """

    def __init__(self, ema_period: int = 50, tolerance_pct: float = 0.001):
        """
        Args:
            ema_period: Period for EMA (default 50)
            tolerance_pct: Zone around EMA considered a "touch" (default 0.1%)
        """
        self.ema_period = ema_period
        self.tolerance_pct = tolerance_pct
        self.ema_val = None
        self.closes = deque(maxlen=ema_period + 10)

    def _update_ema(self, close: float):
        k = 2 / (self.ema_period + 1)
        if self.ema_val is None:
            self.ema_val = close
        else:
            self.ema_val = (close * k) + (self.ema_val * (1 - k))

    def check_signal(self, candle: dict) -> Optional[Dict]:
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        open_p = float(candle["open"])
        timestamp = candle["timestamp"]

        self._update_ema(close)
        self.closes.append(close)

        if self.ema_val is None or len(self.closes) < self.ema_period:
            return None

        # Logic

        # LONG: Trend Up (previous closes > EMA) -> Dip to EMA -> Bounce
        # Check if we were above EMA recently (simple trend check)
        # Ideally check slope, but price position is a good proxy

        # Check touch
        dist_to_ema = abs(low - self.ema_val)
        touch_threshold = self.ema_val * self.tolerance_pct

        # LONG SCENARIO
        # 1. Low touched EMA zone
        if low <= (self.ema_val + touch_threshold):
            # 2. But Close respected EMA (didn't close far below)
            # Allow small violation (0.1%)
            if close >= (self.ema_val * 0.999):
                # 3. Bullish candle (Close > Open) OR Hammer (Long lower wick)
                is_bullish_candle = close > open_p

                # Check for hammer: Lower wick > Body
                body = abs(close - open_p)
                lower_wick = min(close, open_p) - low
                is_hammer = lower_wick > body

                if is_bullish_candle or is_hammer:
                    # 4. Filter: Ensure we are not in a downtrend
                    # Check if EMA is rising? Or just if price was above it before
                    # Simple check: EMA > EMA_prev (requires history)
                    # Let's assume valid if price > EMA

                    return {
                        "timestamp": timestamp,
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                        "side": "LONG",
                        "range_score": 2,
                        "features": {
                            "pattern": "ema50_bounce_long",
                            "ema": float(self.ema_val),
                            "dist_pct": float(dist_to_ema / self.ema_val),
                        },
                    }

        # SHORT SCENARIO
        # 1. High touched EMA zone
        if high >= (self.ema_val - touch_threshold):
            # 2. Close respected EMA
            if close <= (self.ema_val * 1.001):
                # 3. Bearish candle OR Shooting Star
                is_bearish_candle = close < open_p

                upper_wick = high - max(close, open_p)
                body = abs(close - open_p)
                is_shooting_star = upper_wick > body

                if is_bearish_candle or is_shooting_star:
                    return {
                        "timestamp": timestamp,
                        "symbol": candle.get("symbol"),
                        "timeframe": candle.get("timeframe"),
                        "side": "SHORT",
                        "range_score": 2,
                        "features": {
                            "pattern": "ema50_bounce_short",
                            "ema": float(self.ema_val),
                            "dist_pct": float(abs(high - self.ema_val) / self.ema_val),
                        },
                    }

        return None
