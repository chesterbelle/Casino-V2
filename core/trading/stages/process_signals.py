"""
Process Signals Stage - Casino V2

Processes candle through sensors to detect trading signals.
"""

import logging

from core.trading.context import TradingContext
from core.trading.pipeline import Stage

logger = logging.getLogger(__name__)


class ProcessSignalsStage(Stage):
    """
    Process candle through sensors to detect signals.

    Takes a candle and runs it through all active sensors.
    Returns context with detected signals.
    """

    def __init__(self, sensor_manager):
        """
        Initialize stage with sensor manager.

        Args:
            sensor_manager: SensorManager instance
        """
        self.sensor_manager = sensor_manager

    async def process(self, context: TradingContext) -> TradingContext:
        """
        Process candle through sensors.

        Args:
            context: Trading context with candle

        Returns:
            Context with detected signals
        """
        # Convert Candle to dict for sensors (legacy compatibility)
        candle_dict = {
            "timestamp": context.candle.timestamp,
            "open": context.candle.open,
            "high": context.candle.high,
            "low": context.candle.low,
            "close": context.candle.close,
            "volume": context.candle.volume,
            "symbol": context.candle.symbol,
            "timeframe": context.candle.timeframe,
        }

        # Process through sensors
        signals = self.sensor_manager.process_candle(candle_dict)

        # Allow players to force a synthetic signal (e.g. debug_player wants to bet on first candle)
        try:
            meta = context.metadata or {}
            if not signals and meta.get("force_bet_first"):
                # Create a synthetic SHORT signal attributed to the debug player
                synthetic = {
                    "timestamp": candle_dict.get("timestamp"),
                    "symbol": candle_dict.get("symbol"),
                    "timeframe": candle_dict.get("timeframe"),
                    "side": "SHORT",
                    "contributors": ["debug_player"],
                    "origin": "debug_player",
                    "features": {"forced": True},
                }
                signals = [synthetic]
                logger.info("🧪 Injected synthetic signal (force_bet_first) from debug_player")
        except Exception:
            # Be defensive: if anything fails, fallback to sensor signals
            pass

        if signals:
            logger.info(f"📡 Detected {len(signals)} signal(s)")
            for signal in signals:
                logger.debug(f"  Signal: {signal.get('side')} from {signal.get('origin')}")

        return context.with_signals(signals)
