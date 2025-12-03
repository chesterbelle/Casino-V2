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

# Setup observability
from core.observability import (
    configure_logging,
    start_metrics_server,
    stop_metrics_server,
    update_balance,
)
from core.observability.metrics import bot_info
from core.sensor_manager import SensorManager
from croupier.croupier import Croupier
from decision.aggregator import SignalAggregatorV3
from exchanges.adapters import ExchangeAdapter
from exchanges.connectors import BinanceNativeConnector, HyperliquidNativeConnector

# Configure structured logging (console format for development)
configure_logging(log_level="INFO", log_format="console")
logger = logging.getLogger("Casino-V3")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Casino V3 Trading Bot")

    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        choices=["binance", "hyperliquid"],
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

    parser.add_argument(
        "--interval",
        type=str,
        default="1m",
        choices=["1m", "5m", "15m", "1h"],
        help="Candle timeframe (default: 1m)",
    )

    parser.add_argument(
        "--player",
        type=str,
        default="paroli",
        choices=["paroli", "fixed"],
        help="Strategy player to use (default: paroli)",
    )

    parser.add_argument("--wallet", type=str, help="Wallet address (overrides env)")
    parser.add_argument("--key", type=str, help="Private key (overrides env)")

    return parser.parse_args()


async def main():
    """Main entry point for Casino V3."""
    args = parse_args()

    logger.info(f"🚀 Starting Casino-V3 | Exchange: {args.exchange} | Mode: {args.mode}")

    # 0. Start Metrics Server
    logger.info("📊 Starting metrics server...")
    try:
        await start_metrics_server(port=8000)
        # Set bot info
        bot_info.info(
            {
                "version": "3.0.0",
                "exchange": args.exchange,
                "mode": args.mode,
                "symbol": args.symbol,
            }
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to start metrics server: {e}")

    # 1. Initialize Exchange Adapter
    connector = None

    if args.exchange == "binance":
        # Binance Native Connector (SDK)
        connector = BinanceNativeConnector(
            api_key=args.wallet or exchange_config.BINANCE_API_KEY,
            secret=args.key or exchange_config.BINANCE_API_SECRET,
            mode="demo" if args.mode != "live" else "live",
        )
    elif args.exchange == "hyperliquid":
        # Hyperliquid Native Connector
        import os

        connector = HyperliquidNativeConnector(
            api_key=args.key or os.getenv("HYPERLIQUID_API_SECRET"),  # Agent Private Key
            account_address=args.wallet or os.getenv("HYPERLIQUID_MAIN_WALLET"),  # Main Account Address
            mode="demo" if args.mode != "live" else "live",
            enable_websocket=True,
        )
    # Initialize Adapter
    adapter = ExchangeAdapter(connector, symbol=args.symbol)

    # 2. Initialize Core Engine
    engine = Engine()

    # 3. Initialize Croupier (Execution Layer)
    # Fetch actual balance from exchange
    await connector.connect()
    initial_balance_data = await connector.fetch_balance()
    initial_balance = initial_balance_data.get("total", {}).get("USDT", 10000.0)
    logger.info(f"💰 Initial Balance: {initial_balance:.2f} USDT")

    croupier = Croupier(exchange_adapter=adapter, initial_balance=initial_balance)

    # 4. Initialize Data Feed
    data_feed = StreamManager(adapter, engine)
    engine.data_feed = data_feed  # Important for sensors

    # 5. Initialize Candle Maker (Tick → Candle)
    # Convert interval to seconds
    interval_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
    timeframe_seconds = interval_map.get(args.interval, 60)
    CandleMaker(engine, timeframe_seconds=timeframe_seconds)

    # 6. Initialize Sensor Manager (Candle → Signal)
    SensorManager(engine)

    # 7. Initialize Signal Aggregator (Signal → Aggregated Signal)
    aggregator = SignalAggregatorV3(engine)
    tracker = aggregator.tracker  # Get tracker from aggregator

    # 8. Initialize Player (Aggregated Signal → Decision)
    if args.player == "fixed":
        from players.fixed import FixedPlayer

        logger.info("🎰 Using Fixed Player")
        player = FixedPlayer(engine, croupier, fixed_pct=0.01, max_positions=1)
    else:
        from players.paroli import ParoliV3

        logger.info("🎰 Using Paroli Player")
        player = ParoliV3(engine, croupier)

    # 9. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, player, tracker)

    # --- Stats Collection ---
    closed_trades = []

    def on_trade_close(trade_id, result):
        """Callback to collect closed trade results."""
        closed_trades.append(result)

    # Hook callback into PositionTracker
    croupier.position_tracker.on_close_callback = on_trade_close

    # 10. Initialize State Manager (for crash recovery)
    from core.state import StateManager

    state_manager = StateManager(
        position_tracker=croupier.position_tracker,
        balance_manager=croupier.balance_manager,
        state_dir="./state",
        save_interval=5,
    )

    # Attempt recovery from previous session
    logger.info("🔄 Attempting state recovery...")
    recovered = await state_manager.recover()

    if recovered:
        logger.info("✅ State recovered from previous session")
        # Reconcile with exchange to ensure consistency
        try:
            await croupier.reconcile_positions(args.symbol)
        except Exception as e:
            logger.error(f"❌ Post-recovery reconciliation failed: {e}")
    else:
        logger.info("📝 Starting fresh session")
        await state_manager.start(initial_balance)

    # Start components (connector already connected for balance fetch)
    # await connector.connect()  # Already connected above

    # Store initial balance for PnL calc (use recovered or fresh)
    state = state_manager.persistent_state.get_state()
    if state:
        initial_balance = state.initial_balance
    logger.info(f"💰 Session Initial Balance: {initial_balance:.2f} USDT")

    # Update initial balance metrics
    update_balance(
        exchange=args.exchange,
        total=initial_balance,
        available=initial_balance,
        allocated=0.0,
    )

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

        # 2. Sync final state before closing positions
        logger.info("💾 Syncing final state...")
        try:
            await state_manager.sync_to_persistent()
        except Exception as e:
            logger.error(f"❌ Error syncing final state: {e}")

        # 3. Force close open positions
        try:
            open_positions = croupier.get_open_positions()
            if open_positions:
                logger.info(f"🧹 Force closing {len(open_positions)} open positions...")

                # Get current price for forced close
                try:
                    await adapter.get_current_price(args.symbol)
                except Exception:
                    logger.warning("⚠️ Could not fetch current price for forced close, using last known")
                    # Should ideally get from last candle or tick

            await croupier.cleanup_symbol(args.symbol)
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

        # 4. Stop state manager (final save)
        logger.info("🛑 Stopping state manager...")
        try:
            await state_manager.stop()
        except Exception as e:
            logger.error(f"❌ Error stopping state manager: {e}")

        # 5. Stop metrics server
        logger.info("📊 Stopping metrics server...")
        try:
            await stop_metrics_server()
        except Exception as e:
            logger.error(f"❌ Error stopping metrics server: {e}")

        # 6. Generate Session Report (using tracker state which should be updated by cleanup)
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

        print("\n========================================")
        print(f"📊 SESSION REPORT - {args.symbol}")
        print("========================================")
        print(f"   Trades Total          : {total_trades}")
        print(f"   Wins / Losses         : {wins} / {losses}")
        print(f"   WinRate               : {win_rate:.2f}%")
        print(f"   Comisiones (Est)      : {total_fees:.2f}")
        print(f"   Balance Inicial       : {initial_balance:.2f}")
        print(f"   Balance Final (Real)  : {real_final_balance:.2f}")
        print(f"   PnL Total             : {total_pnl_real:.2f} ({pnl_pct:.2f}%)")
        print("========================================\n")


if __name__ == "__main__":
    asyncio.run(main())
