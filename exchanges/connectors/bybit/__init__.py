"""
Bybit Futures Connector Package.

This package provides a connector for Bybit Futures exchange (USDT Perpetual).

Main advantages over Kraken:
- Native TP/SL support (no OCO Monitor needed)
- Modern V5 API
- More stable testnet
- Better documentation

Usage:
    >>> from exchanges.connectors.bybit import BybitConnector
    >>> connector = BybitConnector(mode="testing")
    >>> await connector.connect()
    >>> order = await connector.create_order_with_tpsl(
    ...     symbol="BTC/USD:USD",
    ...     side="buy",
    ...     amount=0.01,
    ...     order_type="market",
    ...     tp_price=50000,
    ...     sl_price=48000
    ... )
"""

from .bybit_connector import BybitConnector
from .bybit_constants import (
    BASE_CURRENCY,
    BYBIT_DEFAULT_CONFIG,
    BYBIT_LIVE_URL,
    BYBIT_TESTNET_URL,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    POSITION_MODE_ONE_WAY,
    TIME_IN_FORCE_GTC,
    TPSL_MODE_FULL,
    denormalize_symbol,
    get_urls,
    normalize_symbol,
)

__all__ = [
    "BybitConnector",
    "normalize_symbol",
    "denormalize_symbol",
    "get_urls",
    "BASE_CURRENCY",
    "BYBIT_DEFAULT_CONFIG",
    "BYBIT_TESTNET_URL",
    "BYBIT_LIVE_URL",
    "ORDER_TYPE_MARKET",
    "ORDER_TYPE_LIMIT",
    "POSITION_MODE_ONE_WAY",
    "TIME_IN_FORCE_GTC",
    "TPSL_MODE_FULL",
]
