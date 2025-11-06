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

"""

import warnings

# Re-export from new location
from exchanges.connectors import (  # noqa: E402
    BaseConnector,
    KrakenConnector,
    ResilientConnector,
)

warnings.warn(
    "The 'tables.connectors' module is deprecated and will be removed in v2.0. "
    "Please use 'exchanges.connectors' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BaseConnector",
    "KrakenConnector",
    "ResilientConnector",
]
