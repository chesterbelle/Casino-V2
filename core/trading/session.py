"""
Trading Session - Casino V2

Unified trading session that works with any data source.
This is the main entry point for running the trading bot.
"""

import inspect
import logging
from typing import Optional

from core.data_sources.base import DataSource
from gemini.gemini_core import Gemini
from sensors.sensor_manager import SensorManager

from .context import TradingContext
from .pipeline import Pipeline
from .stages import BuildOrderStage, EvaluateStage, ExecuteStage, ProcessSignalsStage

logger = logging.getLogger(__name__)


class SessionStats:
    """Track session statistics."""

    def __init__(self):
        self.candles_processed = 0
        self.signals_detected = 0
        self.orders_executed = 0
        self.orders_rejected = 0
        self.orders_error = 0
        self.rejection_reasons = []  # List of rejection reasons
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

    def update(self, context: TradingContext) -> None:
        """Update stats from context."""
        self.candles_processed += 1

        if context.signals:
            self.signals_detected += len(context.signals)

        if context.result:
            status = context.result.get("status")
            if status == "opened":
                self.orders_executed += 1
            elif status == "rejected":
                self.orders_rejected += 1
                reason = context.result.get("reason", "unknown")
                self.rejection_reasons.append(
                    {"candle": self.candles_processed, "reason": reason, "order": context.order}
                )
            elif status == "error":
                self.orders_error += 1
                # Get detailed error message if available, otherwise use generic reason
                reason = context.result.get("error") or context.result.get("reason", "unknown")
                self.rejection_reasons.append(
                    {"candle": self.candles_processed, "reason": reason, "order": context.order}
                )

    def summary(self) -> dict:
        """Get summary statistics."""
        return {
            "candles_processed": self.candles_processed,
            "signals_detected": self.signals_detected,
            "orders_executed": self.orders_executed,
            "orders_rejected": self.orders_rejected,
            "orders_error": self.orders_error,
            "rejection_reasons": self.rejection_reasons,
            "wins": self.wins,
            "losses": self.losses,
            "total_pnl": self.total_pnl,
        }


