"""
====================================================
⚙️ CONFIGURACIÓN GENERAL — CASINO BINANCE V2
====================================================

Este archivo define los parámetros globales de todo el sistema.
Piensa en él como la "ficha de entrada" del jugador:
describe cómo quiere jugar, en qué mesa, y con qué reglas.

Gemini, el Croupier y las Mesas leerán de aquí directamente.
====================================================
"""

# =====================================================
# 🎯 MODO DEL CASINO
# =====================================================
# Puede ser:
#  - "backtest"  → usa dataset CSV y simula operaciones
#  - "live"      → se conecta a un exchange real o de paper trading
MODE = "backtest"

# Perfil del exchange (usa el JSON de tables/data/exchange_profiles)
# Opciones: "asterdex_paper", "kraken_futures_demo", "binance_futures_testnet"
EXCHANGE_PROFILE = "binance_futures_testnet"

# Exchange a utilizar en modo "live"
# Opciones: "ASTER_PAPER", "KRAKEN_DEMO", "BINANCE_FUTURES_TESTNET"
EXCHANGE = "BINANCE_FUTURES_TESTNET"

# Ruta del dataset CSV (para modo backtest) — se utiliza tanto para Gemini
# como para Oscar. Cambia este archivo para alternar rápidamente entre datasets.
DATASET_PATH = "tables/data/raw/LTCUSDT_5m__training.csv"


# =====================================================
# ASTERDEX — PARÁMETROS PAPER/LIVE
# =====================================================
# Valores base para iniciar paper trading. Las claves reales deben
# configurarse via variables de entorno o .env (ver utils/aster_env_loader.py).
ASTER_BASE_URL = "https://fapi.asterdex.com"
ASTER_WS_URL = "wss://fstream.asterdex.com"
ASTER_DEFAULT_SYMBOL = "BTCUSDT"
ASTER_DEFAULT_INTERVAL = "1m"
ASTER_RECV_WINDOW = 5000
ASTER_POLL_INTERVAL = 2.0
ASTER_API_KEY = None
ASTER_API_SECRET = None


# =====================================================
# BINANCE FUTURES — PARÁMETROS TESTNET/LIVE
# =====================================================
BINANCE_BASE_URL = "https://testnet.binancefuture.com"
BINANCE_DEFAULT_SYMBOL = "BTCUSDT"
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
LIVE_MAX_CANDLES = None


# =====================================================
# KRAKEN FUTURES — PARÁMETROS DEMO/LIVE
# =====================================================
KRAKEN_FUTURES_BASE_URL = "https://demo-futures.kraken.com/derivatives/api/"
KRAKEN_FUTURES_CHARTS_URL = "https://demo-futures.kraken.com/api/charts/v1/"
KRAKEN_FUTURES_SYMBOL = "PF_XBTUSD"
KRAKEN_FUTURES_INTERVAL = "1m"
KRAKEN_POLL_INTERVAL = 2.0
KRAKEN_FUTURES_API_KEY = None
KRAKEN_FUTURES_API_SECRET = None


# =====================================================
# 💰 CONFIGURACIÓN FINANCIERA
# =====================================================
# Capital inicial con el que empieza el jugador
STARTING_BALANCE = 10_000.0

# Tamaños relativos de TP y SL (expresados en proporción decimal)
# Ejemplo: 0.01 = 1% de take profit, 0.008 = 0.8% de stop loss
TAKE_PROFIT = 0.012
STOP_LOSS = 0.008

# Fracción del criterio de Kelly a aplicar (1 = Kelly completo, 0.5 = medio Kelly)
KELLY_FRACTION = 0.2


# =====================================================
# 🧠 GEMINI — PARÁMETROS DE APRENDIZAJE
# =====================================================
# Ventana de aprendizaje (cuántos resultados recuerda por bucket)
WINDOW_SIZE = 120

# Mínimo de muestras necesarias por bucket para confiar en la estadística
MIN_SUPPORT = 60

# Umbral mínimo de diferencia estadística para considerar una mesa “caliente”
# Parámetros bayesianos por defecto (coinciden con la biblia GEMINI)
BAYES_CREDIBILITY_THRESHOLD = 0.7
BAYES_LOWER_PERCENTILE = 0.05
BAYES_ALPHA = 1.0
BAYES_BETA = 1.0
EDGE_THRESHOLD = 0.02  # 2% de ventaja mínima


# =====================================================
# 🎛️ SENSORES — DETECTORES TÉCNICOS
# =====================================================
# Activar o desactivar detectores individuales (puedes probar combinaciones)
ACTIVE_SENSORS = {
  
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
MAX_LEVERAGE = 10           # máximo apalancamiento permitido (reducido para evitar liquidaciones)
MAX_POSITION_SIZE = 0.02    # tamaño máximo (2% del equity)
COMMISSION_RATE = 0.0004    # equivalente al taker fee (0.04%)
SLIPPAGE_DEFAULT = 0.0005   # spread estimado de ejecución
MAINTENANCE_MARGIN_RATE = 0.005  # margen de mantenimiento (0.5% para Binance)
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
