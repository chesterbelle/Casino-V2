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
    # === TIER 1: ELITE PERFORMERS (WR >70%) ===
    "EMACrossover": True,  # 80.56% WR - TOP PERFORMER! 🏆
    "PinBarReversal": True,  # 76.56% WR
    "RailsPattern": True,  # 69.05% WR
    # === TIER 2: EXCELLENT (WR 60-70%) ===
    "EMA50Support": True,  # 65.22% WR
    "MarubozuMomentum": True,  # 65.00% WR
    "VWAPBreakout": True,  # 62.96% WR
    "ExtremeCandleRatio": True,  # 61.20% WR
    # === TIER 3: GOOD (WR 55-60%) ===
    "InsideBarBreakout": True,  # 59.21% WR
    "DecelerationCandles": True,  # 57.94% WR
    "VWAPDeviation": True,  # 56.10% WR
    "VCPPattern": True,  # 55.61% WR
    "EngulfingPattern": True,  # 55.07% WR
    # === DISABLED - UNDERPERFORMERS (WR <53%) ===
    "VWAPMomentum": False,  # 51.11% WR - mediocre
    "MicroTrendPullback": False,  # 52.90% WR - mediocre
    "VolatilityWakeup": False,  # 50.00% WR - insufficient data
    # === DISABLED - TERRIBLE PERFORMERS (WR <50%) ===
    "BollingerBandRejection": False,  # 48.63% WR - 7,683 losing trades!
    "KeltnerBreakout": False,  # 47.60% WR - 3,439 losing trades!
    "VolumeFlowImbalance": False,  # 47.20% WR - 2,962 losing trades!
    "HurstRegime": False,  # 49.55% WR - 668 losing trades
    # === DISABLED - LOW PERFORMANCE (WR < 52%) ===
    "BollingerSqueeze": False,
    "Supertrend": False,
    "MACDCrossover": False,
    "CCIReversion": False,
    "MFIReversion": False,
    "StochasticReversion": False,
    "WilliamsRReversion": False,
    "AdaptiveRSIScalper": False,
    "MomentumBurst": False,
    "VSAReversal": False,
    "SmartRangeScalper": False,
    # === DISABLED - PRICE ACTION (Unproven/Noisy) ===
    "FakeoutReversal": False,
    "ThreeBarReversal": False,
    "DojiIndecision": False,
    "MorningStarEvening": False,
    "TweezerPattern": False,
    "SupportResistanceBounce": False,
    "VolumeSpikeReversal": False,
    "OrderBlockBreakout": False,
    "LiquidityVoid": False,
    # "ExtremeCandleRatio": False,  # Duplicate removed
    "LongTailDistribution": False,
    "WyckoffSpring": False,
    "FVGRetest": False,
    "AbsorptionBlock": False,
    # === DISABLED - LAGGING/SLOW ===
    "HigherTFTrendConfirm": False,  # Uses 5m/15m - too slow for 1m scalping
    "MultiTimeframeImpulse": False,  # MTF lag
    # "DecelerationCandles": False,  # Duplicate removed
    # "VCPPattern": False,  # Duplicate removed
    # === DISABLED - MEAN REVERSION (Low WR) ===
    "ADXFilter": False,
    "RSIReversion": False,
    "ZScoreReversion": False,
    "KeltnerReversion": False,
    "BollingerTouch": False,
    # "EMACrossover": False,  # Duplicate removed
    # === NEW OPTIMIZED SENSORS (Tested - Mediocre) ===
    "MomentumPinball": False,  # 51.35% WR - mediocre
    # === DISABLED - NEW SCALPING SENSORS (Failed Tests) ===
    "AggressiveVolume": False,  # Generated losing signals
    "VolumeDelta": False,  # Generated losing signals
    "WickRejection": False,  # Generated losing signals
    # === DISABLED - NO DATA ===
    "OBVBreakout": False,
    "ParabolicSAR": False,
    "AccumulationDistribution": False,
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
    # Params Scalping
    "AdaptiveRSIScalper": {"period": 14, "atr_period": 14},
    "MomentumBurst": {"rsi_period": 14, "burst_threshold": 15.0},
    "BollingerBandRejection": {"window": 20, "std_dev": 2.0},
    "VSAReversal": {"volume_period": 50, "volume_threshold_pct": 90.0, "spread_threshold_pct": 20.0},
    # Params Regimen
    "SmartRangeScalper": {"adx_period": 14, "adx_threshold": 25.0, "bb_window": 20, "bb_std": 2.0},
    "MicroTrendPullback": {"adx_period": 14, "adx_threshold": 25.0, "ema_fast": 9, "ema_slow": 20},
    "VolatilityWakeup": {"bb_window": 20, "bb_std": 2.0, "squeeze_threshold": 0.05, "volume_factor": 1.5},
    # Params HFT
    "VWAPMomentum": {"vwap_period": 20, "momentum_threshold": 0.002},
    "KeltnerBreakout": {"keltner_period": 20, "keltner_multiplier": 2.0, "atr_period": 14},
    "VolumeFlowImbalance": {"volume_period": 20, "imbalance_threshold": 1.5},
    "HurstRegime": {"hurst_period": 50, "hurst_threshold": 0.5},
    # Params Price Action
    "PinBarReversal": {"wick_to_body_ratio": 2.0, "min_wick_pct": 0.003, "close_position_threshold": 0.3},
    "EngulfingPattern": {"volume_multiplier": 1.5, "min_body_pct": 0.002},
    "InsideBarBreakout": {"max_inside_range_pct": 0.005, "breakout_confirmation": True},
    "FakeoutReversal": {"breakout_threshold_pct": 0.002, "lookback_candles": 10, "reversal_body_pct": 0.6},
    "ThreeBarReversal": {"range_decrease_threshold": 0.7, "close_position_threshold": 0.4},
    "DojiIndecision": {"max_body_pct": 0.001, "breakout_body_pct": 0.6, "min_breakout_size": 0.003},
    "MorningStarEvening": {"min_large_body_pct": 0.004, "max_star_body_pct": 0.002, "confirmation_threshold": 0.5},
    "RailsPattern": {"max_level_diff_pct": 0.001, "min_close_position": 0.5},
    "TweezerPattern": {"max_wick_diff_pct": 0.0005, "min_second_body_pct": 0.002},
    "MarubozuMomentum": {"min_body_to_range": 0.8, "min_body_size_pct": 0.004},
    "VolumeSpikeReversal": {"volume_multiplier": 3.0, "min_body_pct": 0.004},
    "HigherTFTrendConfirm": {"higher_tf": 5, "ema_period": 20},
    "OrderBlockBreakout": {"block_size": 3, "max_range_pct": 0.001, "breakout_pct": 0.003},
    "LiquidityVoid": {"gap_pct": 0.002, "max_volume_pct": 0.001},
    "ExtremeCandleRatio": {"lookback": 30, "percentile": 0.95},
    "LongTailDistribution": {"n_small": 5, "factor": 3.0},
    "WyckoffSpring": {"lookback": 20, "volume_factor": 1.5},
    "FVGRetest": {"min_gap_pct": 0.001},
    "AbsorptionBlock": {"volume_factor": 2.0, "body_factor": 0.3},
    "MultiTimeframeImpulse": {"ema_period": 20},
    "DecelerationCandles": {"sequence_length": 3},
    "VCPPattern": {"contractions": 3},
    # Scalping Sensors
    "AggressiveVolume": {"volume_multiplier": 2.0, "min_body_pct": 0.002},
    "VolumeDelta": {"lookback": 10, "delta_threshold": 0.6},
    "WickRejection": {"wick_to_body_ratio": 2.0, "min_wick_pct": 0.003},
    # New Optimized Sensors
    "MomentumPinball": {"ema_period": 34, "rsi_period": 2, "oversold": 10, "overbought": 90},
    "VWAPBreakout": {"std_dev_mult": 1.0, "volume_factor": 1.2, "adx_threshold": 20.0},
    "EMA50Support": {"ema_period": 50, "tolerance_pct": 0.001},
}
