"""
Exchange Connectors Module.

This module provides standardized connectors for different cryptocurrency exchanges.
Each connector implements the BaseConnector interface and handles exchange-specific
communication, authentication, and data normalization.

Available Connectors:
    - KrakenConnector: Kraken Futures (testnet + mainnet)
    - BinanceConnector: Binance Futures (coming in v1.9)
    - HyperliquidConnector: Hyperliquid (coming in v2.0)

Usage:
    ```python
    from tables.connectors import BaseConnector, KrakenConnector

    # Create connector
    connector = KrakenConnector(
        api_key="your_key",
        secret="your_secret",
        testnet=True
    )

    # Connect
    await connector.connect()

    # Use connector
    candles = await connector.fetch_ohlcv("BTC/USD", "1m")
    balance = await connector.fetch_balance()

    # Close
    await connector.close()
    ```

Architecture:
    TableCCXTPro (Mesa) uses BaseConnector interface
    → Specific connector implementation (KrakenConnector, etc.)
    → Exchange API (REST + WebSocket)
"""

from .connector_base import BaseConnector
from .kraken import KrakenConnector

__all__ = ["BaseConnector", "KrakenConnector"]
