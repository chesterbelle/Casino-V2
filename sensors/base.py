"""
Base Class for V3 Sensors.
"""

from abc import ABC, abstractmethod
from typing import Optional


class SensorV3(ABC):
    """
    Abstract Base Class for V3 Sensors.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Sensor Name."""
        pass

    @abstractmethod
    def calculate(self, candle: dict) -> Optional[dict]:
        """
        Calculate signal based on candle.
        Returns dict with keys: 'side', 'score', 'metadata' or None.
        """
        pass

    async def emit_signal(self, side: str, score: float = 1.0, metadata: Optional[dict] = None):
        """Emit a trading signal."""
        from core.events import SignalEvent

        signal = SignalEvent(
            timestamp=self.last_candle["timestamp"],
            symbol=self.symbol,
            side=side,
            sensor_id=self.__class__.__name__,  # Use class name as sensor ID
            score=score,
            metadata=metadata,
        )
        await self.engine.dispatch(signal)
