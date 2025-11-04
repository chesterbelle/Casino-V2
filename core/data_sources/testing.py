"""
Testing Data Source - Casino V2

Provides real-time data from exchange demo/testnet.
"""

import asyncio
import logging
from typing import Dict, Optional

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
    ):
        """
        Initialize testing data source.

        Args:
            connector: Exchange connector (should be ResilientConnector)
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Candle interval (e.g., "5m", "1h")
            poll_interval: Seconds to wait between candle checks
        """
        self.connector = connector
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
            # Connect connector
            if hasattr(self.connector, "connect"):
                await self.connector.connect()

            # Wait for connector to be ready
            if hasattr(self.connector, "ready"):
                timeout = 30
                elapsed = 0
                while not self.connector.ready and elapsed < timeout:
                    await asyncio.sleep(1)
                    elapsed += 1

                if not self.connector.ready:
                    raise RuntimeError("Connector not ready after 30s")

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
            if hasattr(self.connector, "close"):
                await self.connector.close()

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
                # Fetch latest candle
                candles = await self.connector.fetch_ohlcv(self.symbol, self.timeframe, limit=1)

                if not candles:
                    logger.warning("⚠️ No candles received, retrying...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                candle_data = candles[0]
                timestamp = int(candle_data["timestamp"])

                # Check if it's a new candle
                if timestamp <= self._last_candle_timestamp:
                    # Same candle, wait for next
                    await asyncio.sleep(self.poll_interval)
                    continue

                # New candle!
                self._last_candle_timestamp = timestamp

                # Get enriched state
                equity = self.get_equity()
                balance = self.get_balance()
                unrealized_pnl = equity - balance

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
                    unrealized_pnl=unrealized_pnl,
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
            # Execute through connector
            result = await self.connector.create_order(
                symbol=order.get("symbol", self.symbol),
                side=order["side"],
                amount=order["amount"],
                order_type=order.get("type", "market"),
                price=order.get("price"),
            )

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
        """Get current balance from exchange demo."""
        try:
            # This is a simplified version
            # In reality, you'd fetch balance from connector
            if hasattr(self.connector, "fetch_balance"):
                # Sync call (wrap in asyncio if needed)
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't use asyncio.run in running loop
                    # Return cached value or 0
                    return 0.0
                else:
                    balance_data = asyncio.run(self.connector.fetch_balance())
                    return float(balance_data.get("free", {}).get("USD", 0))

            return 0.0

        except Exception as e:
            logger.warning(f"⚠️ Error fetching balance: {e}")
            return 0.0

    def get_equity(self) -> float:
        """Get current equity from exchange demo."""
        try:
            # Equity = balance + unrealized PnL
            balance = self.get_balance()

            # Get unrealized PnL from open positions
            if hasattr(self.connector, "fetch_positions"):
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return balance
                else:
                    positions = asyncio.run(self.connector.fetch_positions())
                    unrealized_pnl = sum(float(pos.get("unrealizedPnl", 0)) for pos in positions)
                    return balance + unrealized_pnl

            return balance

        except Exception as e:
            logger.warning(f"⚠️ Error fetching equity: {e}")
            return 0.0
