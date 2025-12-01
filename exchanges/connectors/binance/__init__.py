"""
Binance Futures Connector Package.

This package provides a connector for Binance Futures exchange (USDT Perpetual).

Main features:
- Testnet and Live trading support
- Native TP/SL support (3 separate orders)
- Modern API
- Full CCXT integration

Usage:
    >>> from exchanges.connectors.binance import BinanceConnector
    >>> connector = BinanceConnector(mode="testnet")
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

from .binance_connector import BinanceConnector
from .binance_constants import (
    BASE_CURRENCY,
    BINANCE_DEFAULT_CONFIG,
    BINANCE_LIVE_URL,
    BINANCE_TESTNET_URL,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    POSITION_MODE_ONE_WAY,
    TIME_IN_FORCE_GTC,
    WORKING_TYPE_CONTRACT_PRICE,
    WORKING_TYPE_MARK_PRICE,
    denormalize_symbol,
    get_urls,
    normalize_symbol,
)
from .binance_native_connector import BinanceNativeConnector

__all__ = [
    "BinanceConnector",
    "BinanceNativeConnector",
    "normalize_symbol",
    "denormalize_symbol",
    "get_urls",
    "BASE_CURRENCY",
    "BINANCE_DEFAULT_CONFIG",
    "BINANCE_TESTNET_URL",
    "BINANCE_LIVE_URL",
    "ORDER_TYPE_MARKET",
    "ORDER_TYPE_LIMIT",
    "ORDER_TYPE_STOP_MARKET",
    "ORDER_TYPE_TAKE_PROFIT_MARKET",
    "POSITION_MODE_ONE_WAY",
    "TIME_IN_FORCE_GTC",
    "WORKING_TYPE_MARK_PRICE",
    "WORKING_TYPE_CONTRACT_PRICE",
]
