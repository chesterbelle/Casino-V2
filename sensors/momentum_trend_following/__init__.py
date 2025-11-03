"""Colección de sensores Momentum / Trend-Following."""

from .adx_filter import ADXFilter
from .ema_crossover import EMACrossover
from .macd_crossover import MACDCrossover
from .parabolic_sar import ParabolicSAR
from .supertrend import Supertrend

__all__ = [
    "EMACrossover",
    "MACDCrossover",
    "Supertrend",
    "ADXFilter",
    "ParabolicSAR",
]
