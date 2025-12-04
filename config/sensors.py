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
    # === DISABLED / NOT OPTIMIZED ===
    "OrderBlock": False,  # No trades generated in 30d
    "VWAPBreakout": False,
    "VWAPMomentum": False,
    "MicroTrendPullback": False,
    "VolatilityWakeup": False,
    "BollingerBandRejection": False,
    "KeltnerBreakout": False,
    "VolumeFlowImbalance": False,
    "HurstRegime": False,
    "MFIReversion": False,
    "AdaptiveRSIScalper": False,
    "VSAReversal": False,
    "SmartRangeScalper": False,
    "FakeoutReversal": False,
    "ThreeBarReversal": False,
    "MorningStarEvening": False,
    "TweezerPattern": False,
    "SupportResistanceBounce": False,
    "VolumeSpikeReversal": False,
    "OrderBlockBreakout": False,
    "LiquidityVoid": False,
    "LongTailDistribution": False,
    "WyckoffSpring": False,
    "AbsorptionBlock": False,
    "HigherTFTrendConfirm": False,
    "MultiTimeframeImpulse": False,
    "MomentumPinball": False,
    "AggressiveVolume": False,
    "VolumeDelta": False,
    "WickRejection": False,
    "OBVBreakout": False,
    "ParabolicSAR": False,
    "AccumulationDistribution": False,
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
    "StochasticReversion": "5m",
    "CCIReversion": "5m",
    "WilliamsRReversion": "5m",
    "AdaptiveRSI": "5m",
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
    "DecelerationCandles": "5m",
    "ExtremeCandleRatio": "1m",  # Detección de pánico rápido
    "Fakeout": "5m",
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
    "ADXFilter": {
        "15m": {"tp_pct": 0.0760, "sl_pct": 0.0790},  # Exp: 0.348%
    },
    "BollingerSqueeze": {
        "5m": {"tp_pct": 0.0230, "sl_pct": 0.0490},  # Exp: 0.193%
        "15m": {"tp_pct": 0.1090, "sl_pct": 0.0400},  # Exp: 1.453%
    },
    "BollingerTouch": {
        "1m": {"tp_pct": 0.0270, "sl_pct": 0.0140},  # Exp: 0.492%
        "5m": {"tp_pct": 0.0770, "sl_pct": 0.0330},  # Exp: 0.372%
        "15m": {"tp_pct": 0.0940, "sl_pct": 0.0160},  # Exp: 0.599%
    },
    "CCIReversion": {
        "1m": {"tp_pct": 0.0070, "sl_pct": 0.0300},  # Exp: 0.303%
        "5m": {"tp_pct": 0.0710, "sl_pct": 0.0470},  # Exp: 0.136%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0190},  # Exp: 0.142%
    },
    "DecelerationCandles": {
        "1m": {"tp_pct": 0.0070, "sl_pct": 0.0200},  # Exp: 0.238%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0190},  # Exp: 0.185%
    },
    "DojiIndecision": {
        "1m": {"tp_pct": 0.0310, "sl_pct": 0.0080},  # Exp: 0.205%
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0350},  # Exp: 0.162%
        "15m": {"tp_pct": 0.0760, "sl_pct": 0.0550},  # Exp: 0.251%
    },
    "EMA50Support": {
        "1m": {"tp_pct": 0.0090, "sl_pct": 0.0180},  # Exp: 0.274%
        "15m": {"tp_pct": 0.1120, "sl_pct": 0.0430},  # Exp: 0.248%
    },
    "EMACrossover": {
        "1m": {"tp_pct": 0.0050, "sl_pct": 0.0290},  # Exp: 0.112%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0280},  # Exp: 0.473%
    },
    "EngulfingPattern": {
        "1m": {"tp_pct": 0.0140, "sl_pct": 0.0220},  # Exp: 0.448%
    },
    "ExtremeCandleRatio": {
        "1m": {"tp_pct": 0.0050, "sl_pct": 0.0280},  # Exp: 0.065%
        "15m": {"tp_pct": 0.1120, "sl_pct": 0.0250},  # Exp: 0.322%
    },
    "FVGRetest": {
        "1m": {"tp_pct": 0.0080, "sl_pct": 0.0190},  # Exp: 0.039%
        "15m": {"tp_pct": 0.1000, "sl_pct": 0.0310},  # Exp: 0.339%
    },
    "InsideBarBreakout": {
        "1m": {"tp_pct": 0.0060, "sl_pct": 0.0300},  # Exp: 0.034%
        "5m": {"tp_pct": 0.0730, "sl_pct": 0.0350},  # Exp: 0.057%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0250},  # Exp: 0.176%
    },
    "KeltnerReversion": {
        "1m": {"tp_pct": 0.0120, "sl_pct": 0.0270},  # Exp: 0.396%
        "5m": {"tp_pct": 0.0790, "sl_pct": 0.0410},  # Exp: 0.152%
        "15m": {"tp_pct": 0.1090, "sl_pct": 0.0100},  # Exp: 0.100%
    },
    "MACDCrossover": {
        "1m": {"tp_pct": 0.0040, "sl_pct": 0.0270},  # Exp: 0.144%
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0350},  # Exp: 0.019%
        "15m": {"tp_pct": 0.1030, "sl_pct": 0.0340},  # Exp: 0.269%
    },
    "MarubozuMomentum": {
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0460},  # Exp: 0.279%
    },
    "MomentumBurst": {
        "1m": {"tp_pct": 0.0050, "sl_pct": 0.0270},  # Exp: 0.278%
        "15m": {"tp_pct": 0.1060, "sl_pct": 0.0250},  # Exp: 0.672%
    },
    "MorningStar": {
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0370},  # Exp: 0.141%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0250},  # Exp: 1.505%
    },
    "PinBarReversal": {
        "1m": {"tp_pct": 0.0050, "sl_pct": 0.0290},  # Exp: 0.122%
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0290},  # Exp: 0.205%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0250},  # Exp: 0.326%
    },
    "RSIReversion": {
        "1m": {"tp_pct": 0.0060, "sl_pct": 0.0300},  # Exp: 0.157%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0220},  # Exp: 0.104%
    },
    "RailsPattern": {
        "1m": {"tp_pct": 0.0060, "sl_pct": 0.0290},  # Exp: 0.210%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0370},  # Exp: 0.577%
    },
    "StochasticReversion": {
        "1m": {"tp_pct": 0.0080, "sl_pct": 0.0290},  # Exp: 0.286%
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0490},  # Exp: 0.104%
    },
    "Supertrend": {
        "1m": {"tp_pct": 0.0040, "sl_pct": 0.0180},  # Exp: 0.148%
        "5m": {"tp_pct": 0.0610, "sl_pct": 0.0290},  # Exp: 0.154%
        "15m": {"tp_pct": 0.1150, "sl_pct": 0.0400},  # Exp: 0.630%
    },
    "VCPPattern": {
        "1m": {"tp_pct": 0.0080, "sl_pct": 0.0300},  # Exp: 0.078%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0250},  # Exp: 0.199%
    },
    "VWAPDeviation": {
        "5m": {"tp_pct": 0.0370, "sl_pct": 0.0490},  # Exp: 0.159%
        "15m": {"tp_pct": 0.0970, "sl_pct": 0.0520},  # Exp: 0.031%
    },
    "VolumeImbalance": {
        "1m": {"tp_pct": 0.0050, "sl_pct": 0.0290},  # Exp: 0.107%
        "15m": {"tp_pct": 0.1120, "sl_pct": 0.0490},  # Exp: 0.637%
    },
    "WilliamsRReversion": {
        "1m": {"tp_pct": 0.0080, "sl_pct": 0.0300},  # Exp: 0.250%
        "5m": {"tp_pct": 0.0690, "sl_pct": 0.0490},  # Exp: 0.084%
        "15m": {"tp_pct": 0.1180, "sl_pct": 0.0190},  # Exp: 0.009%
    },
    "ZScoreReversion": {
        "1m": {"tp_pct": 0.0270, "sl_pct": 0.0260},  # Exp: 0.356%
        "5m": {"tp_pct": 0.0770, "sl_pct": 0.0330},  # Exp: 0.061%
        "15m": {"tp_pct": 0.0940, "sl_pct": 0.0160},  # Exp: 0.317%
    },
    # Legacy parameters for sensors not yet optimized for multi-TF
    "HurstRegime": {"hurst_period": 50, "hurst_threshold": 0.5},
    "FakeoutReversal": {"breakout_threshold_pct": 0.002, "lookback_candles": 10, "reversal_body_pct": 0.6},
    "ThreeBarReversal": {"range_decrease_threshold": 0.7, "close_position_threshold": 0.4},
    "MorningStarEvening": {"min_large_body_pct": 0.004, "max_star_body_pct": 0.002, "confirmation_threshold": 0.5},
    "TweezerPattern": {"max_wick_diff_pct": 0.0005, "min_second_body_pct": 0.002},
    "VolumeSpikeReversal": {"volume_multiplier": 3.0, "min_body_pct": 0.004},
    "HigherTFTrendConfirm": {"higher_tf": 5, "ema_period": 20},
    "OrderBlockBreakout": {"block_size": 3, "max_range_pct": 0.001, "breakout_pct": 0.003},
    "LiquidityVoid": {"gap_pct": 0.002, "max_volume_pct": 0.001},
    "LongTailDistribution": {"n_small": 5, "factor": 3.0},
    "WyckoffSpring": {"lookback": 20, "volume_factor": 1.5},
    "AbsorptionBlock": {"volume_factor": 2.0, "body_factor": 0.3},
    "MultiTimeframeImpulse": {"ema_period": 20},
    "AggressiveVolume": {"volume_multiplier": 2.0, "min_body_pct": 0.002},
    "VolumeDelta": {"lookback": 10, "delta_threshold": 0.6},
    "WickRejection": {"wick_to_body_ratio": 2.0, "min_wick_pct": 0.003},
    "MomentumPinball": {"ema_period": 34, "rsi_period": 2, "oversold": 10, "overbought": 90},
    "VWAPBreakout": {"std_dev_mult": 1.0, "volume_factor": 1.2, "adx_threshold": 20.0},
    # Default TP/SL parameters per timeframe (fallback)
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
