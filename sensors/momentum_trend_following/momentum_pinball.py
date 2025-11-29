"""
Momentum Pinball - RSI Pullback Strategy

A precision scalping strategy that captures pullbacks in established trends.
Based on the "Pinball" setup used by professional scalpers.

Logic:
- Trend Filter: EMA34 slope (or Price vs EMA34)
- Trigger: RSI(2) pulls back to extreme (<10 for Long, >90 for Short)
- Exit: Quick scalp when RSI(2) crosses 50
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class MomentumPinball:
    """
    Momentum Pinball Sensor.

    Captures high-probability pullbacks in strong trends using RSI(2).
    """

    def __init__(self, ema_period: int = 34, rsi_period: int = 2, oversold: float = 10.0, overbought: float = 90.0):
        """
        Args:
            ema_period: Period for trend definition (default 34)
            rsi_period: Short period RSI for timing (default 2)
            oversold: RSI threshold for long entry (default 10)
            overbought: RSI threshold for short entry (default 90)
        """
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

        # Buffers
        self.closes = deque(maxlen=ema_period + 5)
        self.ema_val = None
        self.prev_rsi = None

    def _update_ema(self, close: float):
        k = 2 / (self.ema_period + 1)
        if self.ema_val is None:
            self.ema_val = close
        else:
            self.ema_val = (close * k) + (self.ema_val * (1 - k))

    def _calculate_rsi(self, current_close: float) -> float:
        if len(self.closes) < self.rsi_period:
            return 50.0

        # Calculate RSI(2) manually for efficiency or use library logic
        # Here using simple logic for RSI(2)

        # Need history of gains/losses for proper RSI
        # For RSI(2), we can approximate or need full history
        # Let's use a simplified calculation for efficiency if full history not available
        # But for correctness, we should maintain avg_gain/avg_loss state

        # Re-implementing standard RSI logic with state would be better
        # For now, let's assume we have enough history in closes to calc diffs

        # To do it properly without external lib:
        # We need to calculate RSI on the fly.
        # Let's use a simple array calculation on the last N candles

        # Actually, for RSI(2), we just need the last 2 changes?
        # No, RSI is recursive (Wilder's smoothing).

        # Let's use a stateless approximation using the buffer
        prices = list(self.closes) + [current_close]
        if len(prices) < self.rsi_period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))

        # Simple Moving Average for RSI (Cutler's RSI) is often used in scalping for speed
        # Wilder's is standard. Let's use simple mean of last N for robustness in short periods
        avg_gain = np.mean(gains[-self.rsi_period :])
        avg_loss = np.mean(losses[-self.rsi_period :])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def check_signal(self, candle: dict) -> Optional[Dict]:
        close = float(candle["close"])
        timestamp = candle["timestamp"]

        # Update EMA first
        self._update_ema(close)

        # Calculate RSI
        rsi = self._calculate_rsi(close)

        # Update buffers
        self.closes.append(close)

        if self.ema_val is None or len(self.closes) < self.ema_period:
            return None

        # Logic

        # LONG: Price > EMA34 (Uptrend) AND RSI(2) < 10 (Pullback)
        if close > self.ema_val and rsi < self.oversold:
            return {
                "timestamp": timestamp,
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "LONG",
                "range_score": 2,
                "features": {"pattern": "momentum_pinball_long", "rsi": float(rsi), "ema_trend": "bullish"},
            }

        # SHORT: Price < EMA34 (Downtrend) AND RSI(2) > 90 (Pullback)
        if close < self.ema_val and rsi > self.overbought:
            return {
                "timestamp": timestamp,
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "SHORT",
                "range_score": 2,
                "features": {"pattern": "momentum_pinball_short", "rsi": float(rsi), "ema_trend": "bearish"},
            }

        return None
