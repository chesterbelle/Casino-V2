"""
Backtest Feed for Casino-V3.
Replays historical data as TickEvents.
"""
import asyncio
import logging
import pandas as pd
import time
from typing import Optional, Dict, Any
from .events import TickEvent, EventType
from exchanges.adapters.ccxt_adapter import CCXTAdapter

logger = logging.getLogger(__name__)

class BacktestFeed:
    """
    Simulates a live data feed by replaying historical data.
    """
    def __init__(self, engine, data_path: str, symbol: str, delay: float = 0.001):
        self.engine = engine
        self.data_path = data_path
        self.symbol = symbol
        self.delay = delay  # Delay between events to simulate time
        self.running = False
        self.data = None
        
        # Mock Adapter for Croupier
        self.adapter = self._create_mock_adapter()

    def _create_mock_adapter(self):
        """Create a mock adapter that Croupier can use."""
        # This is a bit hacky: we need an adapter that Croupier accepts
        # but that doesn't actually connect to anything.
        # For V3 backtesting, we might need a VirtualExchangeConnectorV3
        # For now, let's use a dummy object that has 'symbol'
        class MockAdapter:
            def __init__(self, symbol):
                self.symbol = symbol
                # Mock connector for ExchangeStateSync
                self.connector = type('MockConnector', (), {'exchange': type('Exchange', (), {'id': 'mock'})()})()
            async def connect(self): pass
            async def disconnect(self): pass
            
        return MockAdapter(self.symbol)

    def load_data(self):
        """Load data from CSV/Parquet."""
        logger.info(f"📂 Loading backtest data from {self.data_path}...")
        if self.data_path.endswith(".csv"):
            self.data = pd.read_csv(self.data_path)
        elif self.data_path.endswith(".parquet"):
            self.data = pd.read_parquet(self.data_path)
        else:
            raise ValueError("Unsupported file format")
            
        # Ensure columns exist
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in self.data.columns for col in required):
            raise ValueError(f"Data missing required columns: {required}")
            
        # Convert timestamp to datetime and then to epoch seconds
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        self.data['timestamp'] = self.data['timestamp'].astype(int) // 10**9
            
        # Sort by timestamp
        self.data = self.data.sort_values('timestamp').reset_index(drop=True)
        logger.info(f"✅ Loaded {len(self.data)} rows.")

    async def run(self):
        """Start the replay and wait for completion."""
        self.running = True
        self.load_data()
        await self._replay_loop()

    async def connect(self):
        """Legacy connect method."""
        pass

    async def disconnect(self):
        """Stop the replay."""
        self.running = False

    async def subscribe_ticker(self, symbol: str):
        """Mock subscription."""
        logger.info(f"📡 Backtest subscribed to ticker: {symbol}")

    async def _replay_loop(self):
        """Replay data row by row."""
        logger.info("▶️ Starting Backtest Replay...")
        
        for index, row in self.data.iterrows():
            if not self.running:
                break
                
            # Simulate Ticks from Candle
            # For simplicity, we emit 1 tick per candle (Close price)
            # A better simulation would emit Open -> High -> Low -> Close
            
            # 1. Open Tick
            await self._emit_tick(row['timestamp'], row['open'], row['volume'] / 4)
            # 2. High Tick
            await self._emit_tick(row['timestamp'], row['high'], row['volume'] / 4)
            # 3. Low Tick
            await self._emit_tick(row['timestamp'], row['low'], row['volume'] / 4)
            # 4. Close Tick
            await self._emit_tick(row['timestamp'], row['close'], row['volume'] / 4)
            
            if self.delay > 0:
                await asyncio.sleep(self.delay)

        logger.info("🏁 Backtest Replay Finished.")
        self.engine.running = False

    async def _emit_tick(self, timestamp, price, volume):
        """Emit a single tick event."""
        event = TickEvent(
            type=EventType.TICK,
            timestamp=timestamp, # Use historical timestamp
            symbol=self.symbol,
            price=float(price),
            volume=float(volume)
        )
        await self.engine.dispatch(event)
