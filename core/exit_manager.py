"""
ExitManager - Dynamic Exit Strategy Management
==============================================

Manages dynamic exit strategies for open positions, starting with BREAKEVEN.

Strategies:
- FIXED: No modification (default, current behavior)
- BREAKEVEN: Move SL to entry when price reaches X% of TP distance
- TRAILING: (Future) Follow price with trailing stop
- PARTIAL_TP: (Future) Close partial position at trigger

Author: Casino V3 Team
Version: 2.3.0
"""

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from core.portfolio.position_tracker import OpenPosition

logger = logging.getLogger("ExitManager")


class ExitStrategy(Enum):
    """Available exit strategies."""

    FIXED = "fixed"  # No modification (current behavior)
    BREAKEVEN = "breakeven"  # Move SL to entry at trigger
    TRAILING = "trailing"  # Move SL up as price moves (future)
    PARTIAL_TP = "partial"  # Close partial position (future)


class ExitManager:
    """
    Manages dynamic exit strategies for open positions.

    Usage:
        exit_manager = ExitManager(
            croupier=croupier,
            strategy=ExitStrategy.BREAKEVEN,
            params={"breakeven_trigger": 0.5}
        )

        # On each price update
        action = await exit_manager.on_price_update(position, current_price)
        if action:
            # Action was taken (e.g., SL modified)
            pass
    """

    def __init__(
        self,
        croupier,
        strategy: ExitStrategy = ExitStrategy.FIXED,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ExitManager.

        Args:
            croupier: Croupier instance for order modification
            strategy: Exit strategy to use
            params: Strategy parameters
        """
        self.croupier = croupier
        self.strategy = strategy
        self.params = params or {}

        # Default params per strategy
        self.default_params = {
            ExitStrategy.BREAKEVEN: {
                "breakeven_trigger": 0.5,  # Move SL at 50% of TP distance
            },
            ExitStrategy.TRAILING: {
                "trailing_activation": 0.3,  # Start at 30% of TP
                "trailing_step": 0.005,  # 0.5% trailing step
            },
            ExitStrategy.PARTIAL_TP: {
                "partial_trigger": 0.5,  # At 50% of TP
                "partial_close_pct": 0.5,  # Close 50%
            },
        }

        # Merge defaults with provided params
        if strategy in self.default_params:
            for key, value in self.default_params[strategy].items():
                if key not in self.params:
                    self.params[key] = value

        # Track per-position state (e.g., breakeven_applied)
        self._position_state: Dict[str, Dict[str, Any]] = {}

        logger.info(f"ExitManager initialized | Strategy: {strategy.value} | Params: {self.params}")

    async def on_price_update(self, position: "OpenPosition", current_price: float) -> Optional[Dict[str, Any]]:
        """
        Check if exit action needed based on current price.

        Args:
            position: OpenPosition to check
            current_price: Current market price

        Returns:
            Action dict if action taken, None otherwise
        """
        if self.strategy == ExitStrategy.FIXED:
            return None
        elif self.strategy == ExitStrategy.BREAKEVEN:
            return await self._check_breakeven(position, current_price)
        elif self.strategy == ExitStrategy.TRAILING:
            return await self._check_trailing(position, current_price)
        elif self.strategy == ExitStrategy.PARTIAL_TP:
            return await self._check_partial(position, current_price)
        return None

    async def _check_breakeven(self, position: "OpenPosition", current_price: float) -> Optional[Dict[str, Any]]:
        """
        Check and apply breakeven strategy.

        Moves SL to entry price when price reaches X% of TP distance.
        """
        trade_id = position.trade_id

        # Check if already applied
        state = self._position_state.get(trade_id, {})
        if state.get("breakeven_applied"):
            return None

        # Calculate progress to TP
        if position.side == "LONG":
            tp_distance = position.tp_level - position.entry_price
            current_progress = current_price - position.entry_price
        else:  # SHORT
            tp_distance = position.entry_price - position.tp_level
            current_progress = position.entry_price - current_price

        # Avoid division by zero
        if tp_distance <= 0:
            return None

        progress_pct = current_progress / tp_distance

        # Check trigger
        trigger = self.params.get("breakeven_trigger", 0.5)
        if progress_pct >= trigger:
            # Move SL to entry price
            new_sl = position.entry_price

            logger.info(
                f"🔒 BREAKEVEN Triggered | {position.symbol} {position.side} | "
                f"Progress: {progress_pct:.1%} >= {trigger:.0%} | "
                f"Moving SL: {position.sl_level:.2f} → {new_sl:.2f}"
            )

            try:
                # Modify SL via Croupier
                result = await self.croupier.modify_sl(
                    trade_id=trade_id,
                    new_sl_price=new_sl,
                    symbol=position.symbol,
                    old_sl_order_id=position.sl_order_id,
                )

                # Mark as applied
                self._position_state[trade_id] = {"breakeven_applied": True}

                # Update position's SL level
                position.sl_level = new_sl
                if result:
                    position.sl_order_id = result.get("new_order_id")

                logger.info(f"✅ BREAKEVEN Applied | {trade_id} | New SL: {new_sl:.2f}")

                return {
                    "action": "BREAKEVEN",
                    "trade_id": trade_id,
                    "old_sl": position.sl_level,
                    "new_sl": new_sl,
                    "progress_pct": progress_pct,
                }

            except Exception as e:
                logger.error(f"❌ Failed to apply breakeven for {trade_id}: {e}")
                return None

        return None

    async def _check_trailing(self, position: "OpenPosition", current_price: float) -> Optional[Dict[str, Any]]:
        """Trailing stop logic (future implementation)."""
        # TODO: Implement trailing stop
        logger.debug("Trailing stop not yet implemented")
        return None

    async def _check_partial(self, position: "OpenPosition", current_price: float) -> Optional[Dict[str, Any]]:
        """Partial TP logic (future implementation)."""
        # TODO: Implement partial take profit
        logger.debug("Partial TP not yet implemented")
        return None

    def reset_position_state(self, trade_id: str) -> None:
        """Clear state for a closed position."""
        if trade_id in self._position_state:
            del self._position_state[trade_id]

    def get_stats(self) -> Dict[str, Any]:
        """Get ExitManager statistics."""
        return {
            "strategy": self.strategy.value,
            "params": self.params,
            "active_positions": len(self._position_state),
            "breakeven_applied": sum(1 for s in self._position_state.values() if s.get("breakeven_applied")),
        }
