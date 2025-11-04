"""
Trading Context - Casino V2

Immutable state container for trading pipeline.
Each stage receives a context and returns a new modified context.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from core.data_sources.base import Candle


@dataclass(frozen=True)
class TradingContext:
    """
    Immutable trading context.

    Contains all state needed for a trading decision.
    Each pipeline stage receives a context and returns a new one.

    This immutability ensures:
    - No race conditions
    - Easy to debug (state is explicit)
    - Easy to test (predictable)

    Attributes:
        candle: Current candle data
        equity: Current equity (balance + unrealized PnL)
        balance: Available balance
        signals: Detected trading signals (tuple for immutability)
        verdict: Gemini's evaluation result
        order: Built order ready for execution
        result: Execution result
        metadata: Additional context data
    """

    candle: Candle
    equity: float
    balance: float
    signals: Tuple[Dict, ...] = field(default_factory=tuple)
    verdict: Optional[Dict] = None
    order: Optional[Dict] = None
    result: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)

    def with_signals(self, signals: List[Dict]) -> "TradingContext":
        """Return new context with updated signals."""
        return replace(self, signals=tuple(signals))

    def with_verdict(self, verdict: Dict) -> "TradingContext":
        """Return new context with verdict."""
        return replace(self, verdict=verdict)

    def with_order(self, order: Dict) -> "TradingContext":
        """Return new context with order."""
        return replace(self, order=order)

    def with_result(self, result: Dict) -> "TradingContext":
        """Return new context with execution result."""
        return replace(self, result=result)

    def with_metadata(self, **kwargs) -> "TradingContext":
        """Return new context with updated metadata."""
        new_metadata = {**self.metadata, **kwargs}
        return replace(self, metadata=new_metadata)
