"""
HigherTFTrend Sensor (V3).
Logic: Confirms trend using higher timeframe EMA alignment.

Multi-timeframe trend confirmation by aggregating candles into
higher timeframe and checking EMA direction.
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

    def __init__(self, htf_multiplier=5, ema_period=20, lookback=3):
        """
        Args:
            htf_multiplier: How many candles to aggregate (5 = 5m from 1m)
            ema_period: EMA period on the higher timeframe
            lookback: Number of HTF candles to confirm trend
        """
        self.htf_multiplier = htf_multiplier
        self.ema_period = ema_period
        self.lookback = lookback

        # Accumulate candles for HTF aggregation
        self.candle_buffer = deque(maxlen=htf_multiplier)

        # HTF candles and EMA values
        self.htf_candles = deque(maxlen=ema_period + lookback + 10)
        self.htf_emas = deque(maxlen=lookback + 5)

        self.candle_count = 0

    def calculate(self, candle: dict) -> dict:
        self.candle_buffer.append(candle)
        self.candle_count += 1

        # Only process when we have enough candles for HTF
        if len(self.candle_buffer) < self.htf_multiplier:
            return None

        # Aggregate to higher timeframe candle
        if self.candle_count % self.htf_multiplier == 0:
            htf_candle = self._aggregate_candles(list(self.candle_buffer))
            self.htf_candles.append(htf_candle)

            # Calculate EMA on HTF
            if len(self.htf_candles) >= self.ema_period:
                ema = self._calculate_ema()
                self.htf_emas.append(ema)

        # Need enough EMAs to confirm trend
        if len(self.htf_emas) < self.lookback:
            return None

        # Check trend direction
        signal = self._check_trend()
        return signal

    def _aggregate_candles(self, candles):
        """Aggregate multiple candles into one HTF candle."""
        return {
            "open": candles[0]["open"],
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "close": candles[-1]["close"],
            "volume": sum(c.get("volume", 0) for c in candles),
        }

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
                    "htf_ema": current_ema,
                    "htf_close": current_close,
                    "trend": "bearish",
                },
            }

        return None
