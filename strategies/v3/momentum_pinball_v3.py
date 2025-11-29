"""
Momentum Pinball V3 - Event-Driven Implementation.
"""
import logging
import time
from collections import deque
from typing import Optional, List
import numpy as np

from core.v3.events import TickEvent, SignalEvent, EventType
from .base import StrategyV3

logger = logging.getLogger(__name__)

class Candle:
    def __init__(self, timestamp, open, high, low, close, volume):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

class CandleBuilder:
    """Aggregates ticks into 1m candles."""
    def __init__(self, timeframe_seconds=60):
        self.timeframe = timeframe_seconds
        self.current_candle: Optional[Candle] = None
        self.last_candle_time = 0

    def process_tick(self, tick: TickEvent) -> Optional[Candle]:
        """
        Process a tick and return a closed candle if the minute has passed.
        """
        # Calculate candle start time (floor to minute)
        tick_time = int(tick.timestamp)
        candle_start_time = tick_time - (tick_time % self.timeframe)

        closed_candle = None

        # If we have a current candle and we moved to a new minute
        if self.current_candle and candle_start_time > self.last_candle_time:
            closed_candle = self.current_candle
            # Reset for new candle
            self.current_candle = None
        
        # Initialize new candle if needed
        if not self.current_candle:
            self.current_candle = Candle(
                timestamp=candle_start_time,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume
            )
            self.last_candle_time = candle_start_time
        else:
            # Update current candle
            self.current_candle.high = max(self.current_candle.high, tick.price)
            self.current_candle.low = min(self.current_candle.low, tick.price)
            self.current_candle.close = tick.price
            self.current_candle.volume += tick.volume

        return closed_candle

class MomentumPinballV3(StrategyV3):
    """
    Event-Driven Momentum Pinball.
    """
    def __init__(self, engine, ema_period=34, rsi_period=2):
        super().__init__(engine)
        self.candle_builder = CandleBuilder(timeframe_seconds=60)  # 1m candles
        
        # Strategy Params
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.oversold = 10.0
        self.overbought = 90.0
        
        # State
        self.closes = deque(maxlen=ema_period + 10)
        self.ema_val = None

    async def on_tick(self, tick: TickEvent):
        """Handle new tick."""
        # 1. Update Candle Builder
        closed_candle = self.candle_builder.process_tick(tick)
        
        # 2. If candle closed, update indicators and check signal
        if closed_candle:
            await self.on_candle_close(closed_candle)

    async def on_candle_close(self, candle: Candle):
        """Handle closed candle."""
        close = candle.close
        self.closes.append(close)
        
        # Update EMA
        self._update_ema(close)
        
        # Calculate RSI
        rsi = self._calculate_rsi()
        
        logger.info(f"🕯️ Candle Closed: {close} | EMA: {self.ema_val:.2f} | RSI: {rsi:.2f}")
        
        # Check Signal
        if self.ema_val and rsi:
            signal_event = None
            
            # Long Condition: Uptrend (Price > EMA) + RSI Oversold
            if close > self.ema_val and rsi < self.oversold:
                logger.info(f"🚀 LONG SIGNAL | RSI: {rsi:.2f} < {self.oversold}")
                signal_event = SignalEvent(
                    timestamp=time.time(),
                    symbol=self.engine.data_feed.adapter.symbol, # Access symbol from adapter
                    side="LONG",
                    strategy_name="MomentumPinballV3",
                    score=1.0,
                    metadata={"rsi": rsi, "ema": self.ema_val, "close": close}
                )
                
            # Short Condition: Downtrend (Price < EMA) + RSI Overbought
            elif close < self.ema_val and rsi > self.overbought:
                logger.info(f"🔻 SHORT SIGNAL | RSI: {rsi:.2f} > {self.overbought}")
                signal_event = SignalEvent(
                    timestamp=time.time(),
                    symbol=self.engine.data_feed.adapter.symbol,
                    side="SHORT",
                    strategy_name="MomentumPinballV3",
                    score=1.0,
                    metadata={"rsi": rsi, "ema": self.ema_val, "close": close}
                )
            
            # Dispatch Signal
            if signal_event:
                await self.engine.dispatch(signal_event)

    def _update_ema(self, close: float):
        k = 2 / (self.ema_period + 1)
        if self.ema_val is None:
            self.ema_val = close
        else:
            self.ema_val = (close * k) + (self.ema_val * (1 - k))

    def _calculate_rsi(self) -> float:
        if len(self.closes) < self.rsi_period + 1:
            return 50.0

        prices = list(self.closes)
        deltas = np.diff(prices)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))

        # Simple Mean (Cutler's RSI) for speed/stability
        avg_gain = np.mean(gains[-self.rsi_period :])
        avg_loss = np.mean(losses[-self.rsi_period :])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
