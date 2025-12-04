"""
HigherTFTrend Sensor (V3).
Logic: Confirms trend using higher timeframe EMA alignment.

Uses pre-aggregated HTF candles from context (5m, 15m, 1h)
to check EMA direction and trend confirmation.
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class HigherTFTrendV3(SensorV3):
    @property
    def name(self) -> str:
        return "HigherTFTrend"

    # This sensor uses higher timeframe data
    timeframe: str = "5m"

    def __init__(self, htf="5m", ema_period=20, lookback=3):
        """
        Args:
            htf: Higher timeframe to use ("5m", "15m", "1h")
            ema_period: EMA period on the higher timeframe
            lookback: Number of HTF candles to confirm trend
        """
        self.htf = htf
        self.ema_period = ema_period
        self.lookback = lookback

        # HTF candles history (from context)
        self.htf_candles = deque(maxlen=ema_period + lookback + 10)
        self.htf_emas = deque(maxlen=lookback + 5)

        self._last_htf_timestamp = None

    def calculate(self, context: dict) -> dict:
        # Get HTF candle from context
        htf_candle = context.get(self.htf)

        if htf_candle is None:
            return None

        # Skip if we already processed this HTF candle
        htf_timestamp = htf_candle.get("timestamp")
        if htf_timestamp == self._last_htf_timestamp:
            return None

        # Only process complete HTF candles
        if not htf_candle.get("is_complete", True):
            return None

        self._last_htf_timestamp = htf_timestamp
        self.htf_candles.append(htf_candle)

        # Calculate EMA on HTF
        if len(self.htf_candles) >= self.ema_period:
            ema = self._calculate_ema()
            if ema is not None:
                self.htf_emas.append(ema)

        # Need enough EMAs to confirm trend
        if len(self.htf_emas) < self.lookback:
            return None

        # Check trend direction
        return self._check_trend()

    def _calculate_ema(self):
        """Calculate EMA on HTF closes."""
        closes = [c["close"] for c in self.htf_candles]
        if len(closes) < self.ema_period:
            return None

        multiplier = 2 / (self.ema_period + 1)
        ema = np.mean(closes[: self.ema_period])
        for price in closes[self.ema_period :]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _check_trend(self):
        """Check if HTF trend is established."""
        emas = list(self.htf_emas)
        if len(emas) < self.lookback:
            return None

        recent_emas = emas[-self.lookback :]
        current_close = self.htf_candles[-1]["close"]
        current_ema = recent_emas[-1]

        # Check if EMAs are consistently rising or falling
        ema_rising = all(recent_emas[i] < recent_emas[i + 1] for i in range(len(recent_emas) - 1))
        ema_falling = all(recent_emas[i] > recent_emas[i + 1] for i in range(len(recent_emas) - 1))

        # Price above rising EMA = bullish
        if ema_rising and current_close > current_ema:
            return {
                "side": "LONG",
                "score": 1.0,
                "metadata": {
                    "htf": self.htf,
                    "htf_ema": current_ema,
                    "htf_close": current_close,
                    "trend": "bullish",
                },
            }

        # Price below falling EMA = bearish
        if ema_falling and current_close < current_ema:
            return {
                "side": "SHORT",
                "score": 1.0,
                "metadata": {
                    "htf": self.htf,
                    "htf_ema": current_ema,
                    "htf_close": current_close,
                    "trend": "bearish",
                },
            }

        return None
