"""
Simulated Connector - Casino V2

Equivalente a BybitConnector/KrakenConnector pero para backtest.
Simula ejecución de órdenes con slippage y fees realistas.
"""

import logging
from typing import Dict, List, Optional

from exchanges.connectors.connector_base import BaseConnector


class SimulatedConnector(BaseConnector):
    """
    Connector simulado para backtesting.

    Equivalente a BybitConnector pero simula:
    - Validación de límites (min/max amount, precision)
    - Slippage realista
    - Fees de exchange
    - Ejecución instantánea

    Mantiene la misma interface que conectores reales para
    garantizar que el backtest refleje el comportamiento de live.
    """

    def __init__(
        self,
        data_source,
        fee_rate: float = 0.0006,  # 0.06% (Kraken taker)
        slippage_rate: float = 0.0001,  # 0.01%
        spread_rate: float = 0.0001,  # 0.01% spread bid/ask
        min_amount: float = 0.001,  # Mínimo BTC (similar a Bybit)
        amount_precision: int = 3,  # Decimales para BTC
    ):
        """
        Initialize simulated connector.

        Args:
            data_source: BacktestDataSource instance (para acceder a datos)
            fee_rate: Trading fee rate (0.0006 = 0.06%)
            slippage_rate: Simulated slippage (0.0001 = 0.01%)
            spread_rate: Bid/ask spread (0.0001 = 0.01%)
            min_amount: Minimum order amount (similar a límites reales)
            amount_precision: Decimales para redondeo de amount
        """
        super().__init__()
        self.logger = logging.getLogger("SimulatedConnector")

        self.data_source = data_source
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.spread_rate = spread_rate
        self.min_amount = min_amount
        self.amount_precision = amount_precision

        # Metadata (compatible con BaseConnector)
        self._exchange_name = "Simulated"
        self.base_currency = "USD"
        self._ready = True
        self._connected = False

        # Internal order book to emulate exchange OCO behaviour
        # order_id -> order_dict (status: 'open'|'closed'|'canceled')
        self._orders: Dict[str, Dict] = {}
        # Simple sequence to ensure unique order IDs when multiple orders
        # are created at the same timestamp with same side/amount
        self._order_seq = 0

        self.logger.info(
            f"🎮 SimulatedConnector initialized | "
            f"Fee: {fee_rate*100:.2f}% | "
            f"Slippage: {slippage_rate*100:.2f}% | "
            f"Min amount: {min_amount}"
        )

    # =========================================================
    # CONNECTION (Simulated - always ready)
    # =========================================================

    async def connect(self) -> None:
        """Connect (no-op for simulation)."""
        self._ready = True
        self._connected = True
        self.logger.debug("✅ SimulatedConnector ready")

    async def disconnect(self) -> None:
        """Disconnect (no-op for simulation)."""
        self._ready = False
        self._connected = False
        self.logger.debug("🔌 SimulatedConnector disconnected")

    async def close(self) -> None:
        """Close (alias for disconnect)."""
        await self.disconnect()

    @property
    def ready(self) -> bool:
        """Check if connector is ready."""
        return self._ready

    @property
    def status_dict(self) -> Dict:
        """Get connector status."""
        return {"ready": self._ready, "exchange": "Simulated", "mode": "backtest"}

    # =========================================================
    # ORDER EXECUTION (Core functionality)
    # =========================================================

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        """
        Simulate order creation.

        Valida límites (como BybitConnector) y simula ejecución.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order amount
            order_type: 'market' or 'limit'
            price: Limit price (optional)
            params: Additional parameters

        Returns:
            Order result dict

        Raises:
            ValueError: If amount doesn't meet requirements
        """
        # 1. Validate amount (IGUAL que BybitConnector)
        amount_rounded = round(amount, self.amount_precision)

        if amount_rounded < self.min_amount:
            raise ValueError(
                f"Order amount {amount} (rounded to {amount_rounded}) "
                f"is below minimum {self.min_amount} for {symbol}. "
                f"Please increase order size to at least {self.min_amount}."
            )

        # 2. Get current price
        current_price = self._get_current_price()
        entry_price = price if order_type == "limit" and price else current_price

        # 3. Apply spread (bid/ask difference)
        if side.lower() == "buy":
            # Buy at ask price (higher)
            entry_price = entry_price * (1 + self.spread_rate)
        else:
            # Sell at bid price (lower)
            entry_price = entry_price * (1 - self.spread_rate)

        # 4. Apply slippage (peor precio adicional)
        if side.lower() == "buy":
            entry_price = entry_price * (1 + self.slippage_rate)
        else:
            entry_price = entry_price * (1 - self.slippage_rate)

        # 5. Calculate fee
        notional = amount_rounded * entry_price
        fee_cost = notional * self.fee_rate

        # 6. Generate order ID
        timestamp = self.data_source._get_current_timestamp()
        self._order_seq += 1
        order_id = f"sim_{timestamp}_{side}_{amount_rounded}_{self._order_seq}"

        # Build order object (store in internal order book)
        order_obj = {
            "id": order_id,
            "symbol": symbol,
            "side": side.lower(),
            "type": order_type,
            "amount": amount_rounded,
            "price": entry_price,
            "cost": notional,
            "fee": {"cost": fee_cost, "currency": self.base_currency, "rate": self.fee_rate},
            "timestamp": timestamp,
            "datetime": str(timestamp),
            "params": params or {},
        }

        # For STOP / TAKE orders we keep them OPEN until the market hits stopPrice
        if order_type and ("stop" in order_type or "take_profit" in order_type):
            order_obj["status"] = "open"
            # store stopPrice if provided
            order_obj["stopPrice"] = (params or {}).get("stopPrice")
            # If caller didn't provide a parent mapping, try to infer the
            # parent (main) order: choose the last non-conditional order for
            # the same symbol.
            if not (params or {}).get("parent"):
                parent_id = None
                # find candidate orders ordered by timestamp descending
                candidates = sorted(
                    [o for o in self._orders.values() if o.get("symbol") == symbol],
                    key=lambda x: x.get("timestamp", 0),
                    reverse=True,
                )
                for cand in candidates:
                    ctype = (cand.get("type") or "").lower()
                    if ctype and ("stop" in ctype or "take_profit" in ctype):
                        # skip conditional orders
                        continue
                    # accept market/limit orders as parent
                    parent_id = cand.get("id")
                    break
                if parent_id:
                    order_obj["parent"] = parent_id
            else:
                order_obj["parent"] = (params or {}).get("parent")
            order_obj["filled"] = 0.0
            self._orders[order_id] = order_obj
            self.logger.info(
                f"📝 Conditional order created | {order_obj['type']} {amount_rounded} @ stop={order_obj.get('stopPrice')} | id={order_id}"
            )
            return order_obj

        # By default market/limit orders execute instantly (closed)
        order_obj["status"] = "closed"
        order_obj["filled"] = amount_rounded

        self._orders[order_id] = order_obj

        self.logger.info(
            f"📝 Order simulated | "
            f"{side.upper()} {amount_rounded} @ {entry_price:.2f} | "
            f"Fee: {fee_cost:.4f} | id={order_id}"
        )

        # 7. Return result (formato compatible con CCXT)
        return order_obj

    def create_order_sync(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        """
        Synchronous version of create_order for backtest.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order amount
            order_type: 'market' or 'limit'
            price: Limit price (optional)
            params: Additional parameters

        Returns:
            Order result dict
        """
        # Same logic as async version but synchronous
        # 1. Validate amount
        amount_rounded = round(amount, self.amount_precision)

        if amount_rounded < self.min_amount:
            raise ValueError(
                f"Order amount {amount} (rounded to {amount_rounded}) "
                f"is below minimum {self.min_amount} for {symbol}. "
                f"Please increase order size to at least {self.min_amount}."
            )

        # 2. Get current price
        current_price = self._get_current_price()
        entry_price = price if order_type == "limit" and price else current_price

        # 3. Apply slippage
        if side.lower() == "buy":
            entry_price = entry_price * (1 + self.slippage_rate)
        else:
            entry_price = entry_price * (1 - self.slippage_rate)

        # 4. Calculate fee
        notional = amount_rounded * entry_price
        fee_cost = notional * self.fee_rate

        # 5. Generate order ID
        timestamp = self.data_source._get_current_timestamp()
        self._order_seq += 1
        order_id = f"sim_{timestamp}_{side}_{amount_rounded}_{self._order_seq}"

        order_obj = {
            "id": order_id,
            "symbol": symbol,
            "side": side.lower(),
            "type": order_type,
            "amount": amount_rounded,
            "price": entry_price,
            "cost": notional,
            "fee": {"cost": fee_cost, "currency": self.base_currency, "rate": self.fee_rate},
            "timestamp": timestamp,
            "datetime": str(timestamp),
            "params": params or {},
        }

        if order_type and ("stop" in order_type or "take_profit" in order_type):
            order_obj["status"] = "open"
            order_obj["stopPrice"] = (params or {}).get("stopPrice")
            order_obj["filled"] = 0.0
            self._orders[order_id] = order_obj
            self.logger.info(
                f"📝 Conditional order created | {order_obj['type']} {amount_rounded} @ stop={order_obj.get('stopPrice')} | id={order_id}"
            )
            return order_obj

        order_obj["status"] = "closed"
        order_obj["filled"] = amount_rounded
        self._orders[order_id] = order_obj

        self.logger.info(
            f"📝 Order simulated | "
            f"{side.upper()} {amount_rounded} @ {entry_price:.2f} | "
            f"Fee: {fee_cost:.4f} | id={order_id}"
        )

        return order_obj

    # =========================================================
    # MARKET DATA (Simulated)
    # =========================================================

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Fetch OHLCV data from backtest data source.

        Args:
            symbol: Trading pair
            timeframe: Candle interval
            since: Start timestamp
            limit: Number of candles

        Returns:
            List of candle dicts
        """
        # Delegate to data source
        return self.data_source._get_ohlcv(limit or 1)

    async def fetch_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Return a stored order by id.
        """
        return self._orders.get(order_id)

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Return all open conditional orders for a symbol.
        """
        orders = [o for o in self._orders.values() if o.get("status") == "open"]
        if symbol:
            orders = [o for o in orders if o.get("symbol") == symbol]
        return orders

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict:
        """
        Cancel an open order and return the updated order.
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order.get("status") != "open":
            return order
        order["status"] = "canceled"
        order["canceled_timestamp"] = self.data_source._get_current_timestamp()
        self._orders[order_id] = order
        self.logger.info(f"🛑 Order canceled | id={order_id}")
        return order

    async def fetch_ticker(self, symbol: str) -> Dict:
        """
        Get current ticker (simulated).

        Args:
            symbol: Trading pair

        Returns:
            Ticker dict with current price
        """
        current_price = self._get_current_price()
        timestamp = self.data_source._get_current_timestamp()

        return {
            "symbol": symbol,
            "last": current_price,
            "bid": current_price * (1 - self.slippage_rate),
            "ask": current_price * (1 + self.slippage_rate),
            "timestamp": timestamp,
        }

    async def fetch_balance(self) -> Dict:
        """
        Get balance from backtest data source.

        Returns:
            Balance dict
        """
        balance = self.data_source.balance

        return {
            self.base_currency: {
                "free": balance,
                "used": 0.0,
                "total": balance,
            },
            "free": {self.base_currency: balance},
            "used": {self.base_currency: 0.0},
            "total": {self.base_currency: balance},
        }

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """
        Get open positions from backtest data source.

        Args:
            symbols: List of symbols to filter (optional)

        Returns:
            List of position dicts
        """
        positions = []

        for pos in self.data_source.open_positions:
            positions.append(
                {
                    "symbol": pos["symbol"],
                    "side": "long" if pos["side"] == "buy" else "short",
                    "contracts": pos["amount"],
                    "entryPrice": pos["entry_price"],
                    "unrealizedPnl": self._calculate_unrealized_pnl(pos),
                    "timestamp": pos["timestamp"],
                }
            )

        return positions

    async def fetch_my_trades(
        self,
        symbol: Optional[str] = None,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get closed trades from backtest data source.

        Args:
            symbol: Trading pair (optional)
            since: Start timestamp (optional)
            limit: Max number of trades (optional)

        Returns:
            List of trade dicts
        """
        trades = self.data_source.closed_trades

        if limit:
            trades = trades[-limit:]

        return [
            {
                "id": trade.get("trade_id"),
                "symbol": trade["symbol"],
                "side": trade["side"],
                "amount": trade["amount"],
                "price": trade.get("exit_price", trade["entry_price"]),
                "cost": trade["amount"] * trade.get("exit_price", trade["entry_price"]),
                "fee": {"cost": trade.get("fee", 0)},
                "timestamp": trade.get("timestamp"),
            }
            for trade in trades
        ]

    # =========================================================
    # HELPER METHODS
    # =========================================================

    def _get_current_price(self) -> float:
        """Get current price from data source."""
        if self.data_source.index > 0:
            return float(self.data_source.data.iloc[self.data_source.index - 1]["close"])
        else:
            return float(self.data_source.data.iloc[0]["close"])

    def _mark_orders_for_position_closure(self, position: Dict, exit_price: float, exit_reason: str) -> None:
        """
        Called when a position is closed by the data source.
        This method will mark matching TP/SL orders as closed and cancel siblings.

        Matching strategy: look for open orders with same symbol and amount
        and whose stopPrice is close to the TP/SL level derived from position.
        """
        try:
            symbol = position.get("symbol")
            amount = position.get("amount")
            entry = position.get("entry_price")

            # Compute expected TP/SL absolute prices if provided
            tp_mult = position.get("take_profit")
            sl_mult = position.get("stop_loss")
            tp_price = entry * tp_mult if tp_mult else None
            sl_price = entry * sl_mult if sl_mult else None

            # First, try to match by parent main_order_id if present in position
            parent_id = position.get("main_order_id")
            if parent_id:
                for oid, o in list(self._orders.items()):
                    if o.get("status") != "open":
                        continue
                    if o.get("parent") == parent_id:
                        # mark filled
                        o["status"] = "closed"
                        o["filled"] = o.get("amount")
                        o["price"] = exit_price
                        o["closed_timestamp"] = self.data_source._get_current_timestamp()
                        self.logger.info(f"✅ Conditional order filled by parent (sim) | id={oid} @ {exit_price}")
                        # cancel siblings
                        for soid, so in list(self._orders.items()):
                            if soid == oid:
                                continue
                            if so.get("status") == "open" and so.get("parent") == parent_id:
                                so["status"] = "canceled"
                                so["canceled_timestamp"] = self.data_source._get_current_timestamp()
                                self.logger.info(f"🔄 Sibling order canceled (sim) | id={soid}")
                return

            # Fallback to price heuristics if no parent mapping
            for oid, o in list(self._orders.items()):
                if o.get("status") != "open":
                    continue
                if o.get("symbol") != symbol:
                    continue

                stop = o.get("stopPrice")
                # If stop is very close to tp_price or sl_price, mark closed
                if tp_price and stop and abs(stop - tp_price) / tp_price < 0.001:
                    # mark filled
                    o["status"] = "closed"
                    o["filled"] = o.get("amount")
                    o["price"] = exit_price
                    o["closed_timestamp"] = self.data_source._get_current_timestamp()
                    self.logger.info(f"✅ TP order filled (sim) | id={oid} @ {exit_price}")
                    # Cancel sibling orders for same position
                    # sibling: other open orders with same symbol and amount
                    for soid, so in list(self._orders.items()):
                        if soid == oid:
                            continue
                        if so.get("status") == "open" and so.get("symbol") == symbol and so.get("amount") == amount:
                            so["status"] = "canceled"
                            so["canceled_timestamp"] = self.data_source._get_current_timestamp()
                            self.logger.info(f"🔄 Sibling order canceled (sim) | id={soid}")

                if sl_price and stop and abs(stop - sl_price) / sl_price < 0.001:
                    o["status"] = "closed"
                    o["filled"] = o.get("amount")
                    o["price"] = exit_price
                    o["closed_timestamp"] = self.data_source._get_current_timestamp()
                    self.logger.info(f"✅ SL order filled (sim) | id={oid} @ {exit_price}")
                    for soid, so in list(self._orders.items()):
                        if soid == oid:
                            continue
                        if so.get("status") == "open" and so.get("symbol") == symbol and so.get("amount") == amount:
                            so["status"] = "canceled"
                            so["canceled_timestamp"] = self.data_source._get_current_timestamp()
                            self.logger.info(f"🔄 Sibling order canceled (sim) | id={soid}")
        except Exception as e:
            self.logger.error(f"❌ Error marking orders for position closure: {e}")

    def _calculate_unrealized_pnl(self, position: Dict) -> float:
        """Calculate unrealized PnL for a position."""
        current_price = self._get_current_price()
        entry_price = position["entry_price"]
        amount = position["amount"]
        side = position["side"]

        if side == "buy":
            pnl = (current_price - entry_price) * amount
        else:
            pnl = (entry_price - current_price) * amount

        return pnl

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol (no-op for simulation).

        Args:
            symbol: Trading pair

        Returns:
            Normalized symbol
        """
        return symbol

    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """
        Denormalize symbol (no-op for simulation).

        Args:
            exchange_symbol: Exchange-specific symbol

        Returns:
            Standard symbol
        """
        return exchange_symbol

    @property
    def exchange_name(self) -> str:
        """Get exchange name."""
        return self._exchange_name

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
