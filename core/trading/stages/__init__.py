"""
Trading Stages - Casino V2

Individual pipeline stages for trading logic.
Each stage does one specific task.
"""

from .build_order import BuildOrderStage
from .evaluate import EvaluateStage
from .execute import ExecuteStage
from .process_signals import ProcessSignalsStage

__all__ = [
    "ProcessSignalsStage",
    "EvaluateStage",
    "BuildOrderStage",
    "ExecuteStage",
]
