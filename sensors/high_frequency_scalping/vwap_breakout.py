"""
VWAP Breakout - Volatility Expansion

Captures explosive moves away from fair value (VWAP).
Similar to Keltner Breakout but uses VWAP bands which respect volume distribution.

Logic:
- Bands: VWAP +/- 1.0 Standard Deviation
- Trigger: Price breaks band with volume
- Filter: ADX > 20 (Trend strength)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class VWAPBreakout:
    """
    VWAP Breakout Sensor.

    Detects volatility expansion away from VWAP.
    """

    def __init__(
        self,
        std_dev_mult: float = 1.0,
        volume_factor: float = 1.2,
        adx_threshold: float = 20.0,
        reset_period: int = 1440,
    ):
        """
        Args:
            std_dev_mult: Standard deviations for bands (default 1.0)
            volume_factor: Volume required vs average (default 1.2)
            adx_threshold: Minimum ADX to confirm trend (default 20.0)
        """
        self.std_dev_mult = std_dev_mult
        self.volume_factor = volume_factor
        self.adx_threshold = adx_threshold

        # VWAP State
        self.cum_vol = 0.0
        self.cum_vol_price = 0.0
        self.cum_vol_price_sq = 0.0  # For variance calculation
        self.start_timestamp = None

        # ADX/Volume State
        self.volumes = deque(maxlen=20)
        self.closes = deque(maxlen=28)  # Need 2x period for ADX
        self.highs = deque(maxlen=28)
        self.lows = deque(maxlen=28)

        # ADX internal state
        self.prev_tr = None
        self.prev_dm_plus = None
        self.prev_dm_minus = None
        self.prev_adx = None

    def _calculate_adx(self, high, low, close) -> float:
        # Simplified ADX calculation
        if len(self.closes) < 2:
            return 0.0

        prev_close = self.closes[-1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))

        up_move = high - self.highs[-1]
        down_move = self.lows[-1] - low

        dm_plus = up_move if up_move > down_move and up_move > 0 else 0
        dm_minus = down_move if down_move > up_move and down_move > 0 else 0

        if self.prev_tr is None:
            self.prev_tr = tr
            self.prev_dm_plus = dm_plus
            self.prev_dm_minus = dm_minus
            return 0.0

        alpha = 1.0 / 14
        self.prev_tr = self.prev_tr * (1 - alpha) + tr
        self.prev_dm_plus = self.prev_dm_plus * (1 - alpha) + dm_plus
        self.prev_dm_minus = self.prev_dm_minus * (1 - alpha) + dm_minus

        if self.prev_tr == 0:
            return 0.0

        di_plus = (self.prev_dm_plus / self.prev_tr) * 100
        di_minus = (self.prev_dm_minus / self.prev_tr) * 100

        sum_di = di_plus + di_minus
        dx = (abs(di_plus - di_minus) / sum_di) * 100 if sum_di > 0 else 0

        if self.prev_adx is None:
            self.prev_adx = dx
        else:
            self.prev_adx = self.prev_adx * (1 - alpha) + dx * alpha

        return self.prev_adx

    def _update_vwap(self, high, low, close, volume, timestamp):
        tp = (high + low + close) / 3.0

        # Reset logic (daily)
        current_day = int(timestamp / (1000 * 60 * 60 * 24))
        if self.start_timestamp is None or current_day > self.start_timestamp:
            self.cum_vol = 0.0
            self.cum_vol_price = 0.0
            self.cum_vol_price_sq = 0.0
            self.start_timestamp = current_day

        self.cum_vol += volume
        self.cum_vol_price += tp * volume
        self.cum_vol_price_sq += (tp * tp) * volume

        if self.cum_vol == 0:
            return tp, 0.0

        vwap = self.cum_vol_price / self.cum_vol

        # Standard Deviation calculation
        # Variance = E[X^2] - (E[X])^2
        mean_sq = self.cum_vol_price_sq / self.cum_vol
        variance = mean_sq - (vwap * vwap)
        std_dev = np.sqrt(max(0, variance))

        return vwap, std_dev

    def check_signal(self, candle: dict) -> Optional[Dict]:
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        volume = float(candle["volume"])
        timestamp = candle["timestamp"]

        # Update ADX buffers BEFORE calculation
        # But we need previous values for calculation, so append AFTER
        # Actually standard practice is to use current values

        adx = self._calculate_adx(high, low, close)

        # Update buffers
        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        self.volumes.append(volume)

        # Update VWAP
        vwap, std_dev = self._update_vwap(high, low, close, volume, timestamp)

        if len(self.volumes) < 20:
            return None

        avg_volume = np.mean(self.volumes)

        # Logic
        upper_band = vwap + (std_dev * self.std_dev_mult)
        lower_band = vwap - (std_dev * self.std_dev_mult)

        # Filter: ADX must be strong
        if adx < self.adx_threshold:
            return None

        # Filter: Volume must be significant
        if volume < avg_volume * self.volume_factor:
            return None

        # LONG: Close breaks above Upper Band
        if close > upper_band:
            return {
                "timestamp": timestamp,
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "LONG",
                "range_score": 2,
                "features": {
                    "pattern": "vwap_breakout_long",
                    "adx": float(adx),
                    "vol_ratio": float(volume / avg_volume),
                },
            }

        # SHORT: Close breaks below Lower Band
        if close < lower_band:
            return {
                "timestamp": timestamp,
                "symbol": candle.get("symbol"),
                "timeframe": candle.get("timeframe"),
                "side": "SHORT",
                "range_score": 2,
                "features": {
                    "pattern": "vwap_breakout_short",
                    "adx": float(adx),
                    "vol_ratio": float(volume / avg_volume),
                },
            }

        return None
