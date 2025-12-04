"""
DecelerationCandles Sensor (V3).
Tier 3: Good.
Logic: Sequence of shrinking candles indicating exhaustion.
"""

import logging
from collections import deque

from .base import SensorV3

logger = logging.getLogger(__name__)


class DecelerationCandlesV3(SensorV3):
    @property
    def name(self) -> str:
        return "DecelerationCandles"

    def __init__(self, sequence_length=3):
        self.sequence_length = sequence_length
        self.candles = deque(maxlen=sequence_length)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf)
        if candle is None:
            return None  # TF not ready yet, skip this cycle
        self.candles.append(candle)
        if len(self.candles) < self.sequence_length:
            return None

        # Extract bodies and directions
        bodies = []
        directions = []  # 1 for Bullish, -1 for Bearish

        for c in self.candles:
            body = abs(c["close"] - c["open"])
            direction = 1 if c["close"] > c["open"] else -1
            bodies.append(body)
            directions.append(direction)

        # Check 1: All same direction
        first_dir = directions[0]
        if not all(d == first_dir for d in directions):
            return None

        # Check 2: Bodies shrinking
        # Body(N) < Body(N-1) ...
        # Iterating: bodies[i+1] < bodies[i]
        is_shrinking = True
        for i in range(len(bodies) - 1):
            if bodies[i + 1] >= bodies[i]:
                is_shrinking = False
                break

        if not is_shrinking:
            return None

        signal = None

        # Bullish Deceleration -> Reversal SHORT
        if first_dir == 1:
            signal = {"side": "SHORT", "score": 1.0, "metadata": {"pattern": "deceleration_bullish"}}

        # Bearish Deceleration -> Reversal LONG
        elif first_dir == -1:
            signal = {"side": "LONG", "score": 1.0, "metadata": {"pattern": "deceleration_bearish"}}

        return signal
