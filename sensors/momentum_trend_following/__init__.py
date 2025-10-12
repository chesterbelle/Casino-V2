"""Colección de sensores Momentum / Trend-Following."""

from .ema_crossover import EMACrossover
from .macd_crossover import MACDCrossover

__all__ = [
    "EMACrossover",
    "MACDCrossover",
]
