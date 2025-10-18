"""Colección de sensores Momentum / Trend-Following."""

from .ema_crossover import EMACrossover
from .macd_crossover import MACDCrossover
from .supertrend import Supertrend
from .adx_filter import ADXFilter
from .parabolic_sar import ParabolicSAR

__all__ = [
    "EMACrossover",
    "MACDCrossover",
    "Supertrend",
    "ADXFilter",
    "ParabolicSAR",
]
