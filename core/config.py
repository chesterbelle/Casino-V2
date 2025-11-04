"""
====================================================
⚙️ CONFIGURACIÓN GENERAL — CASINO V2
====================================================

Este archivo define los parámetros globales de todo el sistema.
Piensa en él como la "ficha de entrada" del jugador:
describe cómo quiere jugar, en qué mesa, y con qué reglas.

Gemini, el Croupier y las Mesas leerán de aquí directamente.
====================================================
"""

from __future__ import annotations

import os
import sys
from typing import Literal

_MODE_ENV_VAR = "CASINO_MODE"
_EXCHANGE_ENV_VAR = "CASINO_EXCHANGE"
_LIVE_CONFIG_ENV = "CASINO_LIVE_TRADING_ENABLED_CONFIG"

_ALLOWED_MODES = {"backtest", "testing", "live"}
_ALLOWED_EXCHANGES = {"KRAKEN", "BINANCE", "HYPERLIQUID"}


def _get_mode(default: Literal["backtest", "testing", "live"]) -> Literal["backtest", "testing", "live"]:
    value = os.getenv(_MODE_ENV_VAR)
    if value:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_MODES:
            raise ValueError(f"Modo inválido '{value}'. Usa uno de {_ALLOWED_MODES}.")
        return normalized  # type: ignore[return-value]
    return default


def _get_exchange(default: Literal["KRAKEN", "BINANCE", "HYPERLIQUID"]) -> Literal["KRAKEN", "BINANCE", "HYPERLIQUID"]:
    value = os.getenv(_EXCHANGE_ENV_VAR)
    if value:
        normalized = value.strip().upper()
        if normalized not in _ALLOWED_EXCHANGES:
            raise ValueError(f"Exchange inválido '{value}'. Usa uno de {_ALLOWED_EXCHANGES}.")
        return normalized  # type: ignore[return-value]
    return default


# =====================================================
# 🎯 MODO DEL CASINO
# =====================================================
# Puede ser:
#  - "backtest" → usa dataset CSV y simula operaciones históricas
#  - "testing"  → conecta a exchanges demo/testnet (Kraken Demo)
#  - "live"     → trading real con dinero real (placeholder v2.4+)
MODE: Literal["backtest", "testing", "live"] = _get_mode("testing")

# Exchange activo (se usa en modos testing/live)
# Opciones actuales:
#  - "KRAKEN"     → Kraken Futures (demo en testing, real en live)
#  - "BINANCE"    → Binance Futures (placeholder)
#  - "HYPERLIQUID"→ Hyperliquid (placeholder)
EXCHANGE: Literal["KRAKEN", "BINANCE", "HYPERLIQUID"] = _get_exchange("KRAKEN")

# Perfil del exchange (usa el JSON de tables/data/exchange_profiles)
# Opciones: "asterdex_paper", "kraken_futures_demo", "binance_futures_testnet", "hyperliquid"
EXCHANGE_PROFILE = "kraken_futures_demo"

# Confirmación manual para live trading (dinero real)
LIVE_TRADING_ENABLED_DEFAULT = False
LIVE_TRADING_ENABLED = bool(
    LIVE_TRADING_ENABLED_DEFAULT or os.getenv(_LIVE_CONFIG_ENV, "false").strip().lower() == "true"
)
LIVE_CONFIRMATION_KEYWORD = "YES"
LIVE_ENV_FLAG = "CASINO_LIVE_TRADING_ENABLED"

# Ruta del dataset CSV (para modo backtest) — se utiliza tanto para Gemini
# como para Oscar. Cambia este archivo para alternar rápidamente entre datasets.
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"


# =====================================================
# ASTERDEX — PARÁMETROS PAPER/LIVE
# =====================================================
# Valores base para iniciar paper trading. Las claves reales deben
# configurarse via variables de entorno o .env (ver utils/aster_env_loader.py).
ASTER_BASE_URL = "https://fapi.asterdex.com"
ASTER_WS_URL = "wss://fstream.asterdex.com"
ASTER_DEFAULT_SYMBOL = "LTC"
ASTER_DEFAULT_INTERVAL = "1m"
ASTER_RECV_WINDOW = 5000
ASTER_POLL_INTERVAL = 2.0
ASTER_API_KEY = None
ASTER_API_SECRET = None


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
# ⏱️ CONTROL DE SESIONES LIVE
# =====================================================
# Delay entre iteraciones del loop live (segundos)
LIVE_SLEEP_SECONDS = 1.0

# Número máximo de velas a procesar antes de detener la sesión.
# Usa None (o valores <= 0) para dejarlo en ejecución indefinida.
# Para live trading inicial, limitar a sesiones cortas
LIVE_MAX_CANDLES = 30  # Prueba manual limitada a 30 velas


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
# 💰 CONFIGURACIÓN FINANCIERA
# =====================================================
# Capital inicial con el que empieza el jugador
# En live trading, se sincroniza con el balance real del exchange
STARTING_BALANCE = 10_000.0

# Tamaños relativos de TP y SL (expresados en proporción decimal)
# Ejemplo: 0.01 = 1% de take profit, 0.008 = 0.8% de stop loss
TAKE_PROFIT = 0.005  # 0.5% - Take profit más ajustado
STOP_LOSS = 0.015  # 1.5% - Stop loss más amplio (ratio 1:3)

# Fracción del criterio de Kelly a aplicar (1 = Kelly completo, 0.5 = medio Kelly)
# Para live trading, usar valores conservadores
KELLY_FRACTION = 0.1  # Más conservador para live trading


# =====================================================
# 🧠 GEMINI — PARÁMETROS DE APRENDIZAJE
# =====================================================
# Ventana de aprendizaje (cuántos resultados recuerda por bucket)
WINDOW_SIZE = 120

