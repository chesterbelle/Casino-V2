"""
Kraken Futures Connector Module.

This module provides a connector for Kraken Futures exchange (testnet + mainnet).

Usage:
    ```python
    from tables.connectors.kraken import KrakenConnector

    connector = KrakenConnector(
        api_key="your_key",
        secret="your_secret",
        testnet=True
    )

    await connector.connect()
    candles = await connector.fetch_ohlcv("BTC/USD", "1m")
    await connector.close()
    ```
"""

from .kraken_connector import KrakenConnector

__all__ = ["KrakenConnector"]
