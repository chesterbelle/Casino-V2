"""
Fixed Player Strategy
=====================

A simple player that bets a fixed percentage of equity on every signal.
Used as a baseline to compare against progression strategies like Paroli.
"""

import logging
import time

from core.events import Event, EventType
from decision.aggregator import AggregatedSignalEvent

logger = logging.getLogger(__name__)


class DecisionEvent(Event):
    """Decision event with bet sizing."""

    def __init__(
        self,
        symbol: str,
        side: str,
        bet_size: float,
        tp_pct: float = None,
        sl_pct: float = None,
        selected_sensor: str = None,
    ):
        super().__init__(type=EventType.SYSTEM, timestamp=time.time())
        self.symbol = symbol
        self.side = side
        self.bet_size = bet_size
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.selected_sensor = selected_sensor
        # Compatibility fields for logging/Paroli
        self.paroli_step = 0
        self.unit_size = 0.0


class FixedPlayer:
    """
    Player that bets a fixed percentage of equity.
    """

    def __init__(self, engine, croupier, fixed_pct: float = 0.01, max_positions: int = 3):
        self.engine = engine
        self.croupier = croupier
        self.fixed_pct = fixed_pct
        self.max_positions = max_positions
        
        # Subscribe to Aggregated Signals
        self.engine.subscribe(EventType.AGGREGATED_SIGNAL, self.on_aggregated_signal)
        
        logger.info(f"✅ FixedPlayer initialized | Bet Size: {fixed_pct:.1%} | Max Positions: {max_positions}")

    async def on_aggregated_signal(self, event: AggregatedSignalEvent):
        """Process aggregated signal and place fixed bet."""
        if event.side == "SKIP":
            return

        # Check position limit
        open_positions = self.croupier.get_open_positions()
        if len(open_positions) >= self.max_positions:
            logger.debug(f"⏭️ Skipping signal - at position limit ({len(open_positions)}/{self.max_positions})")
            return

        # Get current equity
        equity = self.croupier.get_equity()
        
        # Calculate bet size (fixed percentage)
        bet_size = self.fixed_pct
        
        # Extract TP/SL from metadata if available
        tp_pct = event.metadata.get("tp_pct")
        sl_pct = event.metadata.get("sl_pct")
        
        logger.info(f"🎯 Decision: {event.side} | Fixed Bet: {bet_size:.2%} of {equity:.2f}")

        # Emit Decision with unique ID for tracking
        decision_id = f"DEC_{int(time.time()*1000000)}"  # Microsecond precision
        decision = DecisionEvent(
            symbol=event.symbol,
            side=event.side,
            bet_size=bet_size,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            selected_sensor=event.selected_sensor,
        )
        decision.decision_id = decision_id  # Add unique ID
        logger.debug(f"📤 Emitting DecisionEvent {decision_id} for {event.side}")
        await self.engine.dispatch(decision)

    def handle_trade_outcome(self, trade_id: str, won: bool):
        """Handle trade outcome (stateless)."""
        result = "WIN" if won else "LOSS"
        logger.info(f"Trade {trade_id} finished: {result}")