class TradingSession:
    """
    Unified trading session.

    Works with any DataSource (backtest, testing, live).
    Uses pipeline architecture for clean, testable code.

    Example:
        >>> # Backtest
        >>> source = BacktestDataSource.from_csv("BTC_1h.csv")
        >>> session = TradingSession(source, paroli)
        >>> await session.run()
        >>>
        >>> # Testing (demo exchange)
        >>> connector = ResilientConnector(KrakenConnector(mode="demo"))
        >>> source = TestingDataSource(connector, "BTC/USD", "5m")
        >>> session = TradingSession(source, paroli)
        >>> await session.run()
        >>>
        >>> # Live (real money)
        >>> connector = ResilientConnector(KrakenConnector(mode="live"))
        >>> source = LiveDataSource(connector, "BTC/USD", "5m")
        >>> session = TradingSession(source, paroli)
        >>> await session.run()
    """

    def __init__(
        self,
        data_source: DataSource,
        player_module,
        max_candles: Optional[int] = None,
    ):
        """
        Initialize trading session.

        Args:
            data_source: Data source (backtest, testing, or live)
            player_module: Player module (e.g., paroli, martingale)
            max_candles: Maximum candles to process (None = unlimited)
        """
        self.data_source = data_source
        self.player = player_module
        self.max_candles = max_candles

        # Initialize player state (for progression tracking)
        self.player_state = player_module.init_state() if hasattr(player_module, "init_state") else {}

        # Track last processed trades to avoid duplicates
        self.processed_trade_ids = set()

        # Initialize components
        self.sensor_manager = SensorManager()
        self.gemini = Gemini()

        # Create pipeline
        self.pipeline = Pipeline(
            [
                ProcessSignalsStage(self.sensor_manager),
                EvaluateStage(self.gemini),
                BuildOrderStage(player_module),
                ExecuteStage(data_source),
            ]
        )

        # Stats
        self.stats = SessionStats()

        logger.info(
            f"🎰 TradingSession initialized | "
            f"Player: {player_module.__name__ if hasattr(player_module, '__name__') else 'unknown'} | "
            f"Max candles: {max_candles or 'unlimited'} | "
            f"Initial state: {self.player_state}"
        )

    async def run(self) -> dict:
        """
        Run trading session.

        Processes candles through the pipeline until:
        - No more candles available
        - Max candles reached
        - Error occurs

        Returns:
            Session statistics
        """
        logger.info("🚀 Starting trading session")

        try:
            # Connect to data source
            await self.data_source.connect()

            # Main loop
            while True:
                # Check max candles limit
                if self.max_candles and self.stats.candles_processed >= self.max_candles:
                    logger.info(f"🏁 Max candles reached: {self.max_candles}")
                    break

                # STEP 1: Check for closed positions (TP/SL triggered by exchange)
                await self._check_and_process_closed_trades()

                # STEP 2: Prepare player state for this iteration
                current_equity = self.data_source.get_equity()
                self.player_state, player_meta = self._prepare_player_state(current_equity)

                # Get next candle
                candle = await self.data_source.next_candle()

                if not candle:
                    logger.info("🏁 No more candles available")
                    break

                # Create context with player metadata
                context = TradingContext(
                    candle=candle,
                    equity=current_equity,
                    balance=self.data_source.get_balance(),
                    metadata=player_meta,
                )

                # Process through pipeline
                result_context = await self.pipeline.process(context)

                # Update stats
                self.stats.update(result_context)

                # Log progress
                if self.stats.candles_processed % 10 == 0:
                    logger.info(
                        f"📊 Progress | "
                        f"Candles: {self.stats.candles_processed} | "
                        f"Signals: {self.stats.signals_detected} | "
                        f"Orders: {self.stats.orders_executed} | "
                        f"Equity: {current_equity:.2f} | "
                        f"Player step: {self.player_state.get('step', 0)}"
                    )

        except KeyboardInterrupt:
            logger.info("⚠️ Session interrupted by user")

        except Exception as e:
            logger.error(f"❌ Session error: {e}", exc_info=True)

        finally:
            # Disconnect from data source
            await self.data_source.disconnect()

            # Final stats
            final_stats = self.stats.summary()
            logger.info(
                f"🏁 Session completed | "
                f"Candles: {final_stats['candles_processed']} | "
                f"Signals: {final_stats['signals_detected']} | "
                f"Orders: {final_stats['orders_executed']}"
            )

            # Get data source stats (if available)
            if hasattr(self.data_source, "get_stats"):
                ds_stats = self.data_source.get_stats()
                # Check if it's a coroutine (async method)
                if inspect.iscoroutine(ds_stats):
                    ds_stats = await ds_stats
                logger.info(
                    f"💰 Final balance: {ds_stats.get('final_balance', 0):.2f} | "
                    f"PnL: {ds_stats.get('net_pnl', 0):+.2f} | "
                    f"Win rate: {ds_stats.get('win_rate', 0):.2%}"
                )

        return self.stats.summary()

    def _prepare_player_state(self, equity: float) -> tuple:
        """
        Prepare player state for current iteration.

        Calls player's prepare_state() to ensure unit is calculated
        and returns metadata for BuildOrderStage.

        Args:
            equity: Current equity

        Returns:
            (updated_state, metadata)
        """
        if hasattr(self.player, "prepare_state"):
            return self.player.prepare_state(self.player_state, equity)
        return self.player_state, {}

    async def _check_and_process_closed_trades(self) -> None:
        """
        Check for closed positions and update player state.

        This method:
        1. Fetches recent trades from exchange
        2. Identifies closed positions (TP/SL triggered)
        3. Calculates WIN/LOSS based on PnL
        4. Updates player state (advances Paroli progression)
        """
        # Only check for testing/live modes (backtest handles this internally)
        if not hasattr(self.data_source, "adapter"):
            return

        try:
            # Get adapter from data source
            adapter = self.data_source.adapter

            # Fetch recent trades (last 100 to catch all closes)
            if not hasattr(adapter.connector, "fetch_my_trades"):
                return

            recent_trades = await adapter.connector.fetch_my_trades(symbol=adapter.symbol, limit=100)

            if not recent_trades:
                return

            # Process each trade
            for trade in recent_trades:
                trade_id = trade.get("id")

                # Skip if already processed
                if trade_id in self.processed_trade_ids:
                    continue

                # Mark as processed
                self.processed_trade_ids.add(trade_id)

                # NOTE: Trade normalization and close detection is now handled by
                # the exchange connector and ExchangeStateSync. The ccxt_adapter
                # automatically calls position_tracker.confirm_close() when it
                # detects a fill with is_close=True from the connector.
                #
                # This method is kept for backward compatibility but may be
                # deprecated in the future as the new architecture handles
                # position closes automatically.

        except Exception as e:
            logger.warning(f"⚠️ Error checking closed trades: {e}")
