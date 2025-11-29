"""
Event definitions for Casino-V3 Event-Driven Architecture.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional


class EventType(Enum):
    TICK = auto()
    ORDER_BOOK = auto()
    ORDER_UPDATE = auto()
    CANDLE = auto()
    SIGNAL = auto()
    AGGREGATED_SIGNAL = auto()
    ERROR = auto()
    SYSTEM = auto()


@dataclass
class Event:
    type: EventType
    timestamp: float


@dataclass
class TickEvent(Event):
    symbol: str
    price: float
    volume: float = 0.0

    def __post_init__(self):
        self.type = EventType.TICK


@dataclass
class OrderBookEvent(Event):
    symbol: str
    bids: list  # [[price, amount], ...]
    asks: list  # [[price, amount], ...]

    def __post_init__(self):
        self.type = EventType.ORDER_BOOK


@dataclass
class OrderUpdateEvent(Event):
    order_id: str
    symbol: str
    status: str  # 'open', 'closed', 'canceled', 'rejected'
    filled: float
    remaining: float
    price: float
    side: str
    client_order_id: Optional[str] = None

    def __post_init__(self):
        self.type = EventType.ORDER_UPDATE


@dataclass
class ErrorEvent(Event):
    source: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.type = EventType.ERROR


@dataclass
class SignalEvent(Event):
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    strategy_name: str
    score: float = 1.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.type = EventType.SIGNAL


@dataclass
class CandleEvent(Event):
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        self.type = EventType.CANDLE
