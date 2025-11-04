"""
Testing Data Source - Casino V2

Provides real-time data from exchange demo/testnet.
Uses CCXTAdapter internally for balance/position management.
"""

import asyncio
import logging
from typing import Dict, Optional

from tables.ccxt_adapter import CCXTAdapter

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
            logger.info("✅ Testing data source connected")

        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from exchange demo."""
        if not self._connected:
            return

        try:
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
                # Fetch latest candle through adapter
                candle_data = await self.adapter.next_candle()

                if not candle_data:
                    logger.warning("⚠️ No candle received, retrying...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                # Extract timestamp
                timestamp = int(candle_data["timestamp"])

                # Check if it's a new candle
                if timestamp <= self._last_candle_timestamp:
                    # Same candle, wait for next
                    await asyncio.sleep(self.poll_interval)
                    continue

                # New candle!
                self._last_candle_timestamp = timestamp

                # Adapter already enriches with equity/balance
                return Candle(
                    timestamp=timestamp,
                    open=float(candle_data["open"]),
                    high=float(candle_data["high"]),
                    low=float(candle_data["low"]),
                    close=float(candle_data["close"]),
                    volume=float(candle_data["volume"]),
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    equity=float(candle_data.get("equity", 0)),
                    balance=float(candle_data.get("balance", 0)),
                    unrealized_pnl=float(candle_data.get("unrealized_pnl", 0)),
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
                "fee": result.get("fee", {}).get("cost", 0),
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
