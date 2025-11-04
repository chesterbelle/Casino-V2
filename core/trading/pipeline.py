"""
Trading Pipeline - Casino V2

Clean pipeline architecture for processing trading decisions.
Each stage does one thing and passes context to the next stage.
"""

import logging
from abc import ABC, abstractmethod
from typing import List

from .context import TradingContext

logger = logging.getLogger(__name__)


class Stage(ABC):
    """
    Abstract base class for pipeline stages.

    Each stage:
    - Receives a TradingContext
    - Performs one specific task
    - Returns a new TradingContext (immutable)
    """

    @abstractmethod
    async def process(self, context: TradingContext) -> TradingContext:
        """
        Process the trading context.

        Args:
            context: Current trading context

        Returns:
            New trading context with updates
        """
        pass

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return self.__class__.__name__


class Pipeline:
    """
    Trading pipeline that processes context through multiple stages.

    Example:
        >>> pipeline = Pipeline([
        ...     ProcessSignalsStage(),
        ...     EvaluateStage(),
        ...     BuildOrderStage(),
        ...     ExecuteStage(),
        ... ])
        >>> result = await pipeline.process(context)
    """

    def __init__(self, stages: List[Stage]):
        """
        Initialize pipeline with stages.

        Args:
            stages: List of Stage instances to execute in order
        """
        self.stages = stages
        logger.info(f"📊 Pipeline initialized with {len(stages)} stages")

    async def process(self, context: TradingContext) -> TradingContext:
        """
        Process context through all stages.

        Args:
            context: Initial trading context

        Returns:
            Final trading context after all stages

        Note:
            If any stage raises an exception, it's logged and
            the context is returned as-is (fail-safe).
        """
        current_context = context

        for stage in self.stages:
            try:
                logger.debug(f"🔄 Processing stage: {stage.name}")
                current_context = await stage.process(current_context)
            except Exception as e:
                logger.error(f"❌ Error in stage {stage.name}: {e}", exc_info=True)
                # Return context as-is (fail-safe)
                return current_context

        return current_context
