from typing import Dict, Optional

from core.interfaces.abstract_sensor import AbstractSensorV3


class FootprintAbsorptionV3(AbstractSensorV3):
    """
    Footprint Absorption Sensor.

    Detects absorption: High volume traded at a price level but price fails to continue.

    Logic:
    - High Ask Volume at the High of the candle -> Absorption (Sellers absorbing Buyers) -> SHORT signal.
    - High Bid Volume at the Low of the candle -> Absorption (Buyers absorbing Sellers) -> LONG signal.
    """

    def __init__(self, min_volume_ratio: float = 2.0):
        self.min_volume_ratio = min_volume_ratio

    @property
    def name(self) -> str:
        return "FootprintAbsorption"

    def calculate(self, context: Dict[str, Optional[dict]]) -> Optional[dict]:
        candle = context.get("1m")
        if not candle:
            return None

        profile = candle.get("profile")
        if not profile:
            return None

        high = candle["high"]
        low = candle["low"]
        avg_vol = candle["volume"] / len(profile) if profile else 1.0

        # Check High for Absorption (Sellers absorbing Buyers)
        # Look for high ASK volume at the top price level
        high_vol = profile.get(high, {"bid": 0, "ask": 0})
        if high_vol["ask"] > avg_vol * self.min_volume_ratio:
            # High volume at top, potential reversal
            return {"side": "SHORT", "score": 1.0, "metadata": {"type": "Absorption at High", "vol": high_vol["ask"]}}

        # Check Low for Absorption (Buyers absorbing Sellers)
        # Look for high BID volume at the bottom price level
        low_vol = profile.get(low, {"bid": 0, "ask": 0})
        if low_vol["bid"] > avg_vol * self.min_volume_ratio:
            # High volume at bottom, potential reversal
            return {"side": "LONG", "score": 1.0, "metadata": {"type": "Absorption at Low", "vol": low_vol["bid"]}}

        return None
