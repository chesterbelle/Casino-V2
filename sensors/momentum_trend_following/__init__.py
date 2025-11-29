"""Colección de sensores de Momentum y Trend Following."""

from .adx_filter import ADXFilter
from .ema50_support import EMA50Support
from .ema_crossover import EMACrossover
from .macd_crossover import MACDCrossover
from .momentum_pinball import MomentumPinball
from .parabolic_sar import ParabolicSAR
from .supertrend import Supertrend

__all__ = [
    "EMACrossover",
    "MACDCrossover",
    "Supertrend",
    "ADXFilter",
    "ParabolicSAR",
    "MomentumPinball",
    "EMA50Support",
]
