"""
Casino V3 - Backtest Entry Point
Event-Driven Architecture with Paroli Betting
"""
import asyncio
import logging
import sys
from pathlib import Path

from core.v3.engine import Engine
from core.v3.backtest_feed import BacktestFeed
from core.v3.candle_maker import CandleMaker
from core.v3.sensor_manager import SensorManager
from core.v3.signal_aggregator import SignalAggregatorV3
from core.v3.paroli_v3 import ParoliV3
from core.v3.execution import OrderManager
from croupier.croupier import Croupier
from exchanges.connectors.virtual_exchange import VirtualExchangeConnector
from exchanges.adapters.ccxt_adapter import CCXTAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BacktestV3")

def parse_args():
    """Parse command line arguments."""
    data_file = "data/raw/LTCUSDT_1m__1d.csv"
    symbol = "LTC/USDT:USDT"
    delay = 0.0
    
    for arg in sys.argv[1:]:
        if arg.startswith("--data="):
            data_file = arg.split("=")[1]
        elif arg.startswith("--symbol="):
            symbol = arg.split("=")[1]
        elif arg.startswith("--delay="):
            delay = float(arg.split("=")[1])
    
    return data_file, symbol, delay

async def main():
    """Main backtest entry point."""
    data_file, symbol, delay = parse_args()
    
    logger.info(f"🚀 Starting Casino-V3 Backtest | Data: {data_file}")
    
    # 1. Initialize Core Engine
    engine = Engine()
    
    # 2. Initialize Virtual Exchange & Adapter
    virtual_exchange = VirtualExchangeConnector(initial_balance=10000.0)
    await virtual_exchange.connect()
    adapter = CCXTAdapter(virtual_exchange, symbol=symbol)
    
    # 3. Initialize Croupier with Virtual Exchange
    croupier = Croupier(adapter, initial_balance=10000.0)
    
    # 4. Initialize Backtest Feed
    backtest_feed = BacktestFeed(engine, data_file, symbol, delay=delay)
    engine.data_feed = backtest_feed
    
    # 5. Initialize Candle Maker (Tick → Candle)
    candle_maker = CandleMaker(engine)
    
    # 5. Initialize Sensor Manager (Candle → Signals)
    sensor_manager = SensorManager(engine)
    
    # 6. Initialize Signal Aggregator (Signals → Aggregated Signal)
    signal_aggregator = SignalAggregatorV3(engine)
    
    # 7. Initialize Paroli Player (Aggregated Signal → Decision)
    paroli = ParoliV3(engine, croupier)
    
    # 8. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, paroli)
    
    # Start components
    await order_manager.start()
    await engine.start(blocking=False)
    
    # Run backtest
    await backtest_feed.run()
    
    # Cleanup
    await engine.stop()
    await order_manager.stop()
    
    logger.info("✅ Backtest Complete")

if __name__ == "__main__":
    asyncio.run(main())
