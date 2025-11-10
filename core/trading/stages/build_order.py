"""
Build Order Stage - Casino V2

Builds executable order from Gemini's verdict using Player's logic.

Note:
    Some players (like Paroli) ignore Gemini's verdict and bet on every signal.
    This stage handles both conservative players (Kelly) that respect Gemini's
    BET/GHOST decision, and aggressive players (Paroli) that bet regardless.
"""

import logging

from core.trading.context import TradingContext
from core.trading.pipeline import Stage

logger = logging.getLogger(__name__)


class BuildOrderStage(Stage):
    """
    Build order from verdict using Player.

    Takes Gemini's verdict and uses Player's logic to calculate
    position size and build the final order.

    Behavior:
    - Conservative players (Kelly): Only build order if action == "BET"
    - Aggressive players (Paroli): Build order if there's a side, ignore action
    """

    def __init__(self, player_module):
        """
        Initialize stage with Player module.

        Args:
            player_module: Player module (e.g., paroli, martingale, kelly)
        """
        self.player = player_module

        # Detect if player is aggressive (ignores Gemini verdict)
        # Paroli and Martingale bet on every signal regardless of Gemini
        player_name = getattr(player_module, "__name__", "").lower()
        self.is_aggressive = "paroli" in player_name or "martingale" in player_name

    async def process(self, context: TradingContext) -> TradingContext:
        """
        Build order from verdict.

        Args:
            context: Trading context with verdict

        Returns:
            Context with built order
        """
        verdict = context.verdict

        if not verdict:
            logger.debug("⏭️ No verdict to process")
            return context

        # Check if we should build an order
        action = verdict.get("action", "SKIP")

        if self.is_aggressive:
            # Aggressive players (Paroli): bet if there's a side, ignore action
            if not verdict.get("order") or not verdict["order"].get("side"):
                logger.debug("⏭️ No side in verdict (aggressive player needs a side)")
                return context
            logger.debug(f"🎲 Aggressive player: building order despite action={action}")
        else:
            # Conservative players (Kelly): only bet if action == "BET"
            if action != "BET":
                logger.debug(f"⏭️ No order to build (action={action}, conservative player)")
                return context

        # Get order from verdict (Gemini already built it)
        order = verdict.get("order")

        if not order:
            logger.warning("⚠️ Verdict has action=BET but no order")
            return context

        # Validate order has required fields
        required_fields = ["symbol", "side", "size", "take_profit", "stop_loss"]
        missing = [f for f in required_fields if f not in order]

        if missing:
            logger.error(f"❌ Order missing fields: {missing}")
            return context

        # Get size from order (may be 0 for GHOST orders)
        size_fraction = float(order.get("size", 0.0))

        # For aggressive players (Paroli), recalculate size even if Gemini said GHOST
        # This allows Paroli to bet its own size regardless of Gemini's conservative verdict
        if self.is_aggressive and size_fraction == 0.0:
            # Call player's calculate_position_size if available
            if hasattr(self.player, "calculate_position_size"):
                # Create a simple verdict-like object for the player
                class SimpleVerdict:
                    def __init__(self, side):
                        self.side = side

                player_verdict = SimpleVerdict(order["side"])

                # Calculate size using player's logic with metadata from session
                player_meta = context.metadata or {}
                player_size = self.player.calculate_position_size(player_verdict, context.equity, meta=player_meta)

                if player_size and player_size > 0:
                    size_fraction = player_size
                    logger.info(
                        f"🎲 Aggressive player calculated size: {size_fraction:.4f} "
                        f"(overriding Gemini's GHOST size=0)"
                    )

        # If still 0, skip order
        if size_fraction == 0.0:
            logger.debug("⏭️ Size is 0, skipping order")
            return context

        # Current price is available in context.candle.close if needed
        # current_price = context.candle.close

        # Calculate notional amount (margin to use)
        notional_amount = context.equity * size_fraction

        # Get leverage from player (default to 1 if not specified)
        leverage = getattr(self.player, "LEVERAGE", 1)
        position_size_usd = notional_amount * leverage

        # Calculate base amount (in base currency)
        # Not used in this context, removed to fix flake8 F841
        # base_amount = position_size_usd / current_price

        # Build executable order (using Croupier's internal format)
        # Note: Croupier expects LONG/SHORT (not buy/sell)
        # Croupier will calculate 'amount' from 'size' using real exchange price
        executable_order = {
            "symbol": order["symbol"],
            "side": order["side"],  # Keep LONG/SHORT (Croupier's format)
            "size": size_fraction,  # Croupier expects "size" (fraction of equity)
            "take_profit": order["take_profit"],
            "stop_loss": order["stop_loss"],
            "trade_id": verdict.get("trade_id"),
            "leverage": leverage,
        }

        logger.info(
            f"📝 Order built | "
            f"{executable_order['side'].upper()} "
            f"size={executable_order['size']:.4f} ({executable_order['size']*100:.2f}% equity) | "
            f"Margin: ${notional_amount:.2f} | "
            f"Position: ${position_size_usd:.2f} ({leverage}x)"
        )

        return context.with_order(executable_order)
