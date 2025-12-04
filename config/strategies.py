"""
====================================================
🎯 STRATEGY CONFIGURATION — CASINO V3
====================================================

Defines trading strategies as groups of sensors.
Only sensors from enabled strategies will be loaded.

This solves the problem of conflicting signals from
incompatible sensors (e.g., trend vs reversal).
"""

from typing import Dict, List, Set

# =====================================================
# 📊 STRATEGY DEFINITIONS
# =====================================================

STRATEGIES: Dict[str, dict] = {
    # -----------------------------------------------------
    # TREND FOLLOWING - Use in trending markets (ADX > 25)
    # -----------------------------------------------------
    "TrendFollowing": {
        "enabled": True,
        "description": "Follows established trends using momentum indicators",
        "market_condition": "trending",
        "sensors": [
            "EMACrossover",
            "MACDCrossover",
            "Supertrend",
            "ADXFilter",
            "MomentumBurst",
            "MarubozuMomentum",
        ],
        "tp_multiplier": 1.5,  # Larger targets in trends
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # MEAN REVERSION - Use in ranging/choppy markets
    # -----------------------------------------------------
    "MeanReversion": {
        "enabled": False,
        "description": "Fades extremes expecting price to revert to mean",
        "market_condition": "ranging",
        "sensors": [
            "RSIReversion",
            "BollingerTouch",
            "CCIReversion",
            "StochasticReversion",
            "ZScoreReversion",
            "WilliamsRReversion",
            "KeltnerReversion",
        ],
        "tp_multiplier": 0.8,  # Tighter targets
        "max_positions": 3,
    },
    # -----------------------------------------------------
    # BREAKOUT - Use after compression/consolidation
    # -----------------------------------------------------
    "Breakout": {
        "enabled": False,
        "description": "Captures explosive moves after tight ranges",
        "market_condition": "compression",
        "sensors": [
            "VCPPattern",
            "InsideBarBreakout",
            "BollingerSqueeze",
            "VolumeImbalance",
        ],
        "tp_multiplier": 2.0,  # Big moves on breakouts
        "max_positions": 1,
    },
    # -----------------------------------------------------
    # PATTERN RECOGNITION - Candlestick reversal patterns
    # -----------------------------------------------------
    "PatternReversal": {
        "enabled": False,
        "description": "Identifies candlestick reversal patterns",
        "market_condition": "any",
        "sensors": [
            "EngulfingPattern",
            "PinBarReversal",
            "RailsPattern",
            "MorningStar",
            "DojiIndecision",
        ],
        "tp_multiplier": 1.0,
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # SUPPORT/RESISTANCE - Price action at key levels
    # -----------------------------------------------------
    "SupportResistance": {
        "enabled": False,
        "description": "Trades bounces off key price levels",
        "market_condition": "any",
        "sensors": [
            "EMA50Support",
            "VWAPDeviation",
            "FVGRetest",
        ],
        "tp_multiplier": 1.2,
        "max_positions": 2,
    },
    # -----------------------------------------------------
    # AGGRESSIVE SCALPING - High frequency, small targets
    # -----------------------------------------------------
    "AggressiveScalping": {
        "enabled": False,
        "description": "Quick in-and-out trades with tight stops",
        "market_condition": "volatile",
        "sensors": [
            "DecelerationCandles",
            "ExtremeCandleRatio",
        ],
        "tp_multiplier": 0.5,
        "max_positions": 1,
    },
}


# =====================================================
# 🔧 HELPER FUNCTIONS
# =====================================================


def get_active_sensors() -> Set[str]:
    """
    Get sensors from all enabled strategies.

    Returns:
        Set of sensor names that should be active.

    Example:
        >>> get_active_sensors()
        {'EMACrossover', 'MACDCrossover', 'Supertrend', ...}
    """
    active = set()
    for name, config in STRATEGIES.items():
        if config.get("enabled", False):
            active.update(config.get("sensors", []))
    return active


def get_enabled_strategies() -> List[str]:
    """Get list of enabled strategy names."""
    return [name for name, config in STRATEGIES.items() if config.get("enabled", False)]


def get_strategy_for_sensor(sensor_name: str) -> str:
    """
    Find which strategy a sensor belongs to.

    Args:
        sensor_name: Name of the sensor

    Returns:
        Strategy name or "Unknown"
    """
    for name, config in STRATEGIES.items():
        if sensor_name in config.get("sensors", []):
            return name
    return "Unknown"


def get_strategy_config(strategy_name: str) -> dict:
    """Get configuration for a specific strategy."""
    return STRATEGIES.get(strategy_name, {})


def enable_strategy(strategy_name: str) -> bool:
    """Enable a strategy by name."""
    if strategy_name in STRATEGIES:
        STRATEGIES[strategy_name]["enabled"] = True
        return True
    return False


def disable_all_strategies():
    """Disable all strategies."""
    for config in STRATEGIES.values():
        config["enabled"] = False


def enable_only(strategy_name: str):
    """Enable only the specified strategy, disable others."""
    disable_all_strategies()
    enable_strategy(strategy_name)
