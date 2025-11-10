"""
Bybit Futures Constants and Configuration.

This module contains all Bybit-specific constants, configuration,
and symbol normalization functions.
"""

from typing import Dict, Literal

# =========================================================
# 🌐 EXCHANGE URLS
# =========================================================

BYBIT_DEMO_URL = "https://api-demo.bybit.com"  # Demo Trading (real prices, simulated trades)
BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"  # Testnet (fake prices, for testing features)
BYBIT_LIVE_URL = "https://api.bybit.com"


def get_urls(mode: Literal["demo", "live"]) -> Dict[str, str]:
    """
    Get Bybit URLs based on mode.

    Args:
        mode: "demo" for demo trading (real prices), "live" for production

    Returns:
        Dict with API URLs
    """
    if mode == "demo":
        return {
            "api": BYBIT_DEMO_URL,  # Use Demo Trading API (real market prices)
            "ws": "wss://stream-demo.bybit.com",  # Private streams
            "ws_public": "wss://stream.bybit.com",  # Public streams (same as mainnet)
        }
    else:
        return {
            "api": BYBIT_LIVE_URL,
            "ws": "wss://stream.bybit.com",
        }


# =========================================================
# ⚙️  EXCHANGE CONFIGURATION
# =========================================================

BYBIT_DEFAULT_CONFIG = {
    "enableRateLimit": True,
    "rateLimit": 50,  # ms between requests
    "timeout": 30000,  # 30 seconds
    "options": {
        "defaultType": "linear",  # USDT Perpetual
        "defaultSubType": "linear",
    },
}

# Base currency for balance
BASE_CURRENCY = "USDT"

# =========================================================
# 🔄 SYMBOL NORMALIZATION
# =========================================================


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol from bot format to Bybit format.

    Bot format: "BTC/USD:USD", "ETH/USD:USD", "LTC/USD:USD"
    Bybit format: "BTC/USDT:USDT", "ETH/USDT:USDT", "LTC/USDT:USDT"

    Args:
        symbol: Symbol in bot format (e.g., "BTC/USD:USD")

    Returns:
        Symbol in Bybit format (e.g., "BTC/USDT:USDT")

    Examples:
        >>> normalize_symbol("BTC/USD:USD")
        'BTC/USDT:USDT'
        >>> normalize_symbol("ETH/USD:USD")
        'ETH/USDT:USDT'
        >>> normalize_symbol("LTC/USD:USD")
        'LTC/USDT:USDT'
    """
    # If already in correct format, return as is
    if symbol.endswith("/USDT:USDT"):
        return symbol

    # Extract base currency
    if "/" in symbol:
        base = symbol.split("/")[0]
    else:
        # Assume it's just the base currency
        return f"{symbol}/USDT:USDT"

    # Bybit uses USDT for perpetuals
    return f"{base}/USDT:USDT"


def denormalize_symbol(bybit_symbol: str) -> str:
    """
    Denormalize symbol from Bybit format to bot format.

    Bybit format: "BTCUSDT", "ETHUSDT", "LTCUSDT"
    Bot format: "BTC/USD:USD", "ETH/USD:USD", "LTC/USD:USD"

    Args:
        bybit_symbol: Symbol in Bybit format (e.g., "BTCUSDT")

    Returns:
        Symbol in bot format (e.g., "BTC/USD:USD")

    Examples:
        >>> denormalize_symbol("BTCUSDT")
        'BTC/USD:USD'
        >>> denormalize_symbol("ETHUSDT")
        'ETH/USD:USD'
        >>> denormalize_symbol("LTCUSDT")
        'LTC/USD:USD'
    """
    # Remove USDT suffix
    if bybit_symbol.endswith("USDT"):
        base = bybit_symbol[:-4]
        return f"{base}/USD:USD"

    # If not USDT pair, return as is
    return bybit_symbol


# =========================================================
# 📊 ORDER PARAMETERS
# =========================================================

# Position modes
POSITION_MODE_ONE_WAY = 0
POSITION_MODE_HEDGE_BUY = 1
POSITION_MODE_HEDGE_SELL = 2

# Order types
ORDER_TYPE_MARKET = "Market"
ORDER_TYPE_LIMIT = "Limit"

# Time in force
TIME_IN_FORCE_GTC = "GTC"  # Good Till Cancel
TIME_IN_FORCE_IOC = "IOC"  # Immediate or Cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or Kill

# TP/SL modes
TPSL_MODE_FULL = "Full"  # Full position TP/SL
TPSL_MODE_PARTIAL = "Partial"  # Partial position TP/SL

# Trigger types
TRIGGER_BY_LAST_PRICE = "LastPrice"
TRIGGER_BY_INDEX_PRICE = "IndexPrice"
TRIGGER_BY_MARK_PRICE = "MarkPrice"
