"""
Testing Data Source - Casino V2

Provides real-time data from exchange demo/testnet.
Uses CCXTAdapter internally for balance/position management.
"""

import asyncio
import logging
from typing import Dict, Optional

from exchanges.adapters.ccxt_adapter import CCXTAdapter

from .base import Candle, DataSource

logger = logging.getLogger(__name__)


class TestingDataSource(DataSource):
    """
    Data source for testing with exchange demo/testnet.

    Features:
    - Real-time candles from demo exchange
    - Real order execution (no real money)
    - Real slippage and fees
    - Resilient connection (auto-reconnect)

    Example:
        >>> connector = ResilientConnector(KrakenConnector(mode="demo"))
        >>> source = TestingDataSource(connector, "BTC/USD", "5m")
        >>> await source.connect()
        >>> candle = await source.next_candle()
    """

    def __init__(
        self,
        connector,
        symbol: str,
        timeframe: str,
        poll_interval: float = 5.0,
        starting_balance: float = 10000.0,
    ):
        """
        Initialize testing data source.

        Args:
            connector: Exchange connector (should be ResilientConnector)
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Candle interval (e.g., "5m", "1h")
            poll_interval: Seconds to wait between candle checks
            starting_balance: Initial balance for testing
        """
        # Use CCXTAdapter internally for balance/position management
        self.adapter = CCXTAdapter(
            connector=connector,
            symbol=symbol,
            timeframe=timeframe,
            starting_balance=starting_balance,
        )
        self.symbol = symbol
        self.timeframe = timeframe
        self.poll_interval = poll_interval

        self._connected = False
        self._last_candle_timestamp = 0

        logger.info(
            f"📊 TestingDataSource initialized | "
            f"Symbol: {symbol} | "
            f"Timeframe: {timeframe} | "
            f"Poll: {poll_interval}s"
        )

    async def connect(self) -> None:
        """Connect to exchange demo."""
        if self._connected:
            return

        try:
            # Connect through adapter
            await self.adapter.connect()
            self._connected = True

            # Save initial balance for stats
            self.initial_balance = self.get_balance()

            logger.info("✅ Testing data source connected")

        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from exchange demo and force-close any open positions."""
        if not self._connected:
            return

        try:
            # Force close all open positions before disconnecting
            try:
                open_positions = await self.adapter.connector.fetch_positions()
                if open_positions:
                    logger.info(f"🔄 Force-closing {len(open_positions)} open position(s) at session end...")

                    for position in open_positions:
                        try:
                            # Only close positions with non-zero amount
                            if abs(float(position.get("contracts", 0))) > 0:
                                side = "sell" if position["side"] == "long" else "buy"
                                await self.adapter.connector.create_order(
                                    symbol=position["symbol"],
                                    side=side,
                                    amount=abs(float(position["contracts"])),
                                    order_type="market",
                                )
                                logger.info(
                                    f"✅ Force-closed position: {position['symbol']} "
                                    f"{position['side'].upper()} {position['contracts']}"
                                )
                        except Exception as e:
                            logger.error(f"❌ Failed to force-close position: {e}")
            except Exception as e:
                logger.debug(f"No positions to close or error fetching: {e}")

            await self.adapter.close()
            self._connected = False
            logger.info("🔌 Testing data source disconnected")

        except Exception as e:
            logger.warning(f"⚠️ Error disconnecting: {e}")

    async def next_candle(self) -> Optional[Candle]:
        """
        Get next candle from exchange demo.

        Waits for a new candle (polls every poll_interval seconds).

        Returns:
            Candle object or None on error
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        while True:
            try:
                # Fetch latest candle directly from connector (bypass adapter for now)
                logger.debug("🔄 Fetching candle from connector...")
                candles = await self.adapter.connector.fetch_ohlcv(self.symbol, self.timeframe, limit=1)

                if not candles:
                    logger.warning("⚠️ No candles received, retrying...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                candle_data = candles[0]

                # Extract timestamp
                timestamp = int(candle_data["timestamp"])
                logger.debug(f"📊 Received candle with timestamp: {timestamp}")

                # Check if it's a new candle
                if timestamp <= self._last_candle_timestamp:
                    # Same candle, wait for next
                    logger.debug(f"⏳ Same candle (ts={timestamp}), waiting for new one...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                # New candle!
                self._last_candle_timestamp = timestamp
                logger.info(f"✅ New candle received | ts={timestamp}")

                # Get balance/equity from adapter
                balance = self.adapter.balance_manager.balance
                equity = self.adapter.balance_manager.equity

                return Candle(
                    timestamp=timestamp,
                    open=float(candle_data["open"]),
                    high=float(candle_data["high"]),
                    low=float(candle_data["low"]),
                    close=float(candle_data["close"]),
                    volume=float(candle_data["volume"]),
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    equity=equity,
                    balance=balance,
                    unrealized_pnl=equity - balance,
                )

            except Exception as e:
                logger.error(f"❌ Error fetching candle: {e}")
                await asyncio.sleep(self.poll_interval)
                # Return None to signal error (session will handle it)
                return None

    async def execute_order(self, order: Dict) -> Dict:
        """
        Execute order on exchange demo.

        Args:
            order: Order dict with keys: symbol, side, amount, type, price

        Returns:
            Result dict with status, trade_id, entry_price, fee, balance
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # Execute through adapter
            result = await self.adapter.execute_order(order)

            # Check if result is valid
            if result is None:
                logger.error("❌ Order execution failed: adapter returned None")
                return {
                    "status": "rejected",
                    "reason": "Adapter returned None",
                    "order": order,
                }

            logger.info(
                f"✅ Order executed | "
                f"{result.get('side', '?').upper()} "
                f"{result.get('amount', 0):.4f} @ {result.get('price', 0):.2f}"
            )

            return {
                "status": "opened",
                "result": "OPENED",
                "trade_id": result.get("id", order.get("trade_id")),
                "symbol": result.get("symbol"),
                "side": result.get("side"),
                "amount": result.get("amount"),
                "entry_price": result.get("price"),
                "fee": result.get("fee", {}).get("cost", 0) if isinstance(result.get("fee"), dict) else 0,
                "balance": self.get_balance(),
            }

        except Exception as e:
            logger.error(f"❌ Order execution failed: {e}")
            return {
                "status": "rejected",
                "reason": str(e),
                "order": order,
            }

    def get_balance(self) -> float:
        """Get current balance from adapter."""
        try:
            return self.adapter.balance_manager.balance
        except Exception as e:
            logger.warning(f"⚠️ Error fetching balance: {e}")
            return 0.0

    def get_equity(self) -> float:
        """Get current equity from adapter."""
        try:
            return self.adapter.balance_manager.equity
        except Exception as e:
            logger.warning(f"⚠️ Error fetching equity: {e}")
            return 0.0

    async def get_stats(self) -> dict:
        """
        Get trading statistics from exchange.

        Returns:
            Dict with trading stats (balance, equity, positions, etc.)
        """
        try:
            # Get current balance and equity
            balance = self.get_balance()
            equity = self.get_equity()

            # Try to get closed trades from exchange
            try:
                trades = await self.adapter.connector.fetch_my_trades(self.symbol, limit=1000)
                closed_trades = len(trades) if trades else 0
            except Exception:
                closed_trades = 0

            # Try to get open positions
            try:
                positions = await self.adapter.connector.fetch_positions()
                open_positions = len([p for p in positions if abs(float(p.get("contracts", 0))) > 0])
            except Exception:
                open_positions = 0

            return {
                "initial_balance": getattr(self, "initial_balance", balance),
                "final_balance": balance,
                "final_equity": equity,
                "total_pnl": equity - getattr(self, "initial_balance", balance),
                "total_trades": closed_trades,
                "open_positions": open_positions,
            }

        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {
                "initial_balance": 0,
                "final_balance": 0,
                "final_equity": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "open_positions": 0,
            }
