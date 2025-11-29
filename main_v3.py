"""
Casino V3 - Main Entry Point
Event-Driven Architecture with Paroli Betting
"""
import asyncio
import logging
import sys
import argparse
import os
from pathlib import Path

# Try uvloop for performance
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from config import exchange as exchange_config
from core.v3.engine import Engine
from core.v3.feed import StreamManager
from core.v3.candle_maker import CandleMaker
from core.v3.sensor_manager import SensorManager
from core.v3.signal_aggregator import SignalAggregatorV3
from core.v3.paroli_v3 import ParoliV3
from core.v3.execution import OrderManager
from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors import BybitConnector
from exchanges.connectors.binance.binance_connector import BinanceConnector
from exchanges.connectors.hyperliquid.hyperliquid_connector import HyperliquidConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Casino-V3")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Casino V3 Trading Bot")
    
    parser.add_argument("--exchange", type=str, default="binance", choices=["binance", "hyperliquid", "bybit"],
                        help="Exchange to trade on (default: binance)")
    
    parser.add_argument("--symbol", type=str, default="BTC/USDT:USDT",
                        help="Trading symbol (default: BTC/USDT:USDT)")
    
    parser.add_argument("--mode", type=str, default="testing", choices=["live", "testing", "demo"],
                        help="Execution mode (default: testing)")
    
    parser.add_argument("--wallet", type=str, help="Wallet address (overrides env)")
    parser.add_argument("--key", type=str, help="Private key (overrides env)")
    
    return parser.parse_args()

async def main():
    """Main entry point for Casino V3."""
    args = parse_args()
    
    logger.info(f"🚀 Starting Casino-V3 | Exchange: {args.exchange} | Mode: {args.mode}")
    
    # 1. Initialize Exchange Adapter
    connector = None
    
    if args.exchange == "binance":
        # Binance Connector
        connector = BinanceConnector(
            api_key=args.wallet or exchange_config.API_KEY,
            api_secret=args.key or exchange_config.API_SECRET,
            testnet=(args.mode != "live")
        )
    elif args.exchange == "hyperliquid":
        # Hyperliquid Connector
        connector = HyperliquidConnector(
            api_key=args.wallet,
            secret=args.key,
            mode="testing" if args.mode in ["testing", "demo"] else "live",
            enable_websocket=True
        )
    elif args.exchange == "bybit":
        # Bybit Connector
        connector = BybitConnector(
            api_key=args.wallet or exchange_config.API_KEY,
            api_secret=args.key or exchange_config.API_SECRET,
            testnet=(args.mode != "live")
        )
    
    # Initialize Adapter
    adapter = CCXTAdapter(connector, symbol=args.symbol)
    
    # 2. Initialize Core Engine
    engine = Engine()
    
    # 3. Initialize Croupier (Execution Layer)
    croupier = Croupier(
        adapter=adapter,
        initial_balance=10000.0, # TODO: Fetch actual balance
        mode=args.mode
    )
    
    # 4. Initialize Data Feed
    data_feed = StreamManager(engine, adapter)
    engine.data_feed = data_feed # Important for sensors
    
    # 5. Initialize Candle Maker (Tick → Candle)
    candle_maker = CandleMaker(engine, timeframe="1m")
    
    # 6. Initialize Sensor Manager (Candle → Signals)
    sensor_manager = SensorManager(engine)
    
    # 7. Initialize Signal Aggregator (Signals → Aggregated Signal)
    signal_aggregator = SignalAggregatorV3(engine)
    
    # 8. Initialize Paroli Player (Aggregated Signal → Decision)
    paroli = ParoliV3(engine, croupier)
    
    # 9. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, paroli)
    
    # Start components
    await connector.connect()
    await order_manager.start()
    await engine.start()
    
    # Subscribe to ticker
    logger.info(f"📡 Subscribing to {args.symbol}...")
    await data_feed.subscribe_ticker(args.symbol)
    
    logger.info("✅ Casino-V3 Running | Press Ctrl+C to stop")
    
    try:
        # Keep running
        while engine.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    finally:
        await engine.stop()
        await order_manager.stop()
        await connector.close()

if __name__ == "__main__":
    asyncio.run(main())
