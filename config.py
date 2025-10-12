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
#  - "realtime"  → usa conexión de API (futuro módulo)
MODE = "backtest"

# Perfil del exchange (usa el JSON de tables/data/exchange_profiles)
EXCHANGE_PROFILE = "binance"

# Ruta del dataset CSV (para modo backtest)
DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"


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
KELLY_FRACTION = 0.3


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
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "EMACrossover": True,
    "MACDCrossover": True,
    "OBVBreakout": True,
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
MAX_LEVERAGE = 50           # máximo apalancamiento permitido
MAX_POSITION_SIZE = 0.25    # tamaño máximo (25% del equity)
COMMISSION_RATE = 0.0004    # equivalente al taker fee (0.04%)
SLIPPAGE_DEFAULT = 0.0005   # spread estimado de ejecución


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
