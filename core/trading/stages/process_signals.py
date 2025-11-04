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

        if signals:
            logger.info(f"📡 Detected {len(signals)} signal(s)")
            for signal in signals:
                logger.debug(f"  Signal: {signal.get('side')} from {signal.get('origin')}")

        return context.with_signals(signals)
