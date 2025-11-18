"""
Simulated Adapter - Casino V2

Equivalente a CCXTAdapter pero para backtest.
Traduce multiplicadores a precios y delega a SimulatedConnector.
"""

import logging
from typing import Dict, Optional


class SimulatedAdapter:
    """
    Adapter simulado para backtesting.

    Equivalente a CCXTAdapter pero para simulación:
    - Traduce multiplicadores (take_profit, stop_loss) a precios absolutos
    - Calcula amount desde size (fracción del equity)
    - Delega ejecución al SimulatedConnector

    NO maneja balance ni posiciones (eso es responsabilidad del Croupier).
    Solo traduce y comunica, manteniendo la arquitectura modular.
    """

    def __init__(
        self,
        connector,
        symbol: str,
        timeframe: str = "1m",
    ):
        """
        Initialize simulated adapter.

        Args:
            connector: SimulatedConnector instance
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Candle interval (e.g., "1m", "5m", "1h")
        """
        self.logger = logging.getLogger("SimulatedAdapter")

        # Connector (dependency injection)
        self.connector = connector

        # Configuration
        self.symbol = symbol
        self.timeframe = timeframe
        self.base_currency = "USD"

        self.logger.info(f"🎮 SimulatedAdapter initialized | " f"Symbol: {symbol} | " f"Timeframe: {timeframe}")

    # =========================================================
    # CONNECTION MANAGEMENT
    # =========================================================

    async def connect(self) -> None:
        """Connect to simulated connector."""
        await self.connector.connect()
        self.logger.info("✅ SimulatedAdapter connected")

    async def close(self) -> None:
        """Close connection."""
        await self.connector.close()
        self.logger.info("🔌 SimulatedAdapter closed")

    # =========================================================
    # ORDER EXECUTION (Core functionality)
    # =========================================================

    def execute_order_sync(self, order: Dict) -> Dict:
        """
        Execute order synchronously (for Croupier compatibility).

        This is the main entry point called by Croupier.

        Args:
            order: Order dict with keys:
                - symbol: Trading pair
                - side: 'LONG' or 'SHORT'
                - size: Fraction of equity to risk (e.g., 0.02 = 2%)
                - take_profit: Multiplier (e.g., 1.01 = +1%)
                - stop_loss: Multiplier (e.g., 0.99 = -1%)
                - trade_id: Unique identifier

        Returns:
            Result dict with status, entry_price, amount, etc.
        """
        try:
            # 1. Get current price
            current_price = self.connector._get_current_price()

            # 2. Get current balance (from Croupier's portfolio)
            # NOTE: Croupier ya validó fondos, aquí solo calculamos
            balance = self.connector.data_source.balance

            # 3. Calculate amount from size
            # size = fracción del equity a arriesgar
            # amount = (size * balance) / current_price
            size = order.get("size", 0.02)  # Default 2%
            amount = (size * balance) / current_price

            # 4. Translate side
            side_map = {"LONG": "buy", "SHORT": "sell"}
            side = side_map.get(order["side"], order["side"].lower())

            # 5. Translate multipliers to absolute prices
            tp_mult = order.get("take_profit")
            sl_mult = order.get("stop_loss")

            tp_price = current_price * tp_mult if tp_mult else None
            sl_price = current_price * sl_mult if sl_mult else None

            self.logger.debug(
                f"📊 Translating order | "
                f"Size: {size:.2%} → Amount: {amount:.6f} | "
                f"TP mult: {tp_mult} → {tp_price} | "
                f"SL mult: {sl_mult} → {sl_price}"
            )

            # 6. Execute via connector (call sync version for backtest)
            # NOTE: In backtest, we only create the main order
            # TP/SL are handled by PositionTracker in "simulation" mode
            result = self.connector.create_order_sync(
                symbol=order.get("symbol", self.symbol),
                side=side,
                amount=amount,
            )

            # 7. Format result for Croupier
            # NOTE: tp_order_id and sl_order_id are None in backtest
            # PositionTracker will handle TP/SL detection in simulation mode
            return {
                "id": result["id"],
                "status": "opened",
                "trade_id": order.get("trade_id"),
                "symbol": result["symbol"],
                "side": order["side"],  # Keep original format (LONG/SHORT)
                "amount": result["amount"],
                "entry_price": result["price"],
                "fee": result["fee"]["cost"],
                "tp_price": tp_price,
                "sl_price": sl_price,
                "tp_order_id": None,  # Not created in backtest
                "sl_order_id": None,  # Not created in backtest
                "timestamp": result["timestamp"],
            }

        except ValueError as e:
            # Validation error from connector (e.g., amount below minimum)
            self.logger.error(f"❌ Validation error: {e}")
            return {
                "status": "rejected",
                "reason": str(e),
                "order": order,
            }
        except Exception as e:
            # Unexpected error
            self.logger.error(f"❌ Execution error: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
                "order": order,
            }

    async def execute_order(self, order: Dict) -> Dict:
        """
        Execute order asynchronously (for compatibility).

        Args:
            order: Order dict

        Returns:
            Result dict
        """
        # For backtest, just call sync version
        return self.execute_order_sync(order)

    # =========================================================
    # MARKET DATA (Delegated to connector)
    # =========================================================

    async def fetch_ohlcv(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        Fetch OHLCV data.

        Args:
            symbol: Trading pair (uses self.symbol if None)
            timeframe: Candle interval (uses self.timeframe if None)
            limit: Number of candles

        Returns:
            List of candle dicts
        """
        return await self.connector.fetch_ohlcv(symbol or self.symbol, timeframe or self.timeframe, limit=limit)

    async def fetch_ticker(self, symbol: Optional[str] = None) -> Dict:
        """
        Get current ticker.

        Args:
            symbol: Trading pair (uses self.symbol if None)

        Returns:
            Ticker dict
        """
        return await self.connector.fetch_ticker(symbol or self.symbol)

    async def fetch_balance(self) -> Dict:
        """
        Get balance.

        Returns:
            Balance dict
        """
        return await self.connector.fetch_balance()

    async def fetch_positions(self) -> list:
        """
        Get open positions.

        Returns:
            List of position dicts
        """
        return await self.connector.fetch_positions()

    async def fetch_my_trades(
        self,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list:
        """
        Get closed trades.

        Args:
            symbol: Trading pair (optional)
            limit: Max number of trades (optional)

        Returns:
            List of trade dicts
        """
        return await self.connector.fetch_my_trades(symbol, limit=limit)

    # =========================================================
    # HELPER METHODS
    # =========================================================

    async def get_current_price(self, symbol: str = None) -> float:
        """
        Get current price (async for compatibility with CCXTAdapter).

        Args:
            symbol: Trading symbol (ignored in simulated mode, uses connector's current price)

        Returns:
            Current price
        """
        return self.connector._get_current_price()
