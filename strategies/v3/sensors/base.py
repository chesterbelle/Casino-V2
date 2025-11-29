"""
Base Class for V3 Sensors.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional

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
