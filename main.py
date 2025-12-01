"""
Casino V3 - Main Entry Point
Event-Driven Architecture with Paroli Betting
"""

import argparse
import asyncio
import logging

# Try uvloop for performance
try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from config import exchange as exchange_config
from core.candle_maker import CandleMaker
from core.engine import Engine
from core.execution import OrderManager
from core.feed import StreamManager
from core.sensor_manager import SensorManager
from croupier.croupier import Croupier
from decision.aggregator import SignalAggregatorV3
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors import BybitConnector
from exchanges.connectors.binance.binance_connector import BinanceConnector
from exchanges.connectors.hyperliquid.hyperliquid_connector import HyperliquidConnector
from players.paroli import ParoliV3

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("Casino-V3")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Casino V3 Trading Bot")

    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        choices=["binance", "hyperliquid", "bybit"],
        help="Exchange to trade on (default: binance)",
    )

    parser.add_argument("--symbol", type=str, default="BTC/USDT:USDT", help="Trading symbol (default: BTC/USDT:USDT)")

    parser.add_argument(
        "--mode",
        type=str,
        default="testing",
        choices=["live", "testing", "demo"],
        help="Execution mode (default: testing)",
    )

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
            api_key=args.wallet or exchange_config.BINANCE_API_KEY,
            secret=args.key or exchange_config.BINANCE_API_SECRET,
            mode="demo" if args.mode != "live" else "live",
        )
    elif args.exchange == "hyperliquid":
        # Hyperliquid Connector
        connector = HyperliquidConnector(
            api_key=args.wallet,
            secret=args.key,
            mode="testing" if args.mode in ["testing", "demo"] else "live",
            enable_websocket=True,
        )
    elif args.exchange == "bybit":
        # Bybit Connector
        connector = BybitConnector(
            api_key=args.wallet or exchange_config.BYBIT_API_KEY,
            api_secret=args.key or exchange_config.BYBIT_API_SECRET,
            testnet=(args.mode != "live"),
        )

    # Initialize Adapter
    adapter = CCXTAdapter(connector, symbol=args.symbol)

    # 2. Initialize Core Engine
    engine = Engine()

    # 3. Initialize Croupier (Execution Layer)
    croupier = Croupier(exchange_adapter=adapter, initial_balance=10000.0)  # TODO: Fetch actual balance

    # 4. Initialize Data Feed
    data_feed = StreamManager(adapter, engine)
    engine.data_feed = data_feed  # Important for sensors

    # 5. Initialize Candle Maker (Tick → Candle)
    CandleMaker(engine, timeframe_seconds=60)

    # 6. Initialize Sensor Manager (Candle → Signal)
    SensorManager(engine)

    # 7. Initialize Signal Aggregator (Signal → Aggregated Signal)
    aggregator = SignalAggregatorV3(engine)
    tracker = aggregator.tracker  # Get tracker from aggregator

    # 8. Initialize Fixed Player (Aggregated Signal → Decision)
    from players.fixed import FixedPlayer
    player = FixedPlayer(engine, croupier, fixed_pct=0.01, max_positions=3)

    # 9. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, player, tracker)

    # --- Stats Collection ---
    closed_trades = []

    def on_trade_close(trade_id, result):
        """Callback to collect closed trade results."""
        closed_trades.append(result)

    # Hook callback into PositionTracker
    croupier.position_tracker.on_close_callback = on_trade_close
    
    # Store initial balance for PnL calc
    # Note: In demo/live, this might be the exchange balance
    initial_balance = await connector.fetch_balance()
    initial_balance = initial_balance.get("total", {}).get("USDT", 0.0)
    logger.info(f"💰 Initial Balance for Report: {initial_balance:.2f} USDT")

    # Start components
    await connector.connect()
    await order_manager.start()
    await engine.start(blocking=False)

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
        logger.info("🧹 Cleaning up resources...")
        
        # 1. Stop components to prevent new signals
        await engine.stop()
        await order_manager.stop()

        # 2. Force close open positions
        try:
            open_positions = croupier.get_open_positions()
            if open_positions:
                logger.info(f"🧹 Force closing {len(open_positions)} open positions...")
                
                # Get current price for forced close
                try:
                    current_price = await adapter.get_current_price(args.symbol)
                except Exception:
                    logger.warning("⚠️ Could not fetch current price for forced close, using last known")
                    current_price = 0.0 # Should ideally get from last candle or tick
                
                import time
            await croupier.cleanup_symbol(args.symbol)
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

        # 3. Generate Session Report (using tracker state which should be updated by cleanup)
        logger.info("📊 Generating Session Report...")
        
        # Get closed trades from our collection list
        tracker_stats = croupier.position_tracker.get_stats()
        total_trades = tracker_stats.get("total_closed", 0)
        wins = tracker_stats.get("total_wins", 0)
        losses = tracker_stats.get("total_losses", 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        # Fetch REAL final balance from exchange
        try:
            logger.info("💰 Fetching final balance from exchange...")
            await asyncio.sleep(2)  # Wait for settlement
            final_balance_data = await connector.fetch_balance()
            real_final_balance = final_balance_data.get("total", {}).get("USDT", 0.0)
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch final balance: {e}")
            # Fallback to estimated calculation
            total_pnl_est = sum(t.get("pnl", 0.0) for t in closed_trades)
            total_fees_est = sum(t.get("fee", 0.0) for t in closed_trades)
            real_final_balance = initial_balance + total_pnl_est - total_fees_est

        # Calculate PnL based on real balance difference
        total_pnl_real = real_final_balance - initial_balance
        pnl_pct = (total_pnl_real / initial_balance * 100) if initial_balance > 0 else 0.0
        
        # Calculate fees from closed trades for reference (approximate)
        total_fees = sum(t.get("fee", 0.0) for t in closed_trades)

        print(f"\n========================================")
        print(f"📊 SESSION REPORT - {args.symbol}")
        print(f"========================================")
        print(f"   Trades Total          : {total_trades}")
        print(f"   Wins / Losses         : {wins} / {losses}")
        print(f"   WinRate               : {win_rate:.2f}%")
        print(f"   Comisiones (Est)      : {total_fees:.2f}")
        print(f"   Balance Inicial       : {initial_balance:.2f}")
        print(f"   Balance Final (Real)  : {real_final_balance:.2f}")
        print(f"   PnL Total             : {total_pnl_real:.2f} ({pnl_pct:.2f}%)")
        print(f"========================================\n")


if __name__ == "__main__":
    asyncio.run(main())
