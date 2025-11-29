"""
Trading Session - Casino V2

Unified trading session that works with any data source.
This is the main entry point for running the trading bot.
"""

import inspect
import logging
from typing import Optional

from core.data_sources.base import DataSource
# from gemini.gemini_core import Gemini  # V2 Legacy - Not used in V3
# from sensors.sensor_manager import SensorManager  # V2 Legacy - Not used in V3

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
        self.bets = 0
        self.ghosts = 0
        self.skips = 0

    def update(self, context: TradingContext) -> None:
        """Update stats from context."""
        self.candles_processed += 1

        # Count decision actions when available
        try:
            verdict = getattr(context, "verdict", None)
            if verdict:
                action = verdict.get("action")
                if action == "BET":
                    self.bets += 1
                elif action == "GHOST":
                    self.ghosts += 1
                elif action == "SKIP":
                    self.skips += 1
        except Exception:
            pass

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
            "bets": self.bets,
            "ghosts": self.ghosts,
            "skips": self.skips,
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
        self.player = player_module
        self.gemini = Gemini()

        # Pass Gemini instance to data source if it supports it
        if hasattr(data_source, "set_gemini_instance"):
            data_source.set_gemini_instance(self.gemini)

        self.data_source = data_source
        self.max_candles = max_candles

        # Initialize player state (for progression tracking)
        self.player_state = player_module.init_state() if hasattr(player_module, "init_state") else {}

        # Track last processed trades to avoid duplicates
        self.processed_trade_ids = set()

        # Initialize components
        self.sensor_manager = SensorManager()

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
                # STEP 0: Limpiar posiciones huérfanas ANTES de cualquier otra cosa
                if hasattr(self.data_source, "croupier") and hasattr(
                    self.data_source.croupier, "cleanup_orphaned_positions"
                ):
                    try:
                        await self.data_source.croupier.cleanup_orphaned_positions(self.data_source.symbol)
                    except Exception as cleanup_error:
                        logger.error(f"❌ Error during proactive cleanup: {cleanup_error}")
                # Check max candles limit
                if self.max_candles and self.stats.candles_processed >= self.max_candles:
                    logger.info(f"🏁 Max candles reached: {self.max_candles}")
                    break

                # STEP 1: Monitorear posiciones abiertas y gestionar OCO
                if hasattr(self.data_source, "croupier") and hasattr(self.data_source.croupier, "monitor_positions"):
                    closed_positions = await self.data_source.croupier.monitor_positions()

                    # Update player state based on closed positions (CRITICAL for Paroli progression)
                    if closed_positions and hasattr(self.player, "handle_trade_outcome"):
                        for result in closed_positions:
                            self.player_state = self.player.handle_trade_outcome(self.player_state, "BET", result)
                            logger.info(f"🎲 Player state updated: {self.player_state}")

                # STEP 2: Prepare player state for this iteration
                current_equity = self.data_source.get_equity()
                self.player_state, player_meta = self._prepare_player_state(current_equity)

                # Get next candle
                candle = await self.data_source.next_candle()

                if not candle:
                    logger.info("🏁 No more candles available")
                    break

                # STEP 3: Check for closed positions (critical for position tracking)
                if hasattr(self.data_source, "croupier") and hasattr(self.data_source.croupier, "position_tracker"):
                    # Convert candle to dict format expected by position tracker
                    candle_dict = {
                        "timestamp": candle.timestamp,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                        "symbol": candle.symbol,
                        "timeframe": candle.timeframe,
                    }
                    closed_positions = self.data_source.croupier.position_tracker.check_and_close_positions(candle_dict)
                    if closed_positions:
                        logger.info(f"📊 Position check results: {len(closed_positions)} positions processed")

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

    def get_stats(self) -> SessionStats:
        """Return live SessionStats object (used by validator)."""
        return self.stats

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
