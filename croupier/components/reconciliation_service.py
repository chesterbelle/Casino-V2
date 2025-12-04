"""
ReconciliationService - Syncs local state with exchange.

This component is responsible for:
- Periodic reconciliation of positions with exchange
- Detecting and fixing positions without TP/SL
- Handling unknown positions from exchange
- Cleaning up orphaned orders

Author: Casino V3 Team
Version: 3.0.0
"""

import logging
from typing import Any, Dict, List

from core.error_handling import RetryConfig, get_error_handler
from core.portfolio.position_tracker import PositionTracker


class ReconciliationService:
    """
    Reconciles local position state with exchange state.

    Handles:
    - Positions without complete TP/SL → Fix or close
    - Exchange positions not in tracker → Add or close
    - Orphaned orders without position → Cancel

    Example:
        service = ReconciliationService(adapter, tracker, oco_manager)

        # Reconcile a symbol
        await service.reconcile_symbol("BTC/USDT:USDT")

        # Check for issues
        issues = await service.detect_issues("BTC/USDT:USDT")
    """

    def __init__(self, exchange_adapter, position_tracker: PositionTracker, oco_manager):
        """
        Initialize ReconciliationService.

        Args:
            exchange_adapter: ExchangeAdapter for fetching positions/orders
            position_tracker: PositionTracker instance
            oco_manager: OCOManager for fixing missing TP/SL
        """
        self.adapter = exchange_adapter
        self.tracker = position_tracker
        self.oco_manager = oco_manager
        self.error_handler = get_error_handler()
        self.logger = logging.getLogger("ReconciliationService")

        # Retry config for reconciliation operations
        self.reconcile_retry_config = RetryConfig(max_retries=3, backoff_base=1.0, backoff_factor=2.0, jitter=True)

    async def reconcile_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Reconcile all positions for a symbol.

        Checks:
        1. Local positions have valid TP/SL
        2. Exchange positions exist in tracker
        3. No orphaned orders

        Args:
            symbol: Trading symbol to reconcile

        Returns:
            Reconciliation report dict
        """
        self.logger.info(f"🔄 Starting reconciliation for {symbol}")

        report = {
            "symbol": symbol,
            "positions_checked": 0,
            "positions_fixed": 0,
            "positions_closed": 0,
            "orders_cancelled": 0,
            "issues_found": [],
        }

        try:
            # Get local and exchange positions
            # Filter positions by symbol manually (PositionTracker doesn't have get_positions_by_symbol)
            local_positions = [pos for pos in self.tracker.open_positions if pos.symbol == symbol]
            exchange_positions = await self._fetch_exchange_positions(symbol)

            report["positions_checked"] = len(local_positions)

            # Check 1: Validate local positions have TP/SL
            for pos in local_positions:
                if not self._has_valid_tp_sl(pos):
                    self.logger.warning(f"⚠️ Position {pos.trade_id} missing TP/SL")
                    report["issues_found"].append(f"missing_tp_sl:{pos.trade_id}")

                    # Try to fix or close
                    fixed = await self._fix_or_close_position(pos)
                    if fixed:
                        report["positions_fixed"] += 1
                    else:
                        report["positions_closed"] += 1

            # Check 2: Exchange positions not in tracker
            for ex_pos in exchange_positions:
                if not self._exists_in_tracker(ex_pos, local_positions):
                    self.logger.warning(f"⚠️ Unknown position in exchange: {ex_pos}")
                    report["issues_found"].append(f"unknown_position:{ex_pos}")

                    # Close unknown positions
                    await self._close_unknown_position(ex_pos)
                    report["positions_closed"] += 1

            # Check 3: Orphaned orders
            cancelled = await self._cleanup_orphaned_orders(symbol)
            report["orders_cancelled"] = cancelled

            self.logger.info(
                f"✅ Reconciliation complete: {report['positions_fixed']} fixed, "
                f"{report['positions_closed']} closed, {report['orders_cancelled']} orders cancelled"
            )

        except Exception as e:
            self.logger.error(f"❌ Reconciliation failed: {e}", exc_info=True)
            report["error"] = str(e)

        return report

    async def detect_issues(self, symbol: str) -> List[str]:
        """
        Detect reconciliation issues without fixing them.

        Args:
            symbol: Trading symbol

        Returns:
            List of issue descriptions
        """
        issues = []

        local_positions = self.tracker.get_positions_by_symbol(symbol)

        for pos in local_positions:
            if not self._has_valid_tp_sl(pos):
                issues.append(
                    f"Position {pos.trade_id} missing TP/SL "
                    f"(tp_order_id={pos.tp_order_id}, sl_order_id={pos.sl_order_id})"
                )

        return issues

    def _has_valid_tp_sl(self, position) -> bool:
        """Check if position has both TP and SL order IDs."""
        return (
            position.tp_order_id is not None
            and position.sl_order_id is not None
            and position.tp_order_id != ""
            and position.sl_order_id != ""
        )

    async def _fix_or_close_position(self, position) -> bool:
        """
        Try to fix position by creating missing TP/SL, or close it.

        Returns:
            True if fixed, False if closed
        """
        try:
            self.logger.info(f"🔧 Attempting to fix position {position.trade_id}")

            # Try to create missing TP/SL orders
            # This requires knowing the current position size and entry price
            # For now, we close positions that can't be fixed

            # TODO: Implement TP/SL recreation logic when possible
            # For MVP, just close problematic positions

            self.logger.warning(f"⚠️ Cannot fix position {position.trade_id}, closing instead")
            await self._close_position(position)
            return False

        except Exception as e:
            self.logger.error(f"❌ Failed to fix position {position.trade_id}: {e}")
            return False

    async def _close_position(self, position) -> None:
        """Force close a position by creating a reverse market order."""
        try:
            # Create reverse order to close position
            close_side = "sell" if position.side == "LONG" else "buy"

            # Cancel existing TP/SL if they exist
            if position.tp_order_id:
                try:
                    await self.adapter.cancel_order(position.tp_order_id)
                except Exception:
                    pass

            if position.sl_order_id:
                try:
                    await self.adapter.cancel_order(position.sl_order_id)
                except Exception:
                    pass

            # Close position with market order
            # Note: This uses rough estimate of amount, ideally fetch from exchange
            await self.adapter.create_market_order(
                symbol=position.symbol,
                side=close_side,
                amount=position.notional / position.entry_price,  # Rough estimate
            )

            # Remove from tracker
            self.tracker.open_positions.remove(position)

            self.logger.info(f"✅ Closed position {position.trade_id}")

        except Exception as e:
            self.logger.error(f"❌ Failed to close position {position.trade_id}: {e}")

    async def _fetch_exchange_positions(self, symbol: str) -> List[Dict]:
        """Fetch positions from exchange with retry logic."""
        try:
            positions = await self.error_handler.execute_with_breaker(
                "reconciliation_fetch", self.adapter.fetch_positions, [symbol], retry_config=self.reconcile_retry_config
            )
            return positions or []
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch exchange positions: {e}")
            return []

    def _exists_in_tracker(self, exchange_position: Dict, local_positions: List) -> bool:
        """Check if exchange position exists in local tracker."""
        # Exchange position format varies by exchange
        # Best effort matching by symbol and side
        ex_symbol = exchange_position.get("symbol")

        for local_pos in local_positions:
            if local_pos.symbol == ex_symbol and abs(local_pos.notional) > 0:
                return True

        return False

    async def _close_unknown_position(self, exchange_position: Dict) -> None:
        """Close an unknown position found in exchange."""
        try:
            symbol = exchange_position.get("symbol")
            side = exchange_position.get("side")  # Can be "long" or "short"
            contracts = abs(exchange_position.get("contracts", 0))

            if contracts == 0:
                return  # Nothing to close

            # Determine close side
            close_side = "sell" if side == "long" else "buy"

            self.logger.warning(f"🧹 Closing unknown position: {symbol} {side} {contracts} contracts")

            # Close with market order
            await self.adapter.create_market_order(symbol=symbol, side=close_side, amount=contracts)

            self.logger.info(f"✅ Closed unknown position: {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Failed to close unknown position: {e}")

    async def _cleanup_orphaned_orders(self, symbol: str) -> int:
        """
        Cancel orphaned orders (orders without associated position).

        Returns:
            Number of orders cancelled
        """
        try:
            # Fetch all open orders for symbol with retry
            open_orders = await self.error_handler.execute_with_breaker(
                "reconciliation_fetch", self.adapter.fetch_open_orders, symbol, retry_config=self.reconcile_retry_config
            )

            if not open_orders:
                return 0

            # Get all order IDs from tracker
            tracked_order_ids = set()
            for pos in self.tracker.open_positions:
                if pos.symbol == symbol:
                    if pos.main_order_id:
                        tracked_order_ids.add(pos.main_order_id)
                    if pos.tp_order_id:
                        tracked_order_ids.add(pos.tp_order_id)
                    if pos.sl_order_id:
                        tracked_order_ids.add(pos.sl_order_id)

            # Cancel orphaned orders with retry
            cancelled_count = 0
            for order in open_orders:
                order_id = order.get("id")
                if order_id and order_id not in tracked_order_ids:
                    try:
                        await self.error_handler.execute_with_breaker(
                            "reconciliation_cancel",
                            self.adapter.cancel_order,
                            order_id,
                            retry_config=self.reconcile_retry_config,
                        )
                        self.logger.info(f"🧹 Cancelled orphaned order: {order_id}")
                        cancelled_count += 1
                    except Exception as e:
                        self.logger.error(f"❌ Failed to cancel order {order_id}: {e}")

            return cancelled_count

        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup orphaned orders: {e}")
            return 0
