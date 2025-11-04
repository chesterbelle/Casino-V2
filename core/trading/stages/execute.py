"""
Execute Stage - Casino V2

Executes order through data source (backtest, testing, or live).
"""

import logging

from core.trading.context import TradingContext
from core.trading.pipeline import Stage

logger = logging.getLogger(__name__)


class ExecuteStage(Stage):
    """
    Execute order through data source.

    Takes built order and executes it through the data source.
    The data source handles the actual execution (simulated or real).
    """

    def __init__(self, data_source):
        """
        Initialize stage with data source.

        Args:
            data_source: DataSource instance (backtest, testing, or live)
        """
        self.data_source = data_source

    async def process(self, context: TradingContext) -> TradingContext:
        """
        Execute order.

        Args:
            context: Trading context with order

        Returns:
            Context with execution result
        """
        order = context.order

        if not order:
            logger.debug("⏭️ No order to execute")
            return context

        # Execute through data source
        try:
            result = await self.data_source.execute_order(order)

            status = result.get("status", "unknown")
            logger.info(f"✅ Order executed | Status: {status}")

            return context.with_result(result)

        except Exception as e:
            logger.error(f"❌ Order execution failed: {e}", exc_info=True)

            # Return context with error result
            error_result = {
                "status": "error",
                "reason": str(e),
                "order": order,
            }

            return context.with_result(error_result)
