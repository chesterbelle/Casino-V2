"""
====================================================
🏦 CONFIGURACIÓN DE EXCHANGES — CASINO V2
====================================================

Parámetros de conexión a exchanges y símbolos.
"""

import os
from typing import Literal

# =====================================================
# 🏦 EXCHANGE ACTIVO
# =====================================================

_EXCHANGE_ENV_VAR = "CASINO_EXCHANGE"
_ALLOWED_EXCHANGES = {"KRAKEN", "BINANCE", "BYBIT", "HYPERLIQUID"}


def _get_exchange(
    default: Literal["KRAKEN", "BINANCE", "BYBIT", "HYPERLIQUID"],
) -> Literal["KRAKEN", "BINANCE", "BYBIT", "HYPERLIQUID"]:
    value = os.getenv(_EXCHANGE_ENV_VAR)
    if value:
        normalized = value.strip().upper()
        if normalized not in _ALLOWED_EXCHANGES:
            raise ValueError(f"Exchange inválido '{value}'. Usa uno de {_ALLOWED_EXCHANGES}.")
        return normalized  # type: ignore[return-value]
    return default


# Exchange activo (se usa en modos testing/live)
# Opciones actuales:
#  - "KRAKEN"     → Kraken Futures (demo en testing, real en live)
#  - "BINANCE"    → Binance Futures
#  - "BYBIT"      → Bybit (testnet en testing, real en live)
#  - "HYPERLIQUID"→ Hyperliquid
EXCHANGE: Literal["KRAKEN", "BINANCE", "BYBIT", "HYPERLIQUID"] = _get_exchange("BYBIT")

# Perfil del exchange (usa el JSON de tables/data/exchange_profiles)
EXCHANGE_PROFILE = "kraken_futures_demo"

# Símbolo y timeframe por defecto
SYMBOL = "BTC/USD"
TIMEFRAME = "15m"

# Moneda base para cálculos de balance y PnL
BASE_CURRENCY = "USDT"


# =====================================================
# KRAKEN FUTURES — PARÁMETROS DEMO/LIVE
# =====================================================

KRAKEN_FUTURES_BASE_URL = "https://demo-futures.kraken.com/derivatives/api/"
KRAKEN_FUTURES_CHARTS_URL = "https://demo-futures.kraken.com/api/charts/v1/"
KRAKEN_FUTURES_SYMBOL = "LTC"
KRAKEN_FUTURES_INTERVAL = "1m"
KRAKEN_POLL_INTERVAL = 2.0
KRAKEN_FUTURES_API_KEY = None
KRAKEN_FUTURES_API_SECRET = None


# =====================================================
# BINANCE FUTURES — PARÁMETROS TESTNET/LIVE
# =====================================================

BINANCE_BASE_URL = "https://testnet.binancefuture.com"
BINANCE_DEFAULT_SYMBOL = "BTC/USDT"
BINANCE_DEFAULT_INTERVAL = "15m"
BINANCE_POLL_INTERVAL = 2.0
BINANCE_API_KEY = None
BINANCE_API_SECRET = None


# =====================================================
# HYPERLIQUID — PARÁMETROS LIVE
# =====================================================

HYPERLIQUID_BASE_URL = "https://api.hyperliquid.xyz"
HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"
HYPERLIQUID_DEFAULT_SYMBOL = "LTC"
HYPERLIQUID_DEFAULT_INTERVAL = "1m"
HYPERLIQUID_POLL_INTERVAL = 1.0
HYPERLIQUID_API_KEY = None
HYPERLIQUID_API_SECRET = None
HYPERLIQUID_VAULT_ADDRESS = None  # Para vault trading


# =====================================================
# BYBIT — PARÁMETROS TESTNET/LIVE
# =====================================================

BYBIT_BASE_URL_TESTNET = "https://api-testnet.bybit.com"
BYBIT_BASE_URL_LIVE = "https://api.bybit.com"
BYBIT_DEFAULT_SYMBOL = "BTC/USDT:USDT"
BYBIT_DEFAULT_INTERVAL = "1m"
BYBIT_POLL_INTERVAL = 2.0
BYBIT_API_KEY = None
BYBIT_API_SECRET = None


# =====================================================
# ASTERDEX — PARÁMETROS PAPER/LIVE
# =====================================================

ASTER_BASE_URL = "https://fapi.asterdex.com"
ASTER_WS_URL = "wss://fstream.asterdex.com"
ASTER_DEFAULT_SYMBOL = "LTC"
ASTER_DEFAULT_INTERVAL = "1m"
ASTER_RECV_WINDOW = 5000
ASTER_POLL_INTERVAL = 2.0
ASTER_API_KEY = None
ASTER_API_SECRET = None
