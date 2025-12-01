"""
Paroli Player for Casino-V3.
Progressive betting: 1x → 1x → 3x on wins, reset on loss.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from config import paroli
from core.events import Event, EventType
from decision.aggregator import AggregatedSignalEvent

logger = logging.getLogger(__name__)

# Configuration
BASE_DIVISOR = getattr(paroli, "BASE_DIVISOR", 100)
PROGRESSION = getattr(paroli, "PROGRESSION", (1, 1, 3))
MAX_POSITION_SIZE = getattr(paroli, "MAX_POSITION_SIZE", 0.02)
LEVERAGE = getattr(paroli, "LEVERAGE", 10)
RESET_ON_LOSS = getattr(paroli, "RESET_ON_LOSS", True)
RESET_AFTER_CYCLE = getattr(paroli, "RESET_AFTER_CYCLE", True)

# State file
STATE_FILE = Path("state/paroli_state.json")


class DecisionEvent(Event):
    """Decision event with bet sizing from Paroli."""

    def __init__(
        self,
        symbol: str,
        side: str,
        bet_size: float,
        paroli_step: int,
        unit_size: float,
        tp_pct: Optional[float] = None,
        sl_pct: Optional[float] = None,
    ):
        super().__init__(type=EventType.SYSTEM, timestamp=time.time())  # Will add DECISION type later
        self.symbol = symbol
        self.side = side
        self.bet_size = bet_size
        self.paroli_step = paroli_step
        self.unit_size = unit_size
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct


class ParoliV3:
    """
    Paroli progressive betting system.
    Subscribes to: AGGREGATED_SIGNAL events
    Emits: DECISION events (with bet size)
    """

    def __init__(self, engine, croupier):
        self.engine = engine
        self.croupier = croupier
        self.max_positions = 1  # Paroli requires single position for progression

        # Paroli state
        self.unit: Optional[float] = None
        self.step: int = 0
        self.last_trade_id: Optional[str] = None

        # Load state if exists
        self._load_state()

        # Subscribe to aggregated signals
        self.engine.subscribe(EventType.AGGREGATED_SIGNAL, self.on_aggregated_signal)

        logger.info(f"✅ ParoliV3 initialized (step={self.step}, unit={self.unit}, max_positions={self.max_positions})")

    async def on_aggregated_signal(self, event: AggregatedSignalEvent):
        """Process aggregated signal and calculate bet size."""
        if event.side == "SKIP":
            return

        # Check position limit (Paroli requires single position for progression)
        open_positions = self.croupier.get_open_positions()
        if len(open_positions) >= self.max_positions:
            logger.debug(f"⏭️ Skipping signal - at position limit ({len(open_positions)}/{self.max_positions})")
            return

        # Get current equity from Croupier
        equity = self.croupier.get_equity()

        # Initialize unit if needed
        if self.unit is None:
            self.unit = max(equity / BASE_DIVISOR, 0.0)
            logger.info(f"💰 Initialized unit: {self.unit:.4f} (equity: {equity:.2f})")

        # Calculate bet size based on current step
        multiplier = PROGRESSION[self.step]
        bet_size = self.unit * multiplier

        # Apply max position size limit
        max_bet = equity * MAX_POSITION_SIZE
        if bet_size > max_bet:
            logger.warning(f"⚠️ Bet size {bet_size:.4f} exceeds max {max_bet:.4f}, capping")
            bet_size = max_bet

        # Extract TP/SL from metadata
        metadata = getattr(event, "metadata", {}) or {}
        tp_pct = metadata.get("tp_pct")
        sl_pct = metadata.get("sl_pct")

        # Create decision event
        decision = DecisionEvent(
            symbol=event.symbol,
            side=event.side,
            bet_size=bet_size / equity if equity > 0 else 0,  # Fraction of equity
            paroli_step=self.step,
            unit_size=self.unit,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
        )

        logger.info(f"💾 State Saved | Step: {self.step} | " f"Unit: {self.unit:.2f}")

        # Emit decision
        await self.engine.dispatch(decision)

        logger.info(
            f"🎯 Decision: {event.side} | Step {self.step} | "
            f"Bet: {bet_size:.4f} ({decision.bet_size:.2%} of equity)"
        )

        # Save state
        self._save_state()

    def handle_trade_outcome(self, trade_id: str, won: bool):
        """Update progression based on trade outcome."""
        if won:
            # Advance to next step (max out at last step)
            self.step = min(self.step + 1, len(PROGRESSION) - 1)
            logger.info(f"✅ Win! Advanced to step {self.step}")

            # Reset after completing full cycle
            if RESET_AFTER_CYCLE and self.step >= len(PROGRESSION) - 1:
                logger.info("🔄 Completed full cycle, resetting")
                self.step = 0
                self.unit = None
        else:
            # Reset on loss
            if RESET_ON_LOSS:
                logger.info("❌ Loss! Resetting progression")
                self.step = 0
                self.unit = None

        self.last_trade_id = trade_id
        self._save_state()

    def _load_state(self):
        """Load Paroli state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                self.unit = state.get("unit")
                self.step = state.get("step", 0)
                self.last_trade_id = state.get("last_trade_id")
                logger.info(f"📂 Loaded state: step={self.step}, unit={self.unit}")
            except Exception as e:
                logger.error(f"❌ Failed to load state: {e}")

    def _save_state(self):
        """Save Paroli state to file."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = {
                "unit": self.unit,
                "step": self.step,
                "last_trade_id": self.last_trade_id,
                "timestamp": time.time(),
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save state: {e}")
