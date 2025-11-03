"""
Kraken Futures Constants and Configuration.

This module contains all Kraken-specific constants, URLs, and configuration
extracted from the legacy implementation.

URLs verified and working as of 2025-11-03.
"""

# =========================================================
# 🌐 API URLS
# =========================================================

# Kraken Futures Demo (Testnet) URLs
KRAKEN_DEMO_URLS = {
    "api": {
        "public": "https://demo-futures.kraken.com/derivatives/api/",
        "private": "https://demo-futures.kraken.com/derivatives/api/",
    }
}

# Kraken Futures Production (Mainnet) URLs
KRAKEN_MAINNET_URLS = {
    "api": {
        "public": "https://futures.kraken.com/derivatives/api/",
        "private": "https://futures.kraken.com/derivatives/api/",
    }
}

# =========================================================
# ⚙️ EXCHANGE CONFIGURATION
# =========================================================

# Default CCXT configuration for Kraken Futures
KRAKEN_DEFAULT_CONFIG = {
    "enableRateLimit": True,
    "options": {
        "defaultType": "future",  # Kraken Futures
        "watchBalance": True,  # Enable balance WebSocket
    },
}

# =========================================================
# 💱 SYMBOL MAPPING
# =========================================================

# Kraken uses "PF_" prefix for perpetual futures
# Standard format → Kraken format
SYMBOL_MAPPING = {
    "BTC/USD": "PF_XBTUSD",  # Bitcoin
    "ETH/USD": "PF_ETHUSD",  # Ethereum
    "SOL/USD": "PF_SOLUSD",  # Solana
    "XRP/USD": "PF_XRPUSD",  # Ripple
    "ADA/USD": "PF_ADAUSD",  # Cardano
    "DOGE/USD": "PF_DOGEUSD",  # Dogecoin
    "MATIC/USD": "PF_MATICUSD",  # Polygon
    "DOT/USD": "PF_DOTUSD",  # Polkadot
    "AVAX/USD": "PF_AVAXUSD",  # Avalanche
    "LINK/USD": "PF_LINKUSD",  # Chainlink
}

# Reverse mapping: Kraken format → Standard format
REVERSE_SYMBOL_MAPPING = {v: k for k, v in SYMBOL_MAPPING.items()}

# =========================================================
# ⏱️ TIMEFRAME MAPPING
# =========================================================

# CCXT timeframe → Kraken timeframe
TIMEFRAME_MAPPING = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}

# =========================================================
# 🔢 RATE LIMITS
# =========================================================

# Kraken rate limits (requests per second)
RATE_LIMIT_PUBLIC = 10  # Public endpoints
RATE_LIMIT_PRIVATE = 5  # Private endpoints (orders, balance, etc.)

# =========================================================
# 💰 MARKET INFO
# =========================================================

# Base currency for Kraken Futures
BASE_CURRENCY = "USD"

# Market type
MARKET_TYPE = "future"

# Minimum order sizes (in base currency)
MIN_ORDER_SIZE = {
    "BTC/USD": 0.0001,
    "ETH/USD": 0.001,
    "SOL/USD": 0.1,
    "XRP/USD": 1.0,
    "ADA/USD": 1.0,
    "DOGE/USD": 10.0,
}

# =========================================================
# 🔧 WEBSOCKET CONFIGURATION
# =========================================================

# WebSocket URLs
WS_URL_DEMO = "wss://demo-futures.kraken.com/ws/v1"
WS_URL_MAINNET = "wss://futures.kraken.com/ws/v1"

# WebSocket channels
WS_CHANNELS = {
    "ticker": "ticker",
    "book": "book",
    "trade": "trade",
    "ohlc": "ohlc",  # OHLCV candles
    "balances": "balances",
    "fills": "fills",  # Trade fills
    "open_orders": "open_orders",
}

# =========================================================
# 🚨 ERROR CODES
# =========================================================

# Kraken-specific error codes
ERROR_CODES = {
    "authenticationError": "Invalid API key or signature",
    "insufficientFunds": "Insufficient balance",
    "invalidOrder": "Invalid order parameters",
    "rateLimitExceeded": "Rate limit exceeded",
    "marketClosed": "Market is closed",
    "orderNotFound": "Order not found",
}

# =========================================================
# 🎯 HELPER FUNCTIONS
# =========================================================


def get_urls(testnet: bool = True) -> dict:
    """
    Get Kraken API URLs based on environment.

    Args:
        testnet: If True, return demo URLs; if False, return mainnet URLs

    Returns:
        Dictionary with API URLs
    """
    return KRAKEN_DEMO_URLS if testnet else KRAKEN_MAINNET_URLS


def get_ws_url(testnet: bool = True) -> str:
    """
    Get Kraken WebSocket URL based on environment.

    Args:
        testnet: If True, return demo URL; if False, return mainnet URL

    Returns:
        WebSocket URL string
    """
    return WS_URL_DEMO if testnet else WS_URL_MAINNET


def normalize_symbol(symbol: str) -> str:
    """
    Convert standard symbol format to Kraken format.

    Args:
        symbol: Standard format (e.g., "BTC/USD")

    Returns:
        Kraken format (e.g., "PF_XBTUSD")

    Raises:
        ValueError: If symbol is not supported
    """
    if symbol in SYMBOL_MAPPING:
        return SYMBOL_MAPPING[symbol]
    raise ValueError(f"Symbol {symbol} not supported on Kraken")


def denormalize_symbol(kraken_symbol: str) -> str:
    """
    Convert Kraken symbol format to standard format.

    Args:
        kraken_symbol: Kraken format (e.g., "PF_XBTUSD")

    Returns:
        Standard format (e.g., "BTC/USD")

    Raises:
        ValueError: If symbol is not recognized
    """
    if kraken_symbol in REVERSE_SYMBOL_MAPPING:
        return REVERSE_SYMBOL_MAPPING[kraken_symbol]
    raise ValueError(f"Kraken symbol {kraken_symbol} not recognized")
