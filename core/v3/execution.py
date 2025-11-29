"""
Execution Layer for Casino-V3.
Handles DecisionEvents from Paroli and executes orders via Croupier.
"""
import logging
import time
import asyncio
from typing import Dict, Any, Optional

from core.v3.events import Event, EventType
from croupier.croupier import Croupier

logger = logging.getLogger(__name__)

class OrderManager:
    """
    Executes trading decisions from Paroli.
    Subscribes to DECISION events (from Paroli).
    """
    def __init__(self, engine, croupier: Croupier, paroli=None):
        self.engine = engine
        self.croupier = croupier
        self.paroli = paroli
        self.active = False
        self.pending_trades = {}  # trade_id -> decision
        
        # Subscribe to DECISION events (will come from Paroli)
        self.engine.subscribe(EventType.SYSTEM, self.on_decision)  # Using SYSTEM for now

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
        if not hasattr(event, 'bet_size'):
            return
        
        if event.side == "SKIP":
            logger.info("⏭️ Decision: SKIP - no trade")
            return

        logger.info(f"📩 Decision Received: {event.symbol} {event.side} "
                   f"(Size: {event.bet_size:.2%}, Step: {event.paroli_step})")
        
        # Construct Order Payload
        trade_id = f"V3_{int(time.time()*1000)}"
        order_payload = {
            "trade_id": trade_id,
            "symbol": event.symbol,
            "side": event.side,
            "size": event.bet_size,  # Fraction of equity
            "take_profit": 0.01,  # 1% TP
            "stop_loss": 0.01,  # 1% SL
            "timestamp": str(event.timestamp),
            "ghost": False
        }
        
        # Store for outcome tracking
        self.pending_trades[trade_id] = event
        
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
    
    def handle_trade_outcome(self, trade_id: str, won: bool):
        """Callback when trade closes - update Paroli."""
        if self.paroli and trade_id in self.pending_trades:
            self.paroli.handle_trade_outcome(trade_id, won)
            del self.pending_trades[trade_id]

