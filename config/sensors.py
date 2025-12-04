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
# Activar o desactivar detectores individuales
ACTIVE_SENSORS = {
    # === OPTIMIZED SENSORS (2025-11-29) ===
    "ADXFilter": True,
    "BollingerSqueeze": True,
    "BollingerTouch": True,
    "CCIReversion": True,
    "DecelerationCandles": True,
    "DojiIndecision": True,
    "EMA50Support": True,
    "EMACrossover": True,
    "EngulfingPattern": True,
    "ExtremeCandleRatio": True,
    "FVGRetest": True,
    "InsideBarBreakout": True,
    "KeltnerReversion": True,
    "MACDCrossover": True,
    "MarubozuMomentum": True,
    "MomentumBurst": True,
    "MorningStar": True,
    "PinBarReversal": True,
    "RSIReversion": True,
    "RailsPattern": True,
    "StochasticReversion": True,
    "Supertrend": True,
    "VCPPattern": True,
    "VWAPDeviation": True,
    "VolumeImbalance": True,
    "WilliamsRReversion": True,
    "ZScoreReversion": True,
    # === QUICKSCALPER SENSORS (Active for demo) ===
    "Fakeout": True,
    "MicroTrend": True,
    "SmartRange": True,
    "AdaptiveRSI": True,
    "HigherTFTrend": True,  # Context sensor
    # === ALL SENSORS ENABLED FOR DEBUGALL ===
    "OrderBlock": True,
    "VWAPBreakout": True,
    "VWAPMomentum": True,
    "MTFImpulse": True,
    "VolatilityWakeup": True,
    "BollingerRejection": True,
    "KeltnerBreakout": True,
    "HurstRegime": True,
    "VSAReversal": True,
    "ThreeBar": True,
    "TweezerPattern": True,
    "SupportResistance": True,
    "VolumeSpike": True,
    "LiquidityVoid": True,
    "LongTail": True,
    "WyckoffSpring": True,
    "AbsorptionBlock": True,
    "ParabolicSAR": True,
    "WickRejection": True,
}


# =====================================================
# ⏱️ TIMEFRAME ÓPTIMO POR SENSOR
# =====================================================
# Define qué timeframe del context usar para cada sensor
# Basado en la lógica del sensor y recomendaciones de trading algorítmico:
# - Patrones de velas: 15m/1h (menor ruido)
# - Osciladores: 5m/15m (balance señal/ruido)
# - Momentum/Trend: 1h/4h (contexto macro)
# - Ejecución rápida: 1m (precisión de entrada)

SENSOR_TIMEFRAMES = {
    # === TREND INDICATORS (Higher TF for direction) ===
    "ADXFilter": "15m",
    "EMACrossover": "15m",
    "MACDCrossover": "15m",
    "Supertrend": "15m",
    "ParabolicSAR": "15m",
    "HigherTFTrend": "1h",  # Contexto macro
    "MTFImpulse": "5m",  # Balance entre TFs
    "EMA50Support": "15m",
    # === OSCILLATORS (Medium TF for signal quality) ===
    "RSIReversion": "15m",
    "StochasticReversion": "1m",  # QuickScalper - 1m for demo
    "CCIReversion": "5m",
    "WilliamsRReversion": "5m",
    "AdaptiveRSI": "1m",  # QuickScalper - 1m for demo
    # === VOLATILITY BANDS (Medium TF) ===
    "BollingerTouch": "5m",
    "BollingerSqueeze": "15m",
    "BollingerRejection": "5m",
    "KeltnerReversion": "5m",
    "KeltnerBreakout": "15m",
    "ZScoreReversion": "5m",
    # === CANDLESTICK PATTERNS (Higher TF = more reliable) ===
    "EngulfingPattern": "15m",
    "PinBarReversal": "15m",
    "RailsPattern": "15m",
    "MorningStar": "1h",  # Multi-candle = needs HTF
    "DojiIndecision": "1h",  # Indecision significativa
    "TweezerPattern": "15m",
    "ThreeBar": "15m",
    "MarubozuMomentum": "15m",
    "WickRejection": "15m",
    "LongTail": "15m",
    # === STRUCTURAL PATTERNS (Medium-High TF) ===
    "VCPPattern": "15m",
    "InsideBarBreakout": "15m",
    "DecelerationCandles": "1m",  # QuickScalper - 1m for demo
    "ExtremeCandleRatio": "1m",  # Detección de pánico rápido
    "Fakeout": "1m",  # QuickScalper - 1m for demo
    # === VOLUME ANALYSIS (Quick detection) ===
    "VolumeImbalance": "5m",
    "VolumeSpike": "1m",
    "VSAReversal": "5m",
    "AbsorptionBlock": "5m",
    # === SMART MONEY CONCEPTS (Medium TF) ===
    "OrderBlock": "15m",
    "LiquidityVoid": "15m",
    "FVGRetest": "5m",  # Zones más precisas
    "WyckoffSpring": "15m",
    # === MOMENTUM (Fast detection) ===
    "MomentumBurst": "1m",
    "MicroTrend": "1m",
    "SmartRange": "1m",
    # === VWAP (Medium TF) ===
    "VWAPDeviation": "5m",
    "VWAPBreakout": "5m",
    "VWAPMomentum": "5m",
    # === REGIME DETECTION (Higher TF) ===
    "HurstRegime": "15m",
    "VolatilityWakeup": "15m",
    "SupportResistance": "1h",
}


