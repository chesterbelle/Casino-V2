"""
Trading Module - Casino V2

Unified trading session that works with any data source.
Uses a pipeline architecture for clean, testable code.
"""

from .context import TradingContext
from .pipeline import Pipeline, Stage
from .session import TradingSession

__all__ = [
    "TradingContext",
    "Pipeline",
    "Stage",
    "TradingSession",
]
