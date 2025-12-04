"""
Casino V3 - Backtesting Module
Event-Driven Architecture with Fixed Bet Sizing
"""

import asyncio
import logging
import sys

from core.backtest_feed import BacktestFeed
from core.candle_maker import CandleMaker
from core.engine import Engine
from core.execution import OrderManager
from core.sensor_manager import SensorManager
from croupier.croupier import Croupier
from decision.aggregator import SignalAggregatorV3
from exchanges.adapters import ExchangeAdapter
from exchanges.connectors.virtual_exchange import VirtualExchangeConnector
from players.adaptive import AdaptivePlayer

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("BacktestV3")


def parse_args():
    """Parse command line arguments."""
    data_file = "data/raw/LTCUSDT_1m__1d.csv"
    symbol = "LTC/USDT:USDT"
    delay = 0.0
    # Player configuration
    bet_size = 0.01  # 1% fixed bet size
    max_positions = 3  # Default for Fixed player

    for arg in sys.argv[1:]:
        if arg.startswith("--data="):
            data_file = arg.split("=")[1]
        elif arg.startswith("--symbol="):
            symbol = arg.split("=")[1]
        elif arg.startswith("--delay="):
            delay = float(arg.split("=")[1])
        elif arg.startswith("--max-positions="):
            max_positions = int(arg.split("=")[1])
        elif arg.startswith("--bet-size="):
            bet_size = float(arg.split("=")[1])

    return data_file, symbol, delay, bet_size, max_positions


async def main():
    """Main backtest entry point."""
    data_file, symbol, delay, bet_size, max_positions = parse_args()

    logger.info(f"🚀 Starting Casino-V3 Backtest | Data: {data_file}")

    # Detect timeframe from filename (e.g., LTCUSDT_5m__30d.csv -> 5m)
    import re

    match = re.search(r"_(\d+[mh])_", data_file)
    timeframe = match.group(1) if match else "1m"
    logger.info(f"📊 Detected timeframe: {timeframe}")

    # 1. Initialize Core Engine
    engine = Engine()

    # 2. Initialize Virtual Exchange & Adapter
    virtual_exchange = VirtualExchangeConnector(initial_balance=10000.0)
    await virtual_exchange.connect()
    adapter = ExchangeAdapter(virtual_exchange, symbol=symbol)

    # 3. Initialize Croupier with Virtual Exchange
    croupier = Croupier(adapter, initial_balance=10000.0)

    # 4. Initialize Backtest Feed
    backtest_feed = BacktestFeed(engine, data_file, symbol, delay=delay, exchange_connector=virtual_exchange)
    engine.data_feed = backtest_feed

    # 5. Initialize Candle Maker (Tick → Candle)
    CandleMaker(engine, timeframe_seconds=60)

    # 6. Initialize Sensor Manager (Candle → Signal) with timeframe
    SensorManager(engine, timeframe=timeframe)

    # 7. Initialize Signal Aggregator (Signal → Aggregated Signal)
    aggregator = SignalAggregatorV3(engine)
    tracker = aggregator.tracker  # Get tracker from aggregator

    # 7. Initialize Player (Aggregated Signal → Decision)
    logger.info(f"🎰 Initializing AdaptivePlayer (bet_size={bet_size:.2%}, max_positions={max_positions})")
    player = AdaptivePlayer(engine, croupier, fixed_pct=bet_size, max_positions=max_positions)

    # 8. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, player, tracker)

    # --- Stats Collection ---
    closed_trades = []

    def on_trade_close(trade_id, result):
        """Callback to collect closed trade results."""
        closed_trades.append(result)

    # Hook callback into PositionTracker
    croupier.position_tracker.on_close_callback = on_trade_close

    # Store initial balance for PnL calc
    initial_balance = croupier.get_balance()

    # Start components
    await order_manager.start()
    await engine.start(blocking=False)

    # Run backtest
    await backtest_feed.run()

    # Cleanup
    await engine.stop()
    await order_manager.stop()

    # Force close any remaining positions to capture PnL
    if croupier.get_open_positions():
        logger.info("🧹 Force closing remaining positions...")
        # Create a dummy candle with final price from virtual exchange
        final_price = virtual_exchange._current_price
        final_timestamp = virtual_exchange._current_timestamp
        dummy_candle = {
            "timestamp": final_timestamp,
            "open": final_price,
            "high": final_price,
            "low": final_price,
            "close": final_price,
            "market": symbol,
            "timeframe": "1m",
        }
        forced_closes = croupier.position_tracker.force_close_all_positions(dummy_candle)
        for result in forced_closes:
            on_trade_close(result["trade_id"], result)

    # --- Generate Report ---
    logger.info("✅ Backtest Complete")

    # Save sensor tracker state
    tracker.save_state()
    logger.info(f"💾 Sensor stats saved to {tracker.state_file}")

    # Log top sensors
    top_sensors = tracker.get_top_sensors(n=10)
    if top_sensors:
        logger.info("🏆 Top 10 Sensors by Score:")
        for i, (sensor_id, score) in enumerate(top_sensors, 1):
            stats = tracker.get_stats(sensor_id)
            logger.info(
                f"   {i}. {sensor_id}: {score:.3f} "
                f"(WR: {stats.win_rate_short:.1%}, Exp: {stats.expectancy:.4f}, Trades: {stats.total_trades})"
            )

    # Calculate stats
    total_trades = len(closed_trades)
    wins = sum(1 for t in closed_trades if t["result"] == "WIN")
    losses = sum(1 for t in closed_trades if t["result"] == "LOSS")
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    total_commissions = sum(t.get("fee", 0.0) for t in closed_trades)
    total_funding = sum(t.get("funding", 0.0) for t in closed_trades)
    liquidations = sum(1 for t in closed_trades if t.get("liquidated", False))

    # Calculate PnL from trades to include forced closes
    total_pnl = sum(t.get("pnl", 0.0) for t in closed_trades)
    final_balance = initial_balance + total_pnl
    pnl_pct = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0.0

    print("\n" + "=" * 40)
    print(f"📊 BACKTEST REPORT - {symbol}")
    print("=" * 40)
    print(f"   Wins / Losses         : {wins} / {losses}")
    print(f"   WinRate (BET)         : {win_rate:.2f}%")
    print(f"   Comisiones totales    : {total_commissions:.2f}")
    print(f"   Funding total         : {total_funding:.2f}")
    print(f"   Liquidaciones         : {liquidations}")
    print(f"   Balance final         : {final_balance:.2f}")
    print(f"   PnL Total             : {total_pnl:+.2f} ({pnl_pct:+.2f}%)")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