# =====================================================
# ⚙️ PARÁMETROS DE SENSORES
# =====================================================

# Parámetros personalizados por sensor (MULTI-TIMEFRAME OPTIMIZED 2025-11-29 V3)
# Each sensor can have different TP/SL for different timeframes
# Format: "SensorName": {"1m": {...}, "5m": {...}, "15m": {...}}
SENSOR_PARAMS = {
    # =====================================================
    # MTF-OPTIMIZED SENSOR PARAMS (Generated 2025-12-04)
    # Format: "SensorName": {"optimal_tf": {"tp_pct": X, "sl_pct": Y}}
    # Sorted by expectancy (highest first)
    # =====================================================
    #
    # --- TOP TIER: Exp > 1.0% ---
    "MorningStar": {
        "15m": {"tp_pct": 0.1500, "sl_pct": 0.0250},  # Exp: 1.730%
    },
    "BollingerSqueeze": {
        "15m": {"tp_pct": 0.1500, "sl_pct": 0.0400},  # Exp: 1.602%
    },
    "MomentumBurst": {
        "15m": {"tp_pct": 0.0550, "sl_pct": 0.0950},  # Exp: 1.151%
    },
    "KeltnerBreakout": {
        "15m": {"tp_pct": 0.0750, "sl_pct": 0.0550},  # Exp: 1.018%
    },
    #
    # --- HIGH TIER: Exp 0.5% - 1.0% ---
    "WyckoffSpring": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0200},  # Exp: 0.827%
    },
    "VolumeSpike": {
        "5m": {"tp_pct": 0.1160, "sl_pct": 0.0680},  # Exp: 0.818%
    },
    "VolatilityWakeup": {
        "15m": {"tp_pct": 0.0600, "sl_pct": 0.0950},  # Exp: 0.753%
    },
    "RailsPattern": {
        "15m": {"tp_pct": 0.1250, "sl_pct": 0.0200},  # Exp: 0.663%
    },
    "VolumeImbalance": {
        "15m": {"tp_pct": 0.1350, "sl_pct": 0.0550},  # Exp: 0.639%
    },
    "Supertrend": {
        "15m": {"tp_pct": 0.1150, "sl_pct": 0.0400},  # Exp: 0.630%
    },
    "ThreeBar": {
        "15m": {"tp_pct": 0.1000, "sl_pct": 0.0250},  # Exp: 0.629%
    },
    "EMACrossover": {
        "15m": {"tp_pct": 0.0600, "sl_pct": 0.0800},  # Exp: 0.617%
    },
    "BollingerRejection": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0250},  # Exp: 0.603%
    },
    "VWAPDeviation": {
        "1m": {"tp_pct": 0.0970, "sl_pct": 0.0590},  # Exp: 0.500%
    },
    #
    # --- MID TIER: Exp 0.2% - 0.5% ---
    "BollingerTouch": {
        "5m": {"tp_pct": 0.0920, "sl_pct": 0.0800},  # Exp: 0.476%
    },
    "ADXFilter": {
        "15m": {"tp_pct": 0.0750, "sl_pct": 0.0900},  # Exp: 0.445%
    },
    "PinBarReversal": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0250},  # Exp: 0.371%
    },
    "AbsorptionBlock": {
        "5m": {"tp_pct": 0.0320, "sl_pct": 0.0560},  # Exp: 0.347%
    },
    "FVGRetest": {
        "15m": {"tp_pct": 0.1000, "sl_pct": 0.0500},  # Exp: 0.347%
    },
    "SupportResistance": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0250},  # Exp: 0.340%
    },
    "ExtremeCandleRatio": {
        "15m": {"tp_pct": 0.1100, "sl_pct": 0.0250},  # Exp: 0.327%
    },
    "MarubozuMomentum": {
        "15m": {"tp_pct": 0.1500, "sl_pct": 0.0500},  # Exp: 0.307%
    },
    "DojiIndecision": {
        "15m": {"tp_pct": 0.1500, "sl_pct": 0.0550},  # Exp: 0.271%
    },
    "MACDCrossover": {
        "15m": {"tp_pct": 0.1000, "sl_pct": 0.0350},  # Exp: 0.268%
    },
    "HurstRegime": {
        "15m": {"tp_pct": 0.1200, "sl_pct": 0.0300},  # Exp: 0.260%
    },
    "InsideBarBreakout": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0250},  # Exp: 0.255%
    },
    "ZScoreReversion": {
        "15m": {"tp_pct": 0.1350, "sl_pct": 0.0150},  # Exp: 0.255%
    },
    "TweezerPattern": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0300},  # Exp: 0.247%
    },
    "VCPPattern": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0250},  # Exp: 0.211%
    },
    "KeltnerReversion": {
        "5m": {"tp_pct": 0.0950, "sl_pct": 0.0770},  # Exp: 0.202%
    },
    #
    # --- LOW TIER: Exp 0.05% - 0.2% ---
    "DecelerationCandles": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0200},  # Exp: 0.172%
    },
    "LongTail": {
        "5m": {"tp_pct": 0.1100, "sl_pct": 0.0110},  # Exp: 0.168%
    },
    "CCIReversion": {
        "5m": {"tp_pct": 0.0710, "sl_pct": 0.0800},  # Exp: 0.133%
    },
    "AdaptiveRSI": {
        "15m": {"tp_pct": 0.1050, "sl_pct": 0.0300},  # Exp: 0.130%
    },
    "WickRejection": {
        "5m": {"tp_pct": 0.0410, "sl_pct": 0.0770},  # Exp: 0.104%
    },
    "StochasticReversion": {
        "5m": {"tp_pct": 0.0680, "sl_pct": 0.0800},  # Exp: 0.099%
    },
    "EMA50Support": {
        "15m": {"tp_pct": 0.1100, "sl_pct": 0.0400},  # Exp: 0.095%
    },
    "RSIReversion": {
        "15m": {"tp_pct": 0.1300, "sl_pct": 0.0200},  # Exp: 0.092%
    },
    "SmartRange": {
        "1m": {"tp_pct": 0.0310, "sl_pct": 0.0250},  # Exp: 0.088%
    },
    "MicroTrend": {
        "5m": {"tp_pct": 0.0680, "sl_pct": 0.0530},  # Exp: 0.085%
    },
    "WilliamsRReversion": {
        "5m": {"tp_pct": 0.0680, "sl_pct": 0.0800},  # Exp: 0.083%
    },
    "VWAPMomentum": {
        "5m": {"tp_pct": 0.0530, "sl_pct": 0.0440},  # Exp: 0.018%
    },
    "EngulfingPattern": {
        "1m": {"tp_pct": 0.0990, "sl_pct": 0.0110},  # Exp: 0.014%
    },
    #
    # --- DEFAULT FALLBACK (for sensors not in optimization) ---
    "_default": {
        "1m": {"tp_pct": 0.0150, "sl_pct": 0.0100},
        "5m": {"tp_pct": 0.0300, "sl_pct": 0.0200},
        "15m": {"tp_pct": 0.0600, "sl_pct": 0.0400},
        "1h": {"tp_pct": 0.1200, "sl_pct": 0.0800},
    },
}


