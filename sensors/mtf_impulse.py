"""
MTFImpulse Sensor (V3).
Logic: Multi-timeframe impulse detection using momentum alignment.

Detects strong impulse moves when both current and higher timeframe
show aligned momentum.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class MTFImpulseV3(SensorV3):
    @property
    def name(self) -> str:
        return "MTFImpulse"

    def __init__(
        self,
        htf_multiplier=5,
        momentum_period=10,
        impulse_threshold=0.003,
    ):
        """
        Args:
            htf_multiplier: Candles to aggregate for HTF (5 = 5m from 1m)
            momentum_period: Period for momentum calculation
            impulse_threshold: Min momentum % to trigger signal
        """
        self.htf_multiplier = htf_multiplier
        self.momentum_period = momentum_period
        self.impulse_threshold = impulse_threshold

        # Current timeframe data
        self.closes = deque(maxlen=momentum_period + 10)

        # HTF aggregation
        self.candle_buffer = deque(maxlen=htf_multiplier)
        self.htf_closes = deque(maxlen=momentum_period + 10)

        self.candle_count = 0

    def calculate(self, candle: dict) -> dict:
        close = candle["close"]
        self.closes.append(close)
        self.candle_buffer.append(candle)
        self.candle_count += 1

        # Aggregate HTF
        if self.candle_count % self.htf_multiplier == 0:
            htf_close = candle["close"]  # Use last close as HTF close
            self.htf_closes.append(htf_close)

        # Need enough data for momentum
        if len(self.closes) < self.momentum_period:
            return None
        if len(self.htf_closes) < self.momentum_period:
            return None

        # Calculate momentum on both timeframes
        ltf_momentum = self._calculate_momentum(list(self.closes))
        htf_momentum = self._calculate_momentum(list(self.htf_closes))

        # Check for aligned impulse
        signal = self._check_impulse(ltf_momentum, htf_momentum)
        return signal

    def _calculate_momentum(self, closes):
        """Calculate rate of change momentum."""
        if len(closes) < self.momentum_period:
            return 0

        old_price = closes[-self.momentum_period]
        new_price = closes[-1]

        if old_price == 0:
            return 0

        return (new_price - old_price) / old_price

    def _check_impulse(self, ltf_momentum, htf_momentum):
        """Check for aligned momentum impulse."""
        # Both must exceed threshold
        if abs(ltf_momentum) < self.impulse_threshold:
            return None
        if abs(htf_momentum) < self.impulse_threshold:
            return None

        # Must be same direction
        if (ltf_momentum > 0) != (htf_momentum > 0):
            return None

        # Calculate combined strength
        combined_momentum = (abs(ltf_momentum) + abs(htf_momentum)) / 2

        if ltf_momentum > 0:
            return {
                "side": "LONG",
                "score": min(combined_momentum / self.impulse_threshold, 2.0) / 2,
                "metadata": {
                    "ltf_momentum": ltf_momentum,
                    "htf_momentum": htf_momentum,
                    "combined": combined_momentum,
                },
            }
        else:
            return {
                "side": "SHORT",
                "score": min(combined_momentum / self.impulse_threshold, 2.0) / 2,
                "metadata": {
                    "ltf_momentum": ltf_momentum,
                    "htf_momentum": htf_momentum,
                    "combined": combined_momentum,
                },
            }
