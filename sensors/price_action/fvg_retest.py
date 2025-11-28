from collections import deque
from typing import Dict, List, Optional

import numpy as np


class FVGRetest:
    """Detects a retest of a Fair Value Gap (FVG).

    An FVG is created when there is a large price move with a gap between the
    wicks of the previous and next candles. This sensor identifies FVGs and
    signals when price returns to the gap zone and rejects it.
    """

    def __init__(self, min_gap_pct: float = 0.001, buffer_size: int = 100):
        self.min_gap_pct = min_gap_pct
        self.candle_buffer = deque(maxlen=buffer_size)
        self.active_fvgs: List[Dict] = []  # List of active FVGs

    def _detect(self, candles: np.ndarray) -> Optional[Dict]:
        # candles shape: (N, 6) -> [timestamp, open, high, low, close, volume]
        if candles.shape[0] < 3:
            return None

        # 1. Detect NEW FVGs from the *previous* completed 3-candle sequence
        # We look at candles[-4], [-3], [-2] to confirm FVG at [-3]
        # But to be simple, let's just look at the sequence ending at -2 (completed)

        # Sequence: A (prev_prev), B (prev), C (current)
        # Actually, FVG is formed by A, B, C. Gap is between A's wick and C's wick.
        # We need to detect if FVG was formed recently.

        # Let's scan the buffer for active FVGs if we haven't already.
        # Optimization: Just check if a new FVG was formed by the candle that just closed (index -2).
        # Sequence: -4, -3, -2.
        if candles.shape[0] >= 4:
            c1 = candles[-4]  # Candle 1
            c2 = candles[-3]  # Candle 2 (The big move)
            c3 = candles[-2]  # Candle 3

            # Bullish FVG: C1 High < C3 Low (Gap exists)
            if c1[2] < c3[3]:
                gap_size = (c3[3] - c1[2]) / c1[2]
                if gap_size > self.min_gap_pct:
                    self.active_fvgs.append(
                        {"type": "bullish", "top": c3[3], "bottom": c1[2], "created_at": c2[0], "filled": False}
                    )

            # Bearish FVG: C1 Low > C3 High (Gap exists)
            if c1[3] > c3[2]:
                gap_size = (c1[3] - c3[2]) / c3[2]
                if gap_size > self.min_gap_pct:
                    self.active_fvgs.append(
                        {"type": "bearish", "top": c1[3], "bottom": c3[2], "created_at": c2[0], "filled": False}
                    )

        # 2. Prune filled/old FVGs
        # (For simplicity, we keep them until filled or buffer overflow, but here we just keep last 5)
        if len(self.active_fvgs) > 5:
            self.active_fvgs.pop(0)

        # 3. Check for Retest in CURRENT candle (index -1)
        cur = candles[-1]
        cur_low = cur[3]
        cur_high = cur[2]
        cur_close = cur[4]

        for fvg in self.active_fvgs:
            if fvg["filled"]:
                continue

            # Skip if already signaled for this FVG (one-shot per FVG instance)
            if fvg.get("signaled", False):
                # Check if we should reset signal?
                # For now, strict one-shot per FVG creation.
                # But we also need to check if it gets filled.
                if fvg["type"] == "bullish":
                    if cur_close < fvg["bottom"]:
                        fvg["filled"] = True
                elif fvg["type"] == "bearish":
                    if cur_close > fvg["top"]:
                        fvg["filled"] = True
                continue

            if fvg["type"] == "bullish":
                # Price dips into FVG zone (between bottom and top)
                if cur_low <= fvg["top"] and cur_low >= fvg["bottom"]:
                    fvg["signaled"] = True  # Mark as signaled
                    return {
                        "side": "LONG",
                        "features": {"type": "fvg_retest_bullish", "fvg_top": fvg["top"], "fvg_bottom": fvg["bottom"]},
                    }
                # If price crashes below bottom, FVG is invalid/filled
                if cur_close < fvg["bottom"]:
                    fvg["filled"] = True

            elif fvg["type"] == "bearish":
                # Price rallies into FVG zone
                if cur_high >= fvg["bottom"] and cur_high <= fvg["top"]:
                    fvg["signaled"] = True  # Mark as signaled
                    return {
                        "side": "SHORT",
                        "features": {"type": "fvg_retest_bearish", "fvg_top": fvg["top"], "fvg_bottom": fvg["bottom"]},
                    }
                # If price closes above top, FVG is invalid/filled
                if cur_close > fvg["top"]:
                    fvg["filled"] = True

        return None

    def check_signal(self, candle: dict) -> Optional[Dict]:
        """Wrapper called by SensorManager."""
        self.candle_buffer.append(
            [
                candle.get("timestamp"),
                float(candle["open"]),
                float(candle["high"]),
                float(candle["low"]),
                float(candle["close"]),
                float(candle.get("volume", 0)),
            ]
        )
        if len(self.candle_buffer) < 4:
            return None
        candles_array = np.array(list(self.candle_buffer))
        signal = self._detect(candles_array)
        if signal:
            signal["timestamp"] = candle["timestamp"]
            signal["symbol"] = candle.get("symbol")
            signal["timeframe"] = candle.get("timeframe")
        return signal
