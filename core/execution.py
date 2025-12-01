"""
Execution Layer for Casino-V3.
Handles DecisionEvents from Paroli and executes orders via Croupier.
"""

import logging
import time

import config.trading
from core.events import EventType
from croupier.croupier import Croupier

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Executes trading decisions from Paroli.
    Subscribes to DECISION events (from Paroli).
    """

    def __init__(self, engine, croupier: Croupier, paroli=None, tracker=None):
        self.engine = engine
        self.croupier = croupier
        self.paroli = paroli
        self.tracker = tracker  # SensorTracker instance
        self.active = False
        self.pending_trades = {}  # trade_id -> (decision, sensor_id)
        self.processed_decisions = set()  # Track processed decision IDs to prevent duplicates
        self.candle_count = 0  # Counter for periodic reconciliation
        self.reconciliation_interval = 10  # Run reconciliation every N candles

        # Subscribe to DECISION events (will come from Paroli)
        self.engine.subscribe(EventType.SYSTEM, self.on_decision)  # Using SYSTEM for now

        # Subscribe to CANDLE events to check for TP/SL exits
        self.engine.subscribe(EventType.CANDLE, self.on_candle)

    async def start(self):
        """Start the Order Manager."""
        self.active = True
        logger.info("🚀 OrderManager started")

    async def stop(self):
        """Stop the Order Manager."""
        self.active = False
        logger.info("🛑 OrderManager stopped")

    async def on_decision(self, event):
        """Handle trading decision from Paroli."""
        if not self.active:
            return

        # Check if this is a DecisionEvent (has bet_size attribute)
        if not hasattr(event, "bet_size"):
            return

        if event.side == "SKIP":
            logger.info("⏭️ Decision: SKIP - no trade")
            return

        logger.info(
            f"📩 Decision Received: {event.symbol} {event.side} "
            f"(Size: {event.bet_size:.2%}, Step: {event.paroli_step})"
        )
        
        # Check for duplicate decision processing
        decision_id = getattr(event, "decision_id", None)
        if decision_id:
            if decision_id in self.processed_decisions:
                logger.warning(f"⚠️ DUPLICATE DECISION DETECTED: {decision_id} - SKIPPING")
                return
            self.processed_decisions.add(decision_id)
            logger.debug(f"📥 Processing DecisionEvent {decision_id}")

        # Construct Order Payload
        trade_id = f"V3_{int(time.time()*1000)}"

        # Calculate multipliers from config or event
        tp_pct = getattr(event, "tp_pct", None) or config.trading.TAKE_PROFIT
        sl_pct = getattr(event, "sl_pct", None) or config.trading.STOP_LOSS

        order_payload = {
            "trade_id": trade_id,
            "symbol": event.symbol,
            "side": event.side,
            "size": event.bet_size,  # Fraction of equity
            "take_profit": tp_pct,  # Pass as percentage (e.g. 0.01)
            "stop_loss": sl_pct,  # Pass as percentage (e.g. 0.01)
            "timestamp": str(event.timestamp),
            "ghost": False,
        }

        # Store for outcome tracking (include sensor_id if available)
        sensor_id = getattr(event, "selected_sensor", "Unknown")
        self.pending_trades[trade_id] = (event, sensor_id)

        # Execute via Croupier
        try:
            result = await self.croupier.execute_order(order_payload)

            if result.get("status") == "filled":
                logger.info(f"✅ Order Executed: {result.get('id')}")
                # TODO: Track order to get outcome and update Paroli
            else:
                logger.warning(f"⚠️ Order Result: {result}")

        except Exception as e:
            logger.error(f"❌ Execution Failed: {e}", exc_info=True)

    def handle_trade_outcome(self, trade_id: str, won: bool, pnl: float = 0.0):
        """
        Callback when trade closes - update Paroli and SensorTracker.

        Args:
            trade_id: Trade identifier
            won: True if trade was profitable
            pnl: Profit/Loss amount
        """
        if trade_id in self.pending_trades:
            event, sensor_id = self.pending_trades[trade_id]

            # Update Paroli
            if self.paroli:
                self.paroli.handle_trade_outcome(trade_id, won)

            # Update SensorTracker
            if self.tracker and sensor_id != "Unknown":
                self.tracker.update_sensor(sensor_id, pnl, won)
                logger.debug(f"📊 Updated tracker for {sensor_id}: won={won}, pnl={pnl:.4f}")

            # Clean up
            del self.pending_trades[trade_id]

    async def on_candle(self, event):
        """Handle new candle to check for position exits."""
        if not self.active:
            return

        # Increment candle counter and run periodic reconciliation
        self.candle_count += 1
        if self.candle_count >= self.reconciliation_interval:
            self.candle_count = 0
            logger.info(f"🔄 Running periodic reconciliation (every {self.reconciliation_interval} candles)")
            try:
                await self.croupier.reconcile_positions(event.symbol)
            except Exception as e:
                logger.error(f"❌ Error during reconciliation: {e}", exc_info=True)

        # Convert event to dict for Croupier
        candle_dict = {
            "timestamp": event.timestamp,
            "open": event.open,
            "high": event.high,
            "low": event.low,
            "close": event.close,
            "volume": event.volume,
            "market": event.symbol,
            "timeframe": "1m",  # Assuming 1m for now
        }

        # Check for potential exits (TP/SL touched)
        potential_exits = self.croupier.position_tracker.check_and_close_positions(candle_dict)

        # Determine execution mode
        mode = "testing"
        try:
            if hasattr(self.croupier.exchange_adapter, "connector"):
                mode = getattr(self.croupier.exchange_adapter.connector, "mode", "testing")
        except Exception:
            pass

        for exit_info in potential_exits:
            trade_id = exit_info["trade_id"]
            exit_reason = exit_info["exit_reason_detected"]
            exit_price = exit_info["exit_price_detected"]

            # LIVE / DEMO MODE HANDLING
            if mode in ["live", "demo"]:
                # Case 1: Internal Exits (TIME_EXIT, MANUAL, etc.)
                # These are NOT handled by the exchange automatically, so we MUST execute them.
                if exit_reason in ["TIME_EXIT", "MANUAL_SYNC", "FORCE_CLOSE"]:
                    logger.info(f"⏳ Executing {exit_reason} for {trade_id} in {mode} mode")
                    try:
                        # close_position will:
                        # 1. Cancel TP/SL orders
                        # 2. Execute Market Close (ReduceOnly)
                        # 3. Confirm close in tracker
                        await self.croupier.close_position(trade_id)
                        
                        # Update Paroli/Tracker is handled by the callback registered in main.py
                        # But we might want to log here
                        logger.info(f"✅ {exit_reason} executed successfully for {trade_id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to execute {exit_reason} for {trade_id}: {e}")

                # Case 2: Exchange Exits (TP, SL, LIQUIDATION)
                # These ARE handled by the exchange (Limit/Stop orders).
                # We should NOT simulate them here. We wait for WebSocket confirmation.
                elif exit_reason in ["TP", "SL", "LIQUIDATION"]:
                    logger.debug(f"⏭️ Skipping {exit_reason} detection in {mode} mode - waiting for WebSocket")
                    continue

            # TESTING / BACKTEST MODE HANDLING
            else:
                # In Backtest, we trust the candle data and confirm immediately
                
                # Calculate PnL
                position = self.croupier.position_tracker.get_position(trade_id)
                if not position:
                    continue

                if position.side == "LONG":
                    pnl_pct = (exit_price - position.entry_price) / position.entry_price
                else:
                    pnl_pct = (position.entry_price - exit_price) / position.entry_price

                pnl = position.notional * pnl_pct
                
                # Calculate fee (0.06% taker fee on notional)
                fee = position.notional * 0.0006

                # Confirm close
                result = self.croupier.position_tracker.confirm_close(
                    trade_id=trade_id,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    pnl=pnl,
                    fee=fee,
                )

                if result:
                    logger.info(f"✅ Trade Closed (Simulated): {trade_id} | {exit_reason} | PnL: {pnl:.2f}")
                    # Update Paroli and Tracker
                    won = result["result"] == "WIN"
                    self.handle_trade_outcome(trade_id, won, pnl)
