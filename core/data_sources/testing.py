"""
Testing Data Source - Casino V2

Provides real-time data from an exchange for demo/live trading.
Delegates all order execution and state management to the Croupier.
"""

import asyncio
import logging
from typing import Dict, Optional

from croupier.croupier import Croupier

from .base import Candle, DataSource

logger = logging.getLogger(__name__)


class TestingDataSource(DataSource):
    """
    Data source for demo trading with real market prices.
    This class is a thin wrapper that provides candle data and delegates
    all execution logic to the Croupier.
    """

    def __init__(
        self,
        croupier: Croupier,
        symbol: str,
        timeframe: str,
        poll_interval: float = 5.0,
    ):
        """
        Initializes the TestingDataSource.

        Args:
            croupier: The Croupier instance, which manages state and execution.
            symbol: Trading symbol (e.g., "BTC/USD").
            timeframe: Candle interval (e.g., "5m", "1h").
            poll_interval: Seconds to wait between candle polls.
        """
        self.croupier = croupier
        # The adapter and connector are accessed through the Croupier
        self.adapter = croupier.exchange
        self.connector = self.adapter.connector

        self.symbol = symbol
        self.timeframe = timeframe
        self.poll_interval = poll_interval

        self._connected = False
        self._last_candle_timestamp = 0
        self.initial_balance = 0.0  # Will be set on connect

        logger.info(
            f"📊 TestingDataSource initialized | "
            f"Symbol: {symbol} | "
            f"Timeframe: {timeframe} | "
            f"Poll: {poll_interval}s"
        )

    async def connect(self) -> None:
        """Connects to the exchange via the adapter held by the Croupier."""
        if self._connected:
            return
        try:
            await self.adapter.connect()
            self._connected = True
            # Save initial balance for stats, obtained from the Croupier
            self.initial_balance = self.croupier.get_balance()
            logger.info("✅ Testing data source connected")
        except Exception as e:
            logger.error(f"❌ Failed to connect testing data source: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnects from the exchange via the adapter."""
        if not self._connected:
            return
        try:
            # The Croupier will be responsible for any final state checks or cleanup.
            await self.adapter.close()
            self._connected = False
            logger.info("🔌 Testing data source disconnected")
        except Exception as e:
            logger.warning(f"⚠️ Error disconnecting testing data source: {e}")

    async def next_candle(self) -> Optional[Candle]:
        """
        Gets the next candle from the exchange and enriches it with portfolio data from the Croupier.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        while True:
            try:
                candle_data = await self.adapter.next_candle()
                if not candle_data:
                    logger.warning("⚠️ No candles received, retrying...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                timestamp = int(candle_data["timestamp"])
                if timestamp <= self._last_candle_timestamp:
                    logger.debug(f"⏳ Same candle (ts={timestamp}), waiting for new one...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                self._last_candle_timestamp = timestamp
                logger.info(f"✅ New candle received | ts={timestamp}")

                # The Croupier is now responsible for checking for closed positions.
                # We just get the latest state from it.
                balance = self.croupier.get_balance()
                equity = self.croupier.get_equity()

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
                return None

    async def execute_order(self, order: Dict) -> Dict:
        """
        Delegates order execution directly to the Croupier.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # Croupier is the single point of execution
            result = await self.croupier.execute_order(order)
            return result
        except Exception as e:
            logger.error(f"❌ Order execution failed at DataSource level: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "order": order,
            }

    def get_balance(self) -> float:
        """Gets current balance from the Croupier."""
        return self.croupier.get_balance()

    def get_equity(self) -> float:
        """Gets current equity from the Croupier."""
        return self.croupier.get_equity()

    async def get_stats(self) -> dict:
        """
        Gets trading statistics directly from the Croupier.
        """
        try:
            # The Croupier is the single source of truth for portfolio state.
            stats = self.croupier.get_portfolio_state()
            stats["initial_balance"] = self.initial_balance
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting stats from Croupier: {e}")
            return {
                "initial_balance": self.initial_balance,
                "final_balance": 0,
                "final_equity": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "open_positions": 0,
            }