# Mínimo de muestras necesarias por bucket para confiar en la estadística
MIN_SUPPORT = 20

# Umbral mínimo de diferencia estadística para considerar una mesa “caliente”
# Parámetros bayesianos por defecto (coinciden con la biblia GEMINI)
BAYES_CREDIBILITY_THRESHOLD = 0.7
BAYES_LOWER_PERCENTILE = 0.05
BAYES_ALPHA = 1.0
BAYES_BETA = 1.0
EDGE_THRESHOLD = 0.01  # 2% de ventaja mínima


# =====================================================
# 🎛️ SENSORES — DETECTORES TÉCNICOS
# =====================================================
# Activar o desactivar detectores individuales (puedes probar combinaciones)
ACTIVE_SENSORS = {
    # Mean Reversion (8 sensores)
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "StochasticReversion": True,
    "BollingerSqueeze": True,
    "WilliamsRReversion": True,
    "CCIReversion": True,
    "ZScoreReversion": True,
    # Momentum/Trend (5 sensores)
    "EMACrossover": True,
    "MACDCrossover": True,
    "Supertrend": True,
    "ADXFilter": True,
    "ParabolicSAR": True,
    # Volume (4 sensores)
    "OBVBreakout": True,
    "VWAPDeviation": True,
    "MFIReversion": True,
    "AccumulationDistribution": True,
}

# Parámetros personalizados por sensor (si deseas ajustarlos)
SENSOR_PARAMS = {
    "RSIReversion": {"period": 2, "low": 10, "high": 90},
    "BollingerTouch": {"window": 20, "std_dev": 2.5},
    "KeltnerReversion": {"window": 20, "multiplier": 2.0},
    "EMACrossover": {"short_period": 12, "long_period": 26, "adx_period": 14, "adx_threshold": 20},
    "MACDCrossover": {"short_period": 12, "long_period": 26, "signal_period": 9},
    "OBVBreakout": {"short_period": 20, "long_period": 50},
}


# =====================================================
# 🪙 PERFIL DEL CASINO (GENERAL)
# =====================================================
# Configuración básica de trading
MAX_LEVERAGE = 50  # máximo apalancamiento permitido (Hyperliquid soporta hasta 50x)
MAX_POSITION_SIZE = 0.02  # tamaño máximo conservador (2% del equity para live trading)
COMMISSION_RATE = 0.0005  # taker fee de Hyperliquid (0.05%)
SLIPPAGE_DEFAULT = 0.0003  # spread más ajustado para Hyperliquid
MAINTENANCE_MARGIN_RATE = 0.003  # margen de mantenimiento de Hyperliquid (0.3%)
DEFAULT_MARGIN_TYPE = "ISOLATED"  # Opciones: ISOLATED, CROSSED


# =====================================================
# 🧾 LOGGING Y SALIDA
# =====================================================
# Nivel de detalle del log (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = "INFO"

# Guardar resultados (historial de rendimiento, etc.)
SAVE_RESULTS = True
RESULTS_FILE = "casino_results.csv"
DECISIONS_LOG_PATH = "gemini/data/gemini_decisions.csv"
TRADE_RESULTS_LOG_PATH = "gemini/data/gemini_trade_results.csv"


# =====================================================
# 🧱 OPCIONAL — SEMILLA ALEATORIA (reproducibilidad)
# =====================================================
SEED = 42

# 🚨 Configuración Live (placeholder) ---------------------------------------------------------
SYMBOL = "BTC/USD"
TIMEFRAME = "15m"


# =====================================================
# 🚨 VALIDACIONES DE SEGURIDAD PARA LIVE TRADING
# =====================================================
if MODE == "live":  # pragma: no cover - interacción manual requerida
    if os.getenv(LIVE_ENV_FLAG, "").lower() != "true":
        msg = (
            "\n" + "=" * 70 + "\n"
            "🚨 LIVE TRADING DESHABILITADO 🚨\n" + "=" * 70 + "\n\n"
            "Live trading requiere confirmación explícita.\n"
            "Para habilitarlo ejecuta:\n"
            "    export CASINO_LIVE_TRADING_ENABLED=true\n"
            "(y asegúrate de ejecutar en un entorno seguro).\n"
        )
        print(msg)
        sys.exit(1)

    if not LIVE_TRADING_ENABLED:
        msg = (
            "\n" + "=" * 70 + "\n"
            "❌ LIVE_TRADING_ENABLED=False en core/config.py\n" + "=" * 70 + "\n\n"
            "Para activar live trading debes establecer:\n"
            "  - core/config.py → LIVE_TRADING_ENABLED_DEFAULT = True\n"
            "    o bien\n"
            "  - export CASINO_LIVE_TRADING_ENABLED_CONFIG=true\n"
            "Solo hazlo si estás listo para operar con dinero real.\n"
        )
        print(msg)
        sys.exit(1)

    print("\n" + "=" * 70)
    print("⚠️  CONFIRMACIÓN DE LIVE TRADING (DINERO REAL) ⚠️")
    print("=" * 70)
    print(f"Modo: {MODE}")
    print(f"Exchange: {EXCHANGE}")
    print(f"Símbolo: {SYMBOL}")
    print()
    print("⚠️  ESTO USARÁ DINERO REAL")
    print(f"Escribe '{LIVE_CONFIRMATION_KEYWORD}' para continuar.")

    try:
        confirmation = input("Confirmación: ").strip()
    except EOFError:
        confirmation = ""

    if confirmation != LIVE_CONFIRMATION_KEYWORD:
        print("\n❌ Live trading cancelado por el usuario\n")
        sys.exit(0)

    print("\n✅ Live trading confirmado. Procediendo bajo tu responsabilidad.\n")
