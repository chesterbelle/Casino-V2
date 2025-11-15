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
        order_id = f"sim_{timestamp}_{side}_{amount_rounded}"

        self.logger.info(
            f"📝 Order simulated | " f"{side.upper()} {amount_rounded} @ {entry_price:.2f} | " f"Fee: {fee_cost:.4f}"
        )

        # 7. Return result (formato compatible con CCXT)
        return {
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
            "status": "closed",  # Market orders se ejecutan instantáneamente
            "filled": amount_rounded,
            "remaining": 0.0,
        }

    async def create_order_with_tpsl(
        self,
        symbol: str,
        side: str,
        amount: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> Dict:
        """
        Simulate order with TP/SL.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order amount
            tp_price: Take profit price (absolute)
            sl_price: Stop loss price (absolute)
            order_type: 'market' or 'limit'
            price: Limit price (optional)

        Returns:
            Order result with TP/SL info
        """
        # Create main order
        result = await self.create_order(symbol, side, amount, order_type, price)

        # Add TP/SL info (se verificarán en next_candle)
        result["tp_price"] = tp_price
        result["sl_price"] = sl_price

        # Generate TP/SL order IDs for OCO tracking
        # In simulation, we generate synthetic IDs
        if tp_price:
            result["tp_order_id"] = f"SIM_TP_{result.get('id')}_{int(tp_price)}"
            self.logger.debug(f"  TP: {tp_price:.2f} (ID: {result['tp_order_id']})")

        if sl_price:
            result["sl_order_id"] = f"SIM_SL_{result.get('id')}_{int(sl_price)}"
            self.logger.debug(f"  SL: {sl_price:.2f} (ID: {result['sl_order_id']})")

        return result

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
        order_id = f"sim_{timestamp}_{side}_{amount_rounded}"

        self.logger.info(
            f"📝 Order simulated | " f"{side.upper()} {amount_rounded} @ {entry_price:.2f} | " f"Fee: {fee_cost:.4f}"
        )

        # 6. Return result
        return {
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
            "status": "closed",
            "filled": amount_rounded,
            "remaining": 0.0,
        }

    def create_order_with_tpsl_sync(
        self,
        symbol: str,
        side: str,
        amount: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> Dict:
        """
        Synchronous version of create_order_with_tpsl for backtest.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order amount
            tp_price: Take profit price (absolute)
            sl_price: Stop loss price (absolute)
            order_type: 'market' or 'limit'
            price: Limit price (optional)

        Returns:
            Order result with TP/SL info
        """
        # Create main order (synchronous)
        result = self.create_order_sync(symbol, side, amount, order_type, price)

        # Add TP/SL info
        result["tp_price"] = tp_price
        result["sl_price"] = sl_price

        if tp_price:
            self.logger.debug(f"  TP: {tp_price:.2f}")
        if sl_price:
            self.logger.debug(f"  SL: {sl_price:.2f}")

        return result

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
