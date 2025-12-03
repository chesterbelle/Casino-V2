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

    async def execute_order(self, order: Dict[str, Any], wait_for_fill: bool = False) -> Dict[str, Any]:
        """
        Execute order with full OCO bracket.

        This is the main entry point for creating new positions.
        Delegates to OCOManager for atomic bracket creation.

        Args:
            order: Order dict with:
                - symbol: Trading symbol
                - side: "LONG" or "SHORT"
                - size: Position size fraction (e.g., 0.05 = 5% of equity)
                - amount: Order amount in contracts (optional, calculated from size if missing)
                - take_profit: TP multiplier
                - stop_loss: SL multiplier
            wait_for_fill: Wait for main order fill confirmation (default: False for speed)

        Returns:
            OCO result dict with main_order, tp_order, sl_order

        Raises:
            OCOAtomicityError: If OCO creation fails
        """
        self.logger.info(f"📥 Execute order request: {order['side']} {order['symbol']}")

        # Calculate amount from size if not provided
        if "amount" not in order or order.get("amount") == 0:
            if "size" in order:
                # size is a fraction of equity (e.g., 0.05 = 5%)
                current_equity = self.get_equity()
                position_value = current_equity * order["size"]

                # Get current price
                try:
                    current_price = await self.exchange_adapter.get_current_price(order["symbol"])
                except Exception as e:
                    self.logger.error(f"❌ Failed to get current price for {order['symbol']}: {e}")
                    raise

                # Calculate amount in contracts
                amount_raw = position_value / current_price

                # Round to exchange precision
                amount = float(self.exchange_adapter.amount_to_precision(order["symbol"], amount_raw))

                # Validate minimum amount
                if amount <= 0:
                    raise ValueError(
                        f"Order too small after precision rounding: "
                        f"raw={amount_raw:.12f} → rounded={amount:.8f} | "
                        f"Equity={current_equity:.2f} | Size={order['size']:.2%}"
                    )

                # Add calculated amount to order
                order = order.copy()
                order["amount"] = amount

                self.logger.info(
                    f"📊 Calculated order amount: Equity={current_equity:.2f} | "
                    f"Size={order['size']:.2%} | Value={position_value:.2f} | "
                    f"Price={current_price:.2f} | Amount={amount:.8f}"
                )
            else:
                raise ValueError("Order must have either 'amount' or 'size'")

        # Delegate to OCOManager (don't wait for fill in demo/live, market orders are instant)
        result = await self.oco_manager.create_bracketed_order(order, wait_for_fill=wait_for_fill)

        # Register position in tracker
        position = await self._register_position(order, result)

        # Update balance (reserve margin)
        margin_used = order.get("margin_used", 0)
        if margin_used > 0:
            self.balance_manager.reserve_margin(margin_used)

        self.logger.info(f"✅ Position opened: {position.trade_id} | " f"Entry: {result['fill_price']:.2f}")

        return result

    async def close_position(self, trade_id: str) -> Dict[str, Any]:
        """
        Close a position manually.

        1. Cancel TP/SL orders
        2. Execute market close order
        """
        # Find position
        position = None
        for pos in self.position_tracker.open_positions:
            if pos.trade_id == trade_id:
                position = pos
                break

        if not position:
            raise ValueError(f"Position not found: {trade_id}")

        self.logger.info(f"📤 Closing position: {trade_id} | {position.symbol} {position.side}")

        # 1. Cancel TP/SL
        await self.oco_manager.cancel_bracket(position.tp_order_id, position.sl_order_id)

        # 2. Execute market close
        close_side = "sell" if position.side == "LONG" else "buy"

        # Calculate amount (use remaining amount if partial fills supported, but for now full close)
        # We need to use the original amount or current size.
        # OpenPosition has 'order' dict but maybe not current size if partials happened.
        # Assuming full close for now.
        amount = position.order.get("amount")

        # If amount is missing in order dict (shouldn't happen with new logic), try to calculate or fail
        if not amount:
            # Fallback: try to get from margin/entry if possible, or raise
            raise ValueError("Position has no amount information")

        close_order = {
            "symbol": position.symbol,
            "side": close_side,
            "type": "market",
            "amount": amount,
            "params": {},  # Removed reduceOnly to avoid -2022 error
        }

        self.logger.info(f"📉 Sending close order: {close_side} {amount} {position.symbol}")

        result = await self.order_executor.execute_market_order(close_order)

        fill_price = float(result.get("average", 0) or result.get("price", 0))

        self.logger.info(f"✅ Position closed: {trade_id} | Fill: {fill_price}")

        # Manually confirm close in tracker since we initiated it
        # Calculate PnL
        if position.side == "LONG":
            pnl = (fill_price - position.entry_price) * position.notional / position.entry_price
        else:
            pnl = (position.entry_price - fill_price) * position.notional / position.entry_price

        self.position_tracker.confirm_close(
            trade_id=trade_id,
            exit_price=fill_price,
            exit_reason="MANUAL",
            pnl=pnl,
            fee=0.0,  # We don't have fee info here easily without parsing fills
        )

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
        # Calculate liquidation level (approximate)
        entry_price = oco_result["fill_price"]
        leverage = order.get("leverage", 1)
        side = order["side"]

        liquidation_level = None
        if leverage > 0:
            if side == "LONG":
                liquidation_level = entry_price * (1.0 - (1.0 / leverage) + 0.005)
            elif side == "SHORT":
                liquidation_level = entry_price * (1.0 + (1.0 / leverage) - 0.005)

        # Create position object
        position = OpenPosition(
            trade_id=oco_result["main_order"]["order_id"],
            symbol=order["symbol"],
            side=order["side"],
            entry_price=entry_price,
            entry_timestamp=oco_result["main_order"].get("timestamp", ""),
            margin_used=order.get("margin_used", 0),
            notional=order.get("notional", 0),
            leverage=leverage,
            tp_level=oco_result["tp_price"],
            sl_level=oco_result["sl_price"],
            liquidation_level=liquidation_level,
            order=order,
            main_order_id=oco_result["main_order"]["order_id"],
            tp_order_id=oco_result["tp_order"]["order_id"],
            sl_order_id=oco_result["sl_order"]["order_id"],
        )

        # Add to tracker
        self.position_tracker.open_positions.append(position)
        self.position_tracker.total_trades_opened += 1

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
