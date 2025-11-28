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
    # === TOP PERFORMERS (HFT Sensors) ===
    # VWAPMomentum: 70.37% WR (LTC RS2), 66.67% (LTC RS2)
    "VWAPMomentum": True,
    # KeltnerBreakout: 62.96% WR (BTC RS5), 59.09% (LTC RS5)
    "KeltnerBreakout": True,
    # MicroTrendPullback: 72.73% WR (LTC RS3/RS5)
    "MicroTrendPullback": True,
    # HurstRegime: 56.14% WR (BTC RS5), 51.85% (LTC RS1)
    "HurstRegime": True,
    # VolumeFlowImbalance: 52.76% WR (LTC RS4), 52.50% (LTC RS9)
    "VolumeFlowImbalance": True,
    # === KEEP FOR DIVERSITY (Moderate Performance) ===
    # BollingerBandRejection: Useful for range detection
    "BollingerBandRejection": True,
    # VolatilityWakeup: Breakout specialist
    "VolatilityWakeup": True,
    # === DISABLED (Low Performance WR < 52%) ===
    "BollingerSqueeze": False,
    "Supertrend": False,
    "MACDCrossover": False,
    "CCIReversion": False,  # WR ~48-50%
    "MFIReversion": False,  # WR ~48-50%
    "StochasticReversion": False,  # WR ~48-51%
    "WilliamsRReversion": False,  # WR ~48-50%
    "AdaptiveRSIScalper": False,  # Inconsistent
    "MomentumBurst": False,  # Low sample size
    "VSAReversal": False,  # Low sample size
    "SmartRangeScalper": False,  # WR < 50% in most buckets
    # === Price Action Sensors (Pure Pattern Recognition - 0 Lag) ===
    "PinBarReversal": True,
    "EngulfingPattern": True,
    "InsideBarBreakout": True,
    "FakeoutReversal": True,
    "ThreeBarReversal": True,
    "DojiIndecision": True,
    "MorningStarEvening": True,
    "RailsPattern": True,
    "TweezerPattern": True,
    "MarubozuMomentum": True,
    "SupportResistanceBounce": True,
    "VolumeSpikeReversal": False,
    "HigherTFTrendConfirm": True,
    "OrderBlockBreakout": True,
    "LiquidityVoid": False,
    "ExtremeCandleRatio": True,
    "LongTailDistribution": False,
    # === Sensores NO Rentables (Desactivados) ===
    "ADXFilter": False,
    "RSIReversion": False,
    "ZScoreReversion": False,
    "KeltnerReversion": False,
    "BollingerTouch": False,
    "EMACrossover": False,
    "VWAPDeviation": False,
    "OBVBreakout": False,
    "ParabolicSAR": False,  # No data, disabled as precaution
    "AccumulationDistribution": False,  # No data, disabled as precaution
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
}
