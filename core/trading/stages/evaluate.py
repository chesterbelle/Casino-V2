"""
Evaluate Stage - Casino V2

Evaluates signals through Gemini to make trading decision.
"""

import logging

from core.trading.context import TradingContext
from core.trading.pipeline import Stage

logger = logging.getLogger(__name__)


class EvaluateStage(Stage):
    """
    Evaluate signals through Gemini.

    Takes signals and evaluates them using Gemini's logic
    (Kelly criterion, credibility, etc.) to decide whether to trade.
    """

    def __init__(self, gemini):
        """
        Initialize stage with Gemini instance.

        Args:
            gemini: Gemini instance
        """
        self.gemini = gemini

    async def process(self, context: TradingContext) -> TradingContext:
        """
        Evaluate signals through Gemini.

        Args:
            context: Trading context with signals

        Returns:
            Context with verdict
        """
        # Convert signals to list for Gemini
        signals = list(context.signals)

        if not signals:
            logger.debug("⏭️ No signals to evaluate")
            return context.with_verdict({"action": "SKIP", "reason": "no_signals"})

        # Evaluate through Gemini
        decision = self.gemini.evaluate_signals(signals, equity=context.equity)

        # DEBUG: Log decision details
        logger.debug(f"📊 Decision details: action={decision.action}, reason={decision.reason}, side={decision.side}")

        # Convert Decision to verdict dict
        verdict = {
            "action": decision.action,
            "reason": decision.reason,
            "trade_id": decision.trade_id,
            "order": decision.order,
        }

        action = verdict.get("action", "SKIP")
        reason = verdict.get("reason", "unknown")

        logger.info(f"🎯 Gemini verdict: {action} ({reason})")

        return context.with_verdict(verdict)
