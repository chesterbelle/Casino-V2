"""
Croupier - Portfolio Orchestrator (Refactored).

Lightweight orchestrator that delegates to specialized components:
- OrderExecutor: Handles individual order execution
- OCOManager: Manages OCO bracket orders
- ReconciliationService: Syncs state with exchange

This replaces the 1911-line God Object with a clean facade pattern.

Author: Casino V3 Team
Version: 3.0.0
"""

import logging
from typing import Any, Dict, List, Optional

from core.error_handling import get_error_handler
from core.portfolio.balance_manager import BalanceManager
from core.portfolio.position_tracker import OpenPosition, PositionTracker

from .components.oco_manager import OCOManager
from .components.order_executor import OrderExecutor
from .components.reconciliation_service import ReconciliationService


class Croupier:
    """
    Portfolio orchestrator - delegates to specialized components.

    Components:
    - OrderExecutor: Execute individual orders with retry
    - OCOManager: Create OCO brackets atomically
    - ReconciliationService: Sync state with exchange

    Example:
        adapter = ExchangeAdapter(connector, symbol="BTC/USDT:USDT")
        croupier = Croupier(adapter, initial_balance=10000.0)

        # Execute OCO bracket order
        result = await croupier.execute_order({
            "symbol": "BTC/USDT:USDT",
            "side": "LONG",
            "size": 0.01,
            "take_profit": 1.01,
            "stop_loss": 0.99
        })
    """

    def __init__(self, exchange_adapter, initial_balance: float, max_concurrent_positions: int = 10):
        """
        Initialize Croupier orchestrator.

        Args:
            exchange_adapter: ExchangeAdapter for order execution
            initial_balance: Starting capital
            max_concurrent_positions: Max number of concurrent positions
        """
        self.adapter = exchange_adapter
        # Backward compatibility: some components expect exchange_adapter
        self.exchange_adapter = exchange_adapter
        self.logger = logging.getLogger("Croupier")

        # Initialize core components
        self.error_handler = get_error_handler()
        self.balance_manager = BalanceManager(initial_balance)
        self.position_tracker = PositionTracker(max_concurrent_positions=max_concurrent_positions)

        # Initialize specialized components
        self.order_executor = OrderExecutor(exchange_adapter, self.error_handler)
        self.oco_manager = OCOManager(self.order_executor, self.position_tracker, exchange_adapter)
        self.reconciliation = ReconciliationService(exchange_adapter, self.position_tracker, self.oco_manager)

        self.logger.info(
            f"✅ Croupier initialized | Balance: {initial_balance} | " f"Max Positions: {max_concurrent_positions}"
        )

    async def execute_order(self, order: Dict[str, Any], wait_for_fill: bool = True) -> Dict[str, Any]:
        """
        Execute order with full OCO bracket.

        This is the main entry point for creating new positions.
        Delegates to OCOManager for atomic bracket creation.

        Args:
            order: Order dict with:
                - symbol: Trading symbol
                - side: "LONG" or "SHORT"
                - size: Position size (will be calculated)
                - amount: Order amount in contracts
                - take_profit: TP multiplier
                - stop_loss: SL multiplier
            wait_for_fill: Wait for main order fill confirmation

        Returns:
            OCO result dict with main_order, tp_order, sl_order

        Raises:
            OCOAtomicityError: If OCO creation fails
        """
        self.logger.info(f"📥 Execute order request: {order['side']} {order['symbol']}")

        # Delegate to OCOManager
        result = await self.oco_manager.create_bracketed_order(order, wait_for_fill=wait_for_fill)

        # Register position in tracker
        position = await self._register_position(order, result)

        # Update balance (reserve margin)
        margin_used = order.get("margin_used", 0)
        if margin_used > 0:
            self.balance_manager.reserve_margin(margin_used)

        self.logger.info(f"✅ Position opened: {position.trade_id} | " f"Entry: {result['fill_price']:.2f}")

        return result

    async def reconcile_positions(self, symbol: Optional[str] = None):
        """
        Reconcile positions with exchange.

        Args:
            symbol: Symbol to reconcile (None = all symbols)

        Returns:
            Reconciliation report
        """
        if symbol:
            return await self.reconciliation.reconcile_symbol(symbol)
        else:
            # Reconcile all symbols with open positions
            symbols = {pos.symbol for pos in self.position_tracker.open_positions}
            reports = []

            for sym in symbols:
                report = await self.reconciliation.reconcile_symbol(sym)
                reports.append(report)

            return reports

    def get_balance(self) -> float:
        """Get current available balance."""
        return self.balance_manager.balance

    def get_equity(self) -> float:
        """Get current equity (balance + unrealized PnL)."""
        return self.balance_manager.equity

    def get_open_positions(self) -> List[OpenPosition]:
        """Get all open positions."""
        return self.position_tracker.open_positions

    def can_open_position(self, margin_required: float) -> bool:
        """Check if we can open a new position."""
        return self.balance_manager.can_open_position(margin_required)

    async def _register_position(self, order: Dict[str, Any], oco_result: Dict[str, Any]) -> OpenPosition:
        """
        Register new position in tracker.

        Args:
            order: Original order dict
            oco_result: OCO creation result

        Returns:
            OpenPosition instance
        """
        # Create position object
        position = OpenPosition(
            trade_id=oco_result["main_order"]["order_id"],
            symbol=order["symbol"],
            side=order["side"],
            entry_price=oco_result["fill_price"],
            entry_timestamp=oco_result["main_order"].get("timestamp", ""),
            margin_used=order.get("margin_used", 0),
            notional=order.get("notional", 0),
            leverage=order.get("leverage", 1),
            tp_level=oco_result["tp_price"],
            sl_level=oco_result["sl_price"],
            main_order_id=oco_result["main_order"]["order_id"],
            tp_order_id=oco_result["tp_order"]["order_id"],
            sl_order_id=oco_result["sl_order"]["order_id"],
        )

        # Add to tracker
        self.position_tracker.open_positions.append(position)

        return position

    def get_stats(self) -> Dict[str, Any]:
        """
        Get trading statistics.

        Returns:
            Dict with stats from position tracker
        """
        return self.position_tracker.get_stats()

    def __repr__(self) -> str:
        return (
            f"Croupier(balance={self.get_balance():.2f}, "
            f"equity={self.get_equity():.2f}, "
            f"positions={len(self.get_open_positions())})"
        )
