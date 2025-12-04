"""
OCOManager - Manages OCO (One-Cancels-Other) bracket orders.

This component is responsible for:
- Creating bracketed orders (Main + TP + SL)
- Ensuring atomicity of OCO creation
- Waiting for fill confirmation via WebSocket
- Validating OCO integrity (all 3 orders exist)
- Cleanup on partial failure

Author: Casino V3 Team
Version: 3.0.0
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from core.error_handling import RetryConfig, get_error_handler
from core.portfolio.position_tracker import PositionTracker


class OCOAtomicityError(Exception):
    """Raised when OCO bracket creation fails atomically."""

    pass


class OCOManager:
    """
    Manages creation and validation of OCO bracket orders.

    OCO Flow:
    1. Execute main market order
    2. Wait for fill confirmation (WebSocket or polling)
    3. Create TP limit order
    4. Create SL stop order
    5. Validate all 3 orders exist
    6. If any step fails: cleanup and raise error

    Example:
        oco_manager = OCOManager(order_executor, position_tracker, exchange_adapter)

        result = await oco_manager.create_bracketed_order({
            "symbol": "BTC/USDT:USDT",
            "side": "LONG",
            "size": 0.01,
            "take_profit": 1.01,
            "stop_loss": 0.99
        })
    """

    def __init__(self, order_executor, position_tracker: PositionTracker, exchange_adapter):
        """
        Initialize OCOManager.

        Args:
            order_executor: OrderExecutor instance
            position_tracker: PositionTracker instance
            exchange_adapter: ExchangeAdapter for price fetching
        """
        self.executor = order_executor
        self.tracker = position_tracker
        self.adapter = exchange_adapter
        self.error_handler = get_error_handler()
        self.logger = logging.getLogger("OCOManager")

        # Retry configuration for TP/SL operations (more aggressive than market orders)
        self.tpsl_retry_config = RetryConfig(
            max_retries=5, backoff_base=0.5, backoff_factor=1.5, backoff_max=10.0, jitter=True
        )

    async def create_bracketed_order(
        self, order: Dict[str, Any], wait_for_fill: bool = True, fill_timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Create complete OCO bracket order with atomicity guarantees.

        Args:
            order: Order dict with:
                - symbol: Trading symbol
                - side: "LONG" or "SHORT"
                - size: Position size (fraction of equity)
                - take_profit: TP multiplier (e.g., 1.01 = +1%)
                - stop_loss: SL multiplier (e.g., 0.99 = -1%)
            wait_for_fill: Whether to wait for main order fill
            fill_timeout: Timeout for fill confirmation (seconds)

        Returns:
            Dict with:
                - main_order: Main order result
                - tp_order: Take profit order result
                - sl_order: Stop loss order result
                - fill_price: Actual fill price

        Raises:
            OCOAtomicityError: If OCO bracket creation fails
            TimeoutError: If fill confirmation times out
        """
        symbol = order["symbol"]
        side = order["side"]

        self.logger.info(
            f"🛡️ Creating OCO bracket for {symbol} {side} | "
            f"TP: {order.get('take_profit', 0):.4f} | SL: {order.get('stop_loss', 0):.4f}"
        )

        # Validate TP/SL presence
        if "take_profit" not in order or "stop_loss" not in order:
            raise ValueError("Order must contain 'take_profit' and 'stop_loss'")

        main_order = None
        tp_order = None
        sl_order = None

        try:
            # Step 1: Execute main market order
            main_order = await self._execute_main_order(order)

            # Log the response for debugging
            self.logger.debug(f"Main order response: {main_order}")

            # Validate main_order has required fields
            if not main_order:
                raise OCOAtomicityError("Main order returned None")

            if "order_id" not in main_order and "id" not in main_order:
                self.logger.error(f"Main order missing order_id. Response: {main_order}")
                raise OCOAtomicityError(f"Main order missing order_id. Got: {list(main_order.keys())}")

            # Normalize order_id field (some exchanges use 'id' instead of 'order_id')
            order_id = main_order.get("order_id") or main_order.get("id")

            # Step 2: Wait for fill confirmation or use immediate response
            if wait_for_fill:
                fill_price = await self._wait_for_fill(order_id, symbol, timeout=fill_timeout)
            else:
                # For market orders, use response price immediately (faster)
                # The connector is responsible for normalizing the price (including calculating from cumQuote if needed)

                # DEBUG: Log the full response
                self.logger.info(f"🔍 DEBUG: main_order keys = {list(main_order.keys())}")

                # Use standard normalized fields
                fill_price = main_order.get("price") or main_order.get("avgPrice") or main_order.get("average")

                if fill_price and float(fill_price) > 0:
                    fill_price = float(fill_price)
                    self.logger.info(f"🔍 DEBUG: Using normalized fill_price = {fill_price}")
                else:
                    fill_price = None

                # Last resort: check fills array (standard CCXT structure)
                if not fill_price and main_order.get("fills"):
                    fills = main_order["fills"]
                    if fills and len(fills) > 0:
                        fill_price = fills[0].get("price")
                        if fill_price:
                            fill_price = float(fill_price)
                            self.logger.info(f"🔍 DEBUG: From fills[0], fill_price = {fill_price}")

            # If we still don't have a price (e.g. order status is NEW), we MUST wait for fill
            if not fill_price or fill_price <= 0:
                self.logger.info("⏳ Fill price not in response (status NEW?), waiting for fill...")
                try:
                    fill_price = await self._wait_for_fill(order_id, symbol, timeout=fill_timeout)
                except Exception as e:
                    self.logger.error(f"❌ Failed to wait for fill: {e}")
                    raise OCOAtomicityError(f"Failed to get fill price: {e}")

            self.logger.info(f"✅ Main order filled @ {fill_price}")

            # Step 3: Calculate TP/SL prices
            tp_price, sl_price = self._calculate_tp_sl_prices(
                fill_price, side, order["take_profit"], order["stop_loss"]
            )

            # Step 4: Create TP order
            tp_order = await self._create_tp_order(symbol, side, main_order["amount"], tp_price)

            # Step 5: Create SL order
            sl_order = await self._create_sl_order(symbol, side, main_order["amount"], sl_price)

            # Step 6: Validate OCO completeness
            self._validate_oco_complete(main_order, tp_order, sl_order)

            self.logger.info(
                f"✅ OCO bracket created: Main={main_order.get('order_id') or main_order.get('id')}, "
                f"TP={tp_order.get('order_id') or tp_order.get('id')}, "
                f"SL={sl_order.get('order_id') or sl_order.get('id')}"
            )

            return {
                "main_order": main_order,
                "tp_order": tp_order,
                "sl_order": sl_order,
                "fill_price": fill_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
            }

        except Exception as e:
            # Cleanup on failure
            self.logger.error(f"❌ OCO bracket creation failed: {e}")
            await self._cleanup_partial_oco(main_order, tp_order, sl_order)
            raise OCOAtomicityError(f"Failed to create OCO bracket: {e}") from e

    async def _execute_main_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute main market order."""
        # Convert from trading order to exchange order format
        exchange_order = {
            "symbol": order["symbol"],
            "type": "market",
            "side": "buy" if order["side"] == "LONG" else "sell",
            "amount": order.get("amount", 0),  # Will be calculated by Croupier
        }

        return await self.executor.execute_market_order(exchange_order)

    async def _wait_for_fill(self, order_id: str, symbol: str, timeout: float = 30.0) -> Optional[float]:
        """
        Wait for order fill confirmation via WebSocket or polling.

        Args:
            order_id: Order ID to wait for
            symbol: Trading symbol (required by some connectors)
            timeout: Timeout in seconds

        Returns:
            Fill price or None if timeout

        Raises:
            TimeoutError: If fill not confirmed within timeout
        """
        start_time = time.time()

        # TODO: Subscribe to WebSocket updates if available
        # For now, use polling fallback

        while time.time() - start_time < timeout:
            try:
                # Fetch order status from exchange (pass symbol for Binance)
                order_info = await self.adapter.fetch_order(order_id, symbol)
                status = order_info.get("status")

                # DEBUG: Log status during polling
                self.logger.debug(f"⏳ Polling order {order_id}: status={status}")

                if status == "closed":
                    fill_price = order_info.get("average") or order_info.get("price")
                    if fill_price and float(fill_price) > 0:
                        return float(fill_price)

                await asyncio.sleep(1)
            except Exception as e:
                self.logger.warning(f"⚠️ Error fetching order status: {e}")

            # The sleep is now inside the try block, so this one is removed.
            # await asyncio.sleep(0.5)  # Poll every 500ms

        raise TimeoutError(f"Order {order_id} not filled within {timeout}s")

    def _calculate_tp_sl_prices(
        self, entry_price: float, side: str, tp_pct: float, sl_pct: float
    ) -> tuple[float, float]:
        """
        Calculate absolute TP/SL prices from percentages.

        Args:
            entry_price: Entry price
            side: "LONG" or "SHORT"
            tp_pct: TP percentage (e.g., 0.01 for 1%)
            sl_pct: SL percentage (e.g., 0.01 for 1%)

        Returns:
            (tp_price, sl_price) tuple
        """
        if side == "LONG":
            tp_price = entry_price * (1 + tp_pct)
            sl_price = entry_price * (1 - sl_pct)
        else:  # SHORT
            tp_price = entry_price * (1 - tp_pct)
            sl_price = entry_price * (1 + sl_pct)

        return tp_price, sl_price

    async def _create_tp_order(self, symbol: str, side: str, amount: float, tp_price: float) -> Dict[str, Any]:
        """Create take profit limit order with retry logic."""
        # TP is opposite side of entry
        tp_side = "sell" if side == "LONG" else "buy"

        self.logger.info(f"📈 Creating TP order @ {tp_price}")

        # Use error handler with retry for TP order creation
        return await self.error_handler.execute_with_breaker(
            "oco_tp_orders",
            self.executor.execute_limit_order,
            symbol=symbol,
            side=tp_side,
            amount=amount,
            price=tp_price,
            retry_config=self.tpsl_retry_config,
        )

    async def _create_sl_order(self, symbol: str, side: str, amount: float, sl_price: float) -> Dict[str, Any]:
        """Create stop loss order with retry logic."""
        # SL is opposite side of entry
        sl_side = "sell" if side == "LONG" else "buy"

        self.logger.info(f"📉 Creating SL order @ stop {sl_price}")

        # Use error handler with retry for SL order creation
        return await self.error_handler.execute_with_breaker(
            "oco_sl_orders",
            self.executor.execute_stop_order,
            symbol=symbol,
            side=sl_side,
            amount=amount,
            stop_price=sl_price,
            retry_config=self.tpsl_retry_config,
        )

    def _validate_oco_complete(
        self, main_order: Optional[Dict], tp_order: Optional[Dict], sl_order: Optional[Dict]
    ) -> None:
        """
        Validate that all 3 orders exist.

        Raises:
            OCOAtomicityError: If any order is missing
        """
        if not main_order:
            raise OCOAtomicityError("Main order is missing")
        if not tp_order:
            raise OCOAtomicityError("TP order is missing")
        if not sl_order:
            raise OCOAtomicityError("SL order is missing")

        # Validate order IDs exist
        if not (main_order.get("order_id") or main_order.get("id")):
            raise OCOAtomicityError("Main order has no order_id")
        if not (tp_order.get("order_id") or tp_order.get("id")):
            raise OCOAtomicityError("TP order has no order_id")
        if not (sl_order.get("order_id") or sl_order.get("id")):
            raise OCOAtomicityError("SL order has no order_id")

        self.logger.debug("✅ OCO validation passed: all 3 orders exist")

    async def _cleanup_partial_oco(
        self, main_order: Optional[Dict], tp_order: Optional[Dict], sl_order: Optional[Dict]
    ) -> None:
        """
        Cleanup partial OCO bracket on failure.

        Cancels any orders that were created before failure.
        """
        self.logger.warning("🧹 Cleaning up partial OCO bracket...")

        orders_to_cancel = []

        if tp_order and tp_order.get("order_id"):
            orders_to_cancel.append(("TP", tp_order["order_id"]))
        if sl_order and sl_order.get("order_id"):
            orders_to_cancel.append(("SL", sl_order["order_id"]))
        if main_order and main_order.get("order_id"):
            # Only cancel main if not filled yet
            if main_order.get("status") != "closed":
                orders_to_cancel.append(("Main", main_order["order_id"]))

        for order_type, order_id in orders_to_cancel:
            try:
                await self.adapter.cancel_order(order_id)
                self.logger.info(f"✅ Cancelled {order_type} order: {order_id}")
            except Exception as e:
                self.logger.error(f"❌ Failed to cancel {order_type} order {order_id}: {e}")

        if orders_to_cancel:
            self.logger.warning(f"🧹 Cleaned up {len(orders_to_cancel)} orders")

    async def cancel_bracket(self, tp_order_id: Optional[str], sl_order_id: Optional[str]) -> None:
        """
        Cancel TP and SL orders for a position with retry logic.
        """
        cancel_retry_config = RetryConfig(max_retries=3, backoff_base=0.3, backoff_factor=2.0, jitter=True)

        if tp_order_id:
            try:
                await self.error_handler.execute_with_breaker(
                    "oco_cancel", self.adapter.cancel_order, tp_order_id, retry_config=cancel_retry_config
                )
                self.logger.info(f"✅ Cancelled TP order: {tp_order_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to cancel TP order {tp_order_id}: {e}")

        if sl_order_id:
            try:
                await self.error_handler.execute_with_breaker(
                    "oco_cancel", self.adapter.cancel_order, sl_order_id, retry_config=cancel_retry_config
                )
                self.logger.info(f"✅ Cancelled SL order: {sl_order_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to cancel SL order {sl_order_id}: {e}")
