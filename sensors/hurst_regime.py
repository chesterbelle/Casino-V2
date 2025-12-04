"""
HurstRegime Sensor (V3).
Logic: Hurst exponent for trend/mean-reversion regime detection.

H > 0.5: Trending (persistent)
H < 0.5: Mean-reverting (anti-persistent)
H = 0.5: Random walk
"""

import logging
from collections import deque

import numpy as np

from .base import SensorV3

logger = logging.getLogger(__name__)


class HurstRegimeV3(SensorV3):
    @property
    def name(self) -> str:
        return "HurstRegime"

    def __init__(self, period=50, trend_threshold=0.6, reversion_threshold=0.4):
        """
        Args:
            period: Period for Hurst calculation
            trend_threshold: H above this = trending
            reversion_threshold: H below this = mean-reverting
        """
        self.period = period
        self.trend_threshold = trend_threshold
        self.reversion_threshold = reversion_threshold

        self.closes = deque(maxlen=period + 10)

    def calculate(self, context: dict) -> dict:
        # Get optimal timeframe for this sensor (configured in config/sensors.py)
        tf = getattr(self, "_optimal_tf", "1m")
        candle = context.get(tf) or context["1m"]
        self.closes.append(candle["close"])

        if len(self.closes) < self.period:
            return None

        # Calculate simplified Hurst exponent
        hurst = self._calculate_hurst()
        if hurst is None:
            return None

        # Get recent price direction
        closes = list(self.closes)
        recent_direction = closes[-1] - closes[-5] if len(closes) >= 5 else 0

        # Only signal when regime is clear
        if hurst > self.trend_threshold:
            # Trending regime - follow the trend
            if recent_direction > 0:
                return {
                    "side": "LONG",
                    "score": 0.8,
                    "metadata": {
                        "hurst": hurst,
                        "regime": "trending",
                    },
                }
            elif recent_direction < 0:
                return {
                    "side": "SHORT",
                    "score": 0.8,
                    "metadata": {
                        "hurst": hurst,
                        "regime": "trending",
                    },
                }

        # Mean-reversion regime signals can be added here
        # but typically used as filter, not direct signal

        return None

    def _calculate_hurst(self):
        """
        Calculate Hurst exponent using R/S analysis.
        Simplified implementation.
        """
        closes = np.array(list(self.closes)[-self.period :])

        if len(closes) < 20:
            return None

        # Calculate returns
        returns = np.diff(np.log(closes))

        if len(returns) < 10:
            return None

        # R/S analysis over different time scales
        rs_values = []
        ns = []

        for n in [10, 20, 30, 40]:
            if n > len(returns):
                continue

            # Split into chunks
            num_chunks = len(returns) // n
            if num_chunks == 0:
                continue

            chunk_rs = []
            for i in range(num_chunks):
                chunk = returns[i * n : (i + 1) * n]

                # Mean-adjusted cumulative sum
                mean_adj = chunk - np.mean(chunk)
                cumsum = np.cumsum(mean_adj)

                # Range
                R = np.max(cumsum) - np.min(cumsum)

                # Standard deviation
                S = np.std(chunk, ddof=1)

                if S > 0:
                    chunk_rs.append(R / S)

            if chunk_rs:
                rs_values.append(np.mean(chunk_rs))
                ns.append(n)

        if len(rs_values) < 2:
            return 0.5  # Default to random walk

        # Fit log(R/S) vs log(n)
        log_n = np.log(ns)
        log_rs = np.log(rs_values)

        # Linear regression slope = Hurst exponent
        slope = np.polyfit(log_n, log_rs, 1)[0]

        return max(0.0, min(1.0, slope))  # Clamp to [0, 1]
