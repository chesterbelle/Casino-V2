"""
OrderExecutor - Handles individual order execution with retry logic.

This component is responsible for:
- Executing market, limit, and stop orders
- Integrating with ErrorHandler for intelligent retry
- Validating order parameters
- Converting order results to standardized format

Author: Casino V3 Team
Version: 3.0.0
"""

import logging
from typing import Any, Dict, Optional

from core.error_handling import RetryConfig, get_error_handler


class OrderExecutor:
    """
    Executes individual orders with retry and error handling.

    Delegates actual execution to ExchangeAdapter but adds:
    - Intelligent retry logic via ErrorHandler
    - Order validation
    - Standardized error handling

    Example:
        executor = OrderExecutor(exchange_adapter)

        result = await executor.execute_market_order({
            "symbol": "BTC/USDT:USDT",
            "side": "buy",
            "amount": 0.01
        })
    """

    def __init__(self, exchange_adapter, error_handler=None):
        """
        Initialize OrderExecutor.

        Args:
            exchange_adapter: ExchangeAdapter instance for order execution
            error_handler: Optional ErrorHandler (uses global if None)
        """
        self.adapter = exchange_adapter
        self.error_handler = error_handler or get_error_handler()
        self.logger = logging.getLogger("OrderExecutor")

    async def execute_market_order(
        self, order: Dict[str, Any], retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """
        Execute market order with retry logic.

        Args:
            order: Order dict with symbol, side, amount
            retry_config: Optional retry configuration

        Returns:
            Order result dict with order_id, status, filled_price, etc.

        Raises:
            ValidationError: If order validation fails
            ExchangeError: If order execution fails after retries
        """
        # Validate order
        self._validate_market_order(order)

        # Execute with retry
        retry_cfg = retry_config or RetryConfig(max_retries=3, backoff_base=1.0, backoff_factor=2.0, jitter=True)

        self.logger.info(f"📤 Executing market order: {order['side']} {order['amount']} {order['symbol']}")

        result = await self.error_handler.execute_with_breaker(
            "exchange_orders", self.adapter.execute_order, order, retry_config=retry_cfg
        )

        self.logger.info(f"✅ Market order executed: {result.get('order_id')} | " f"Status: {result.get('status')}")

        return result

    async def execute_limit_order(
        self, symbol: str, side: str, amount: float, price: float, retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """
        Execute limit order with retry logic.

        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            amount: Order amount
            price: Limit price
            retry_config: Optional retry configuration

        Returns:
            Order result dict
        """
        order = {"symbol": symbol, "type": "limit", "side": side, "amount": amount, "price": price}

        self._validate_limit_order(order)

        retry_cfg = retry_config or RetryConfig(max_retries=3)

        self.logger.info(f"📤 Executing limit order: {side} {amount} {symbol} @ {price}")

        result = await self.error_handler.execute_with_breaker(
            "exchange_orders", self.adapter.execute_order, order, retry_config=retry_cfg
        )

        self.logger.info(f"✅ Limit order executed: {result.get('order_id')}")

        return result

    async def execute_stop_order(
        self, symbol: str, side: str, amount: float, stop_price: float, retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """
        Execute stop order with retry logic.

        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            amount: Order amount
            stop_price: Stop trigger price
            retry_config: Optional retry configuration

        Returns:
            Order result dict
        """
        order = {"symbol": symbol, "type": "stop", "side": side, "amount": amount, "stopPrice": stop_price}

        self._validate_stop_order(order)

        retry_cfg = retry_config or RetryConfig(max_retries=3)

        self.logger.info(f"📤 Executing stop order: {side} {amount} {symbol} @ stop {stop_price}")

        result = await self.error_handler.execute_with_breaker(
            "exchange_orders", self.adapter.execute_order, order, retry_config=retry_cfg
        )

        self.logger.info(f"✅ Stop order executed: {result.get('order_id')}")

        return result

    def _validate_market_order(self, order: Dict[str, Any]) -> None:
        """
        Validate market order parameters.

        Args:
            order: Order dict

        Raises:
            ValueError: If validation fails
        """
        required_fields = ["symbol", "side", "amount"]
        for field in required_fields:
            if field not in order:
                raise ValueError(f"Missing required field: {field}")

        if order["amount"] <= 0:
            raise ValueError(f"Invalid amount: {order['amount']}")

        if order["side"] not in ["buy", "sell"]:
            raise ValueError(f"Invalid side: {order['side']}")

    def _validate_limit_order(self, order: Dict[str, Any]) -> None:
        """Validate limit order parameters."""
        self._validate_market_order(order)

        if "price" not in order:
            raise ValueError("Missing required field: price")

        if order["price"] <= 0:
            raise ValueError(f"Invalid price: {order['price']}")

    def _validate_stop_order(self, order: Dict[str, Any]) -> None:
        """Validate stop order parameters."""
        self._validate_market_order(order)

        if "stopPrice" not in order:
            raise ValueError("Missing required field: stopPrice")

        if order["stopPrice"] <= 0:
            raise ValueError(f"Invalid stopPrice: {order['stopPrice']}")
