"""
====================================================
🎯 SENSOR TYPES & TRADING STRATEGIES — CASINO V3
====================================================

ARCHITECTURE:
- SENSOR_TYPES: Categorize sensors by WHAT they detect
- STRATEGIES: Define HOW to trade, using sensors from any type

A sensor belongs to ONE type but can be used in MULTIPLE strategies.
"""

from typing import Dict, List, Set

# =====================================================
# 📊 SENSOR TYPES (What the sensor detects)
# =====================================================

SENSOR_TYPES: Dict[str, List[str]] = {
    # -----------------------------------------------------
    # TREND INDICATORS - Direction of the market
    # -----------------------------------------------------
    "TrendIndicator": [
        "EMACrossover",
        "MACDCrossover",
        "Supertrend",
        "ADXFilter",
        "ParabolicSAR",
        "HigherTFTrend",
        "MTFImpulse",
    ],
    # -----------------------------------------------------
    # OSCILLATORS - Overbought/Oversold conditions
    # -----------------------------------------------------
    "Oscillator": [
        "RSIReversion",
        "StochasticReversion",
        "CCIReversion",
        "WilliamsRReversion",
        "AdaptiveRSI",
    ],
    # -----------------------------------------------------
    # VOLATILITY/BANDS - Price relative to bands
    # -----------------------------------------------------
    "VolatilityBands": [
        "BollingerTouch",
        "BollingerSqueeze",
        "BollingerRejection",
        "KeltnerReversion",
        "KeltnerBreakout",
        "ZScoreReversion",
    ],
    # -----------------------------------------------------
    # CANDLESTICK PATTERNS - Single/Multi candle formations
    # -----------------------------------------------------
    "CandlestickPattern": [
        "EngulfingPattern",
        "PinBarReversal",
        "RailsPattern",
        "MorningStar",
        "DojiIndecision",
        "TweezerPattern",
        "ThreeBar",
        "MarubozuMomentum",
        "WickRejection",
        "LongTail",
    ],
    # -----------------------------------------------------
    # STRUCTURAL PATTERNS - Multi-bar structures
    # -----------------------------------------------------
    "StructuralPattern": [
        "VCPPattern",
        "InsideBarBreakout",
        "DecelerationCandles",
        "ExtremeCandleRatio",
        "Fakeout",
    ],
    # -----------------------------------------------------
    # VOLUME ANALYSIS - Volume-based signals
    # -----------------------------------------------------
    "VolumeAnalysis": [
        "VolumeImbalance",
        "VolumeSpike",
        "VSAReversal",
        "AbsorptionBlock",
    ],
    # -----------------------------------------------------
    # SMART MONEY / ICT - Institutional concepts
    # -----------------------------------------------------
    "SmartMoneyConcepts": [
        "OrderBlock",
        "LiquidityVoid",
        "FVGRetest",
        "WyckoffSpring",
    ],
    # -----------------------------------------------------
    # VWAP BASED - Volume-weighted average price
    # -----------------------------------------------------
    "VWAPBased": [
        "VWAPDeviation",
        "VWAPBreakout",
        "VWAPMomentum",
    ],
    # -----------------------------------------------------
    # SUPPORT/RESISTANCE - Key price levels
    # -----------------------------------------------------
    "SupportResistance": [
        "EMA50Support",
        "SupportResistance",
    ],
    # -----------------------------------------------------
    # REGIME/FILTER - Market condition detection
    # -----------------------------------------------------
    "RegimeFilter": [
        "HurstRegime",
        "VolatilityWakeup",
        "MicroTrend",
        "SmartRange",
        "MomentumBurst",
    ],
}


# =====================================================
# 🎯 TRADING STRATEGIES (How to trade)
# =====================================================

