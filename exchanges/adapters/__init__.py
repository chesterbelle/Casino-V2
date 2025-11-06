"""
Exchange adapters for Casino V2.

Adapters provide a unified interface to different exchange implementations.
"""

from .ccxt_adapter import CCXTAdapter
from .exchange_state_sync import ExchangeStateSync

__all__ = [
    "CCXTAdapter",
    "ExchangeStateSync",
]
