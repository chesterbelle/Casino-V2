"""
Exchange Connectors Module.

This module provides standardized connectors for different cryptocurrency exchanges.
Each connector implements the BaseConnector interface and handles exchange-specific
communication, authentication, and data normalization.

Available Connectors:
    - KrakenConnector: Kraken Futures (testing + live mode)
    - BinanceConnector: Placeholder (v2.0) — raises NotImplementedError
    - HyperliquidConnector: Placeholder (v2.1) — raises NotImplementedError
    - ResilientConnector: Wrapper que agrega resiliencia a cualquier conector

Usage:
    ```python
    from tables.connectors import BaseConnector, KrakenConnector, ResilientConnector

    # Create connector
    connector = KrakenConnector(
        api_key="your_key",
        secret="your_secret",
        testnet=True
    )

    # Wrap with resilience (optional)
    resilient_connector = ResilientConnector(
        connector=connector,
        state_recovery_config={'state_dir': './state'}
    )

    # Connect
    await resilient_connector.connect()

    # Use connector (transparente)
    candles = await resilient_connector.fetch_ohlcv("BTC/USD", "1m")
    balance = await resilient_connector.fetch_balance()

    # Close
    await resilient_connector.close()
    ```

Architecture:
    CCXTAdapter (Mesa) uses BaseConnector interface
    → Specific connector implementation (KrakenConnector, etc.)
    → Exchange API (REST + WebSocket)
"""

from .binance import BinanceConnector, BinanceNativeConnector
from .bybit import BybitConnector
from .connector_base import BaseConnector
from .hyperliquid import HyperliquidNativeConnector
from .kraken import KrakenConnector
from .resilient_connector import ResilientConnector

__all__ = [
    "BaseConnector",
    "KrakenConnector",
    "BinanceConnector",
    "BinanceNativeConnector",
    "HyperliquidNativeConnector",
    "BybitConnector",
    "ResilientConnector",
]
