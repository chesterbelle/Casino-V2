"""
====================================================
🎛️ CONFIGURACIÓN DE SENSORES — CASINO V2
====================================================

Configuración de detectores técnicos y sus parámetros.
"""

# =====================================================
# 🎛️ SENSORES ACTIVOS
# =====================================================

# Activar o desactivar detectores individuales
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


# =====================================================
# ⚙️ PARÁMETROS DE SENSORES
# =====================================================

# Parámetros personalizados por sensor
SENSOR_PARAMS = {
    "RSIReversion": {"period": 2, "low": 10, "high": 90},
    "BollingerTouch": {"window": 20, "std_dev": 2.5},
    "KeltnerReversion": {"window": 20, "multiplier": 2.0},
    "EMACrossover": {"short_period": 12, "long_period": 26, "adx_period": 14, "adx_threshold": 20},
    "MACDCrossover": {"short_period": 12, "long_period": 26, "signal_period": 9},
    "OBVBreakout": {"short_period": 20, "long_period": 50},
}
