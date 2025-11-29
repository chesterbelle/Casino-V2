"""
Base Strategy Interface for Casino-V3.
"""
import logging
from abc import ABC, abstractmethod
from core.v3.events import TickEvent, OrderBookEvent, OrderUpdateEvent

logger = logging.getLogger(__name__)

class StrategyV3(ABC):
    def __init__(self, engine):
        self.engine = engine
        self.active = False

    async def on_start(self):
        """Called when the engine starts."""
        self.active = True
        logger.info(f"🚀 Strategy {self.__class__.__name__} started")

    async def on_stop(self):
        """Called when the engine stops."""
        self.active = False
        logger.info(f"🛑 Strategy {self.__class__.__name__} stopped")

    @abstractmethod
    async def on_tick(self, tick: TickEvent):
        """Called on every price update."""
        pass

    async def on_order_book(self, event: OrderBookEvent):
        """Called on order book update (optional)."""
        pass

    async def on_order_update(self, event: OrderUpdateEvent):
        """Called on order status update (optional)."""
        pass
