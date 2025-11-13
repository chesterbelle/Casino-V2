"""
Testing Data Source - Casino V2

Provides real-time data from exchange demo trading (Bybit Demo Trading).
Uses Croupier for order execution and portfolio management.

Note: Despite the name "TestingDataSource", this now connects to Demo Trading
which uses REAL market prices (not testnet fake prices).
"""

import asyncio
import logging
from typing import Dict, Optional

from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter

from .base import Candle, DataSource

logger = logging.getLogger(__name__)


class TestingDataSource(DataSource):
    """
    Data source for demo trading with real market prices.

    Features:
    - Real-time candles with REAL market prices (from mainnet)
    - Simulated order execution (no real money)
    - Real slippage and fees simulation
    - Resilient connection (auto-reconnect)

    Example:
        >>> connector = ResilientConnector(BybitConnector(mode="demo"))
        >>> source = TestingDataSource(connector, "BTC/USDT:USDT", "1m")
        >>> await source.connect()
        >>> candle = await source.next_candle()
    """

    def __init__(
        self,
        connector,
        symbol: str,
        timeframe: str,
        poll_interval: float = 5.0,
        starting_balance: float = None,  # DEPRECATED - will be ignored
    ):
        """
        Initialize testing data source.

        Args:
            connector: Exchange connector (should be ResilientConnector)
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Candle interval (e.g., "5m", "1h")
            poll_interval: Seconds to wait between candle checks
            starting_balance: DEPRECATED - TestingDataSource always uses exchange's real balance
        """
        # SAFETY: TestingDataSource NEVER uses custom starting_balance
        if starting_balance is not None:
            logger.warning(f"⚠️ starting_balance={starting_balance} IGNORED in TestingDataSource")
            logger.warning("   TestingDataSource ALWAYS uses exchange's real balance for safety")

        # Create CCXTAdapter for exchange communication (no starting_balance = uses exchange balance)
        self.adapter = CCXTAdapter(
            connector=connector,
            symbol=symbol,
            timeframe=timeframe,
            # starting_balance=None means use exchange's real balance
        )

        # Create Croupier for order execution and portfolio management (no initial_balance = uses exchange balance)
        self.croupier = Croupier(exchange_adapter=self.adapter)  # No initial_balance = uses exchange balance

        self.symbol = symbol
        self.timeframe = timeframe
        self.poll_interval = poll_interval

        self._connected = False
        self._last_candle_timestamp = 0

        # Track open positions to detect closures
        self._tracked_positions = {}  # {symbol: {side, amount, entry_price, timestamp}}

        logger.info(
            f"📊 TestingDataSource initialized | "
            f"Symbol: {symbol} | "
            f"Timeframe: {timeframe} | "
            f"Poll: {poll_interval}s | "
            f"Using Croupier for order execution"
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

            # Final check for any missed position closures
            await self._final_position_check()

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

                # Extract timestamp (CCXT format: [timestamp, open, high, low, close, volume])
                timestamp = int(candle_data[0])
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

                # Check for closed positions (TP/SL executed)
                await self._check_closed_positions()

                # Get balance/equity from adapter
                balance = self.adapter.balance_manager.balance
                equity = self.adapter.balance_manager.equity

                # CCXT format: [timestamp, open, high, low, close, volume]
                return Candle(
                    timestamp=timestamp,
                    open=float(candle_data[1]),
                    high=float(candle_data[2]),
                    low=float(candle_data[3]),
                    close=float(candle_data[4]),
                    volume=float(candle_data[5]),
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
        Execute order on exchange demo through Croupier.

        Args:
            order: Order dict with keys: symbol, side, size, take_profit, stop_loss

        Returns:
            Result dict with status, trade_id, entry_price, fee, balance
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # Execute through Croupier (async call)
            # Croupier will validate, execute via adapter, and update portfolio
            result = await self.croupier.execute_order(order)

            # Check if result is valid
            if result is None:
                logger.error("❌ Order execution failed: croupier returned None")
                return {
                    "status": "rejected",
                    "reason": "Croupier returned None",
                    "order": order,
                }

            # Log execution
            status = result.get("status", "unknown")
            if status == "opened":
                logger.info(
                    f"✅ Order executed | "
                    f"{result.get('side', '?').upper()} "
                    f"{result.get('amount', 0):.4f} @ {result.get('entry_price', 0):.2f}"
                )

                # Track this position for closure detection
                # CRITICAL: Use connector's normalized symbol, not the original order symbol
                # This ensures consistency with fetch_positions() results
                symbol = self.adapter.connector.normalize_symbol(self.adapter.symbol)
                position_info = {
                    "side": result.get("side"),
                    "amount": result.get("amount"),
                    "entry_price": result.get("entry_price"),
                    "timestamp": result.get("timestamp", self._last_candle_timestamp),
                }
                self._tracked_positions[symbol] = position_info
                logger.info(
                    f"📍 POSITION TRACKING STARTED: {symbol} | {position_info['side'].upper()} {position_info['amount']:.4f} @ ${position_info['entry_price']:.2f}"
                )
                logger.debug(f"📍 Normalized symbol: '{symbol}' (original: '{self.adapter.symbol}')")

            elif status == "rejected":
                logger.warning(f"⚠️ Order rejected: {result.get('reason', 'unknown')}")
            elif status == "error":
                logger.error(f"❌ Order error: {result.get('reason', 'unknown')}")

            return result

        except Exception as e:
            logger.error(f"❌ Order execution failed: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "order": order,
            }

    def get_balance(self) -> float:
        """Get current balance from Croupier."""
        try:
            return self.croupier.get_balance()
        except Exception as e:
            logger.warning(f"⚠️ Error fetching balance: {e}")
            return 0.0

    def get_equity(self) -> float:
        """Get current equity from Croupier."""
        try:
            return self.croupier.get_equity()
        except Exception as e:
            logger.warning(f"⚠️ Error fetching equity: {e}")
            return 0.0

    async def get_stats(self) -> dict:
        """
        Get trading statistics from exchange.

        CRITICAL: This method MUST sync with exchange to get REAL balance,
        not internal balance which may be desynchronized.

        Returns:
            Dict with trading stats (balance, equity, positions, etc.)
        """
        try:
            # CRITICAL: Sync with exchange to get REAL balance
            # Do NOT use self.get_balance() which reads internal balance_manager
            try:
                equity_snapshot = await self.adapter.state_sync.sync_equity()
                balance = equity_snapshot.balance
                equity = equity_snapshot.equity
                logger.info(f"✅ Stats synced with exchange | Balance: ${balance:,.2f} | Equity: ${equity:,.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to sync with exchange, using internal balance: {e}")
                balance = self.get_balance()
                equity = self.get_equity()

            # Get closed trades count from position tracker
            # NOTE: Do NOT use fetch_my_trades() as it returns ALL historical trades
            # from the exchange, not just from this session
            try:
                tracker_stats = self.adapter.position_tracker.get_stats()
                closed_trades = tracker_stats.get("total_closed", 0)
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

    async def _check_closed_positions(self) -> None:
        """
        Check if any tracked positions have been closed (TP/SL executed).

        This method compares tracked positions with actual exchange positions
        to detect when Binance closes a position via TP/SL (OCO behavior).
        """
        if not self._tracked_positions:
            logger.debug("🔍 No tracked positions to check")
            return

        try:
            # Log current tracking state
            logger.debug(
                f"🔍 Checking {len(self._tracked_positions)} tracked positions: {list(self._tracked_positions.keys())}"
            )

            # Fetch current positions from exchange
            current_positions = await self.adapter.connector.fetch_positions()
            current_symbols = {p["symbol"] for p in current_positions if abs(float(p.get("contracts", 0))) > 0}

            logger.debug(f"🔍 Current open positions on exchange: {current_symbols}")

            # Check which tracked positions are no longer open
            closed_symbols = []
            for symbol in list(self._tracked_positions.keys()):
                logger.debug(f"🔍 Checking tracked position: {symbol}")

                if symbol not in current_symbols:
                    # Position was closed!
                    pos_info = self._tracked_positions[symbol]
                    closed_symbols.append(symbol)
                    logger.info(f"🎯 POSITION CLOSURE DETECTED: {symbol} no longer in exchange positions")

                    # Get current price to calculate PnL and register the closure
                    try:
                        # Use the last known close price as the exit price
                        current_price = self.adapter.get_current_price(symbol)
                        if not current_price:
                            # Fallback to fetching OHLCV if ticker fails
                            candles = await self.adapter.connector.fetch_ohlcv(symbol, self.timeframe, limit=1)
                            if candles:
                                current_price = candles[0][4]  # Close price

                        if not current_price:
                            logger.error(f"❌ Could not determine exit price for {symbol}")
                            continue  # Skip this closed position

                        # Calculate PnL
                        entry_price = pos_info["entry_price"]
                        amount = pos_info["amount"]
                        side = pos_info["side"]

                        if side == "long":
                            pnl = (current_price - entry_price) * amount
                        else:  # short
                            pnl = (entry_price - current_price) * amount

                        logger.info(
                            f"🎯 Position closure processed | "
                            f"{symbol} {side.upper()} {amount:.4f} | "
                            f"Entry: ${entry_price:.2f} | Exit: ${current_price:.2f} | "
                            f"PnL: ${pnl:+.2f}"
                        )

                        # Notify position tracker about the closure
                        self.adapter.position_tracker.confirm_close(
                            symbol=symbol, realized_pnl=pnl, close_reason="TP_SL_EXECUTED"
                        )
                        logger.info(f"✅ Closure for {symbol} registered in PositionTracker.")

                    except Exception as e:
                        logger.error(f"❌ Error processing closed position {symbol}: {e}")
                else:
                    logger.debug(f"🔍 Position {symbol} still open on exchange")

            # Remove closed positions from tracking
            for symbol in closed_symbols:
                del self._tracked_positions[symbol]

        except Exception as e:
            logger.error(f"❌ Error checking closed positions: {e}")

    async def _final_position_check(self) -> None:
        """
        Final check for any positions that were closed but not detected.
        Called during disconnect to ensure no trades are missed.
        """
        if not self._tracked_positions:
            logger.debug("🔍 No tracked positions for final check")
            return

        logger.info(f"🔍 FINAL POSITION CHECK: {len(self._tracked_positions)} positions still tracked")

        try:
            # Fetch current positions from exchange
            current_positions = await self.adapter.connector.fetch_positions()
            current_symbols = {p["symbol"] for p in current_positions if abs(float(p.get("contracts", 0))) > 0}

            logger.info(f"🔍 Final exchange positions: {current_symbols}")

            # Check for any tracked positions that are no longer open
            for symbol, pos_info in list(self._tracked_positions.items()):
                if symbol not in current_symbols:
                    logger.warning(f"⚠️ MISSED CLOSURE: Position {symbol} was closed but not detected during session")
                    logger.info(
                        f"🎯 Registering missed closure: {symbol} {pos_info['side'].upper()} {pos_info['amount']:.4f}"
                    )

                    try:
                        # Get current price to calculate PnL
                        current_price = await self.adapter.get_current_price(symbol)

                        # Calculate PnL
                        entry_price = pos_info["entry_price"]
                        amount = pos_info["amount"]
                        side = pos_info["side"]

                        if side == "long":
                            pnl = (current_price - entry_price) * amount
                        else:  # short
                            pnl = (entry_price - current_price) * amount

                        logger.info(
                            f"🎯 Missed closure PnL: Entry ${entry_price:.2f} → Exit ${current_price:.2f} = ${pnl:+.2f}"
                        )

                        # Register the missed closure
                        try:
                            self.adapter.position_tracker.confirm_close(
                                symbol=symbol, realized_pnl=pnl, close_reason="MISSED_CLOSURE_DETECTED"
                            )
                            logger.info("✅ Missed closure registered successfully")
                        except Exception as e:
                            logger.error(f"❌ Failed to register missed closure: {e}")

                    except Exception as e:
                        logger.error(f"❌ Error processing missed closure for {symbol}: {e}")
                else:
                    logger.warning(f"⚠️ Position {symbol} still open at session end - may need manual cleanup")

        except Exception as e:
            logger.error(f"❌ Error in final position check: {e}")
