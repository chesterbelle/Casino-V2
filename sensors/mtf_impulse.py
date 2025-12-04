"""
MTFImpulse Sensor (V3).
Logic: Multi-timeframe impulse detection using momentum alignment.

Detects strong impulse moves when both current (1m) and higher
timeframe (5m/15m) show aligned momentum.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class MTFImpulseV3(SensorV3):
    @property
    def name(self) -> str:
        return "MTFImpulse"

    # This sensor uses multiple timeframes
    timeframe: str = "1m"

    def __init__(
        self,
        htf="5m",
        momentum_period=10,
        impulse_threshold=0.003,
    ):
        """
        Args:
            htf: Higher timeframe to use ("5m", "15m", "1h")
            momentum_period: Period for momentum calculation
            impulse_threshold: Min momentum % to trigger signal
        """
        self.htf = htf
        self.momentum_period = momentum_period
        self.impulse_threshold = impulse_threshold

        # Current timeframe (1m) data
        self.closes = deque(maxlen=momentum_period + 10)

        # HTF closes (from context)
        self.htf_closes = deque(maxlen=momentum_period + 10)

        self._last_htf_timestamp = None

    def calculate(self, context: dict) -> dict:
        # Get 1m candle (always available)
        candle = context["1m"]
        close = candle["close"]
        self.closes.append(close)

        # Get HTF candle from context
        htf_candle = context.get(self.htf)

        # Store HTF close when available and new
        if htf_candle is not None:
            htf_timestamp = htf_candle.get("timestamp")
            if htf_timestamp != self._last_htf_timestamp:
                if htf_candle.get("is_complete", True):
                    self.htf_closes.append(htf_candle["close"])
                    self._last_htf_timestamp = htf_timestamp

        # Need enough data for momentum on both timeframes
        if len(self.closes) < self.momentum_period:
            return None
        if len(self.htf_closes) < self.momentum_period:
            return None

        # Calculate momentum on both timeframes
        ltf_momentum = self._calculate_momentum(list(self.closes))
        htf_momentum = self._calculate_momentum(list(self.htf_closes))

        # Check for aligned impulse
        return self._check_impulse(ltf_momentum, htf_momentum)

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
                    "htf": self.htf,
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
                    "htf": self.htf,
                    "ltf_momentum": ltf_momentum,
                    "htf_momentum": htf_momentum,
                    "combined": combined_momentum,
                },
            }
