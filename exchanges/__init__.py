"""
Exchange integrations for Casino V2.

This package contains all exchange-related functionality:
- connectors/: Exchange API connectors (Kraken, Binance, etc.)
- adapters/: CCXT adapter and state synchronization
- resilience/: Resilient connector wrappers for fault tolerance
"""

from .adapters.ccxt_adapter import CCXTAdapter
from .connectors import KrakenConnector

__all__ = [
    "CCXTAdapter",
    "KrakenConnector",
]