STRATEGIES: Dict[str, dict] = {
    # -----------------------------------------------------
    # TREND RIDER - Seguir la dirección del mercado
    # -----------------------------------------------------
    "TrendRider": {
        "enabled": False,  # Disabled for demo - using QuickScalper
        "description": "Seguir la dirección del mercado con momentum",
        "logic": "Entrar en pullbacks dentro de tendencias establecidas",
        "sensors": [
            # Trend Indicators
            "EMACrossover",
            "MACDCrossover",
            "Supertrend",
            "ADXFilter",
            "ParabolicSAR",
            # Momentum
            "MomentumBurst",
            "MarubozuMomentum",
            # Multi-timeframe
            "HigherTFTrend",
            "MTFImpulse",
        ],
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # MEAN REVERTER - Operar extremos esperando reversión
    # -----------------------------------------------------
    "MeanReverter": {
        "enabled": False,
        "description": "Operar extremos esperando reversión a la media",
        "logic": "Fade en zonas de sobrecompra/sobreventa",
        "sensors": [
            # Oscillators
            "RSIReversion",
            "StochasticReversion",
            "CCIReversion",
            "WilliamsRReversion",
            "AdaptiveRSI",
            # Bands
            "BollingerTouch",
            "KeltnerReversion",
            "ZScoreReversion",
            # Patterns at extremes
            "PinBarReversal",
            "DojiIndecision",
            # Context (macro trend)
            "HigherTFTrend",
        ],
        "max_positions": 3,
    },
    # -----------------------------------------------------
    # BREAKOUT HUNTER - Capturar movimientos explosivos
    # -----------------------------------------------------
    "BreakoutHunter": {
        "enabled": False,
        "description": "Capturar movimientos explosivos después de compresión",
        "logic": "Entrar cuando volatilidad se expande desde rango",
        "sensors": [
            # Structural
            "VCPPattern",
            "InsideBarBreakout",
            # Volatility expansion
            "BollingerSqueeze",
            "KeltnerBreakout",
            "VolatilityWakeup",
            # Volume confirmation
            "VolumeImbalance",
            # VWAP
            "VWAPBreakout",
            # Context (macro trend)
            "HigherTFTrend",
        ],
        "max_positions": 1,
    },
    # -----------------------------------------------------
    # QUICK SCALPER - Trades rápidos con stops ajustados
    # -----------------------------------------------------
    "QuickScalper": {
        "enabled": False,  # Disabled - using DebugAll
        "description": "Trades rápidos con stops ajustados",
        "logic": "Entradas precisas, salidas rápidas, alto volumen",
        "sensors": [
            # Quick patterns
            "DecelerationCandles",
            "ExtremeCandleRatio",
            "Fakeout",
            # Short-term
            "MicroTrend",
            "SmartRange",
            # Fast oscillators
            "AdaptiveRSI",
            "StochasticReversion",
            # Context (macro trend)
            "HigherTFTrend",
        ],
        "max_positions": 1,
    },
    # -----------------------------------------------------
    # SMART MONEY FOLLOWER - Seguir flujo institucional
    # -----------------------------------------------------
    "SmartMoneyFollower": {
        "enabled": False,
        "description": "Seguir huellas institucionales y manipulación",
        "logic": "Detectar acumulación/distribución y actuar con smart money",
        "sensors": [
            # ICT Concepts
            "OrderBlock",
            "LiquidityVoid",
            "FVGRetest",
            "WyckoffSpring",
            # Volume
            "AbsorptionBlock",
            "VSAReversal",
            "VolumeSpike",
            # VWAP
            "VWAPMomentum",
            "VWAPDeviation",
            # Context (macro trend)
            "HigherTFTrend",
        ],
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # PATTERN TRADER - Operar patrones de velas
    # -----------------------------------------------------
    "PatternTrader": {
        "enabled": False,
        "description": "Operar patrones clásicos de velas",
        "logic": "Identificar reversiones con patrones de alta probabilidad",
        "sensors": [
            # Candlestick patterns
            "EngulfingPattern",
            "PinBarReversal",
            "RailsPattern",
            "MorningStar",
            "TweezerPattern",
            "ThreeBar",
            "WickRejection",
            "LongTail",
            # Context
            "EMA50Support",
            "SupportResistance",
            # Context (macro trend)
            "HigherTFTrend",
        ],
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # DEBUG ALL - Todos los sensores (solo para debugging)
    # -----------------------------------------------------
    "DebugAll": {
        "enabled": True,  # ACTIVE FOR DEBUGGING
        "description": "Todos los sensores activos para debugging",
        "logic": "Máxima cantidad de señales para probar el sistema",
        "sensors": [
            # Trend
            "ADXFilter",
            "EMACrossover",
            "MACDCrossover",
            "Supertrend",
            "ParabolicSAR",
            "HigherTFTrend",
            "MTFImpulse",
            "EMA50Support",
            # Oscillators
            "RSIReversion",
            "StochasticReversion",
            "CCIReversion",
            "WilliamsRReversion",
            "AdaptiveRSI",
            # Bands
            "BollingerTouch",
            "BollingerSqueeze",
            "BollingerRejection",
            "KeltnerReversion",
            "KeltnerBreakout",
            "ZScoreReversion",
            # Patterns
            "EngulfingPattern",
            "PinBarReversal",
            "RailsPattern",
            "MorningStar",
            "DojiIndecision",
            "TweezerPattern",
            "ThreeBar",
            "MarubozuMomentum",
            "WickRejection",
            "LongTail",
            # Structural
            "VCPPattern",
            "InsideBarBreakout",
            "DecelerationCandles",
            "ExtremeCandleRatio",
            "Fakeout",
            # Volume
            "VolumeImbalance",
            "VolumeSpike",
            "VSAReversal",
            "AbsorptionBlock",
            # SMC
            "OrderBlock",
            "LiquidityVoid",
            "FVGRetest",
            "WyckoffSpring",
            # Momentum
            "MomentumBurst",
            "MicroTrend",
            "SmartRange",
            # VWAP
            "VWAPDeviation",
            "VWAPBreakout",
            "VWAPMomentum",
            # Regime
            "HurstRegime",
            "VolatilityWakeup",
            "SupportResistance",
        ],
        "max_positions": 3,
    },
}


# =====================================================
# 🔧 HELPER FUNCTIONS
# =====================================================


def get_sensor_type(sensor_name: str) -> str:
    """Get the type category for a sensor."""
    for type_name, sensors in SENSOR_TYPES.items():
        if sensor_name in sensors:
            return type_name
    return "Unknown"


def get_sensors_by_type(type_name: str) -> List[str]:
    """Get all sensors of a specific type."""
    return SENSOR_TYPES.get(type_name, [])


def get_active_sensors() -> Set[str]:
    """Get sensors from all enabled strategies."""
    active = set()
    for config in STRATEGIES.values():
        if config.get("enabled", False):
            active.update(config.get("sensors", []))
    return active


def get_enabled_strategies() -> List[str]:
    """Get list of enabled strategy names."""
    return [name for name, config in STRATEGIES.items() if config.get("enabled", False)]


def get_strategy_for_sensor(sensor_name: str) -> List[str]:
    """Find which strategies use a sensor (can be multiple)."""
    strategies = []
    for name, config in STRATEGIES.items():
        if sensor_name in config.get("sensors", []):
            strategies.append(name)
    return strategies


def get_strategy_config(strategy_name: str) -> dict:
    """Get configuration for a specific strategy."""
    return STRATEGIES.get(strategy_name, {})


def enable_only(strategy_name: str):
    """Enable only the specified strategy, disable others."""
    for name, config in STRATEGIES.items():
        config["enabled"] = name == strategy_name


def enable_strategies(strategy_names: List[str]):
    """Enable multiple strategies."""
    for name, config in STRATEGIES.items():
        config["enabled"] = name in strategy_names
