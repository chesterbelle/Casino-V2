"""
Casino V3 - Backtest Entry Point
Event-Driven Architecture with Paroli Betting
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
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.virtual_exchange import VirtualExchangeConnector
from players.paroli import ParoliV3

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
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
    backtest_feed = BacktestFeed(engine, data_file, symbol, delay=delay, exchange_connector=virtual_exchange)
    engine.data_feed = backtest_feed

    # 5. Initialize Candle Maker (Tick → Candle)
    CandleMaker(engine, timeframe_seconds=60)

    # 6. Initialize Sensor Manager (Candle → Signal)
    SensorManager(engine)

    # 7. Initialize Signal Aggregator (Signal → Aggregated Signal)
    SignalAggregatorV3(engine)

    # 7. Initialize Paroli Player (Aggregated Signal → Decision)
    paroli = ParoliV3(engine, croupier)

    # 8. Initialize Order Manager (Decision → Execution)
    order_manager = OrderManager(engine, croupier, paroli)

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