# =====================================================
# 🔧 HELPER FUNCTIONS
# =====================================================


def get_sensor_params(sensor_id: str, timeframe: str = "1m") -> dict:
    """
    Get TP/SL parameters for a sensor at a specific timeframe.

    Supports both legacy format (single dict) and new multi-timeframe format.

    Args:
        sensor_id: Name of the sensor (e.g., "BollingerTouch")
        timeframe: Timeframe string (e.g., "1m", "5m", "15m", "1h")

    Returns:
        Dictionary with at least {"tp_pct": float, "sl_pct": float}

    Examples:
        # Multi-TF format
        >>> get_sensor_params("BollingerTouch", "5m")
        {"tp_pct": 0.045, "sl_pct": 0.025}

        # Legacy format (backward compatible)
        >>> get_sensor_params("BollingerTouch", "1m")
        {"tp_pct": 0.027, "sl_pct": 0.014}
    """
    if sensor_id not in SENSOR_PARAMS:
        # Sensor not found, use default
        return SENSOR_PARAMS["_default"].get(timeframe, {"tp_pct": 0.015, "sl_pct": 0.01})

    sensor_config = SENSOR_PARAMS[sensor_id]

    # Check if it's multi-timeframe format (has timeframe keys)
    if isinstance(sensor_config, dict) and timeframe in sensor_config:
        return sensor_config[timeframe]

    # Check if it's legacy format (has tp_pct/sl_pct directly)
    if isinstance(sensor_config, dict) and "tp_pct" in sensor_config:
        # Legacy format, return as-is (assumes 1m optimization)
        return sensor_config

    # Fallback to default
    return SENSOR_PARAMS["_default"].get(timeframe, {"tp_pct": 0.015, "sl_pct": 0.01})


def get_sensor_timeframe(sensor_id: str) -> str:
    """
    Get the optimal timeframe for a sensor.

    Args:
        sensor_id: Name of the sensor (e.g., "DojiIndecision")

    Returns:
        Timeframe string (e.g., "1m", "5m", "15m", "1h")
        Defaults to "1m" if sensor not found in SENSOR_TIMEFRAMES.

    Example:
        >>> get_sensor_timeframe("DojiIndecision")
        "1h"
        >>> get_sensor_timeframe("ExtremeCandleRatio")
        "1m"
    """
    return SENSOR_TIMEFRAMES.get(sensor_id, "1m")
