"""
Script temporal para ejecutar backtesting con balance inicial custom.
"""

import asyncio
import logging
import sys

from config import system
from core.data_sources import BacktestDataSource
from core.trading import TradingSession
from players import paroli_player

# Setup logging
logging.basicConfig(
    level=getattr(logging, system.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("Backtest-Custom")


async def run_backtest_with_balance(data_file: str, initial_balance: float, max_candles: int = None):
    """Run backtest with custom initial balance."""
    logger.info(f"🎰 Starting BACKTEST with custom balance: ${initial_balance:,.2f}")
    logger.info(f"📁 Loading data from: {data_file}")

    # Create backtest data source with custom balance
    source = BacktestDataSource.from_csv(
        data_file,
        initial_balance=initial_balance,  # Custom balance
        normalize_symbol=True,
        force_timeframe="1m",
    )

    # Create session
    session = TradingSession(source, paroli_player, max_candles)

    # Run
    await session.run()

    # Print stats
    stats = source.get_stats()
    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Balance:  ${stats['initial_balance']:,.2f}")
    print(f"Final Balance:    ${stats['final_balance']:,.2f}")
    print(f"Final Equity:     ${stats['final_equity']:,.2f}")
    print(f"Net PnL:          ${stats['net_pnl']:+,.2f}")
    print(f"Total Fees:       ${stats['total_fees']:,.2f}")
    print(f"Total Trades:     {stats['total_trades']}")
    print(f"Wins:             {stats['wins']}")
    print(f"Losses:           {stats['losses']}")
    print(f"Win Rate:         {stats['win_rate']:.2%}")
    print(f"Avg Win:          ${stats['avg_win']:+,.2f}")
    print(f"Avg Loss:         ${stats['avg_loss']:+,.2f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_backtest_custom_balance.py <data_file> <initial_balance> [max_candles]")
        sys.exit(1)

    data_file = sys.argv[1]
    initial_balance = float(sys.argv[2])
    max_candles = int(sys.argv[3]) if len(sys.argv) > 3 else None

    asyncio.run(run_backtest_with_balance(data_file, initial_balance, max_candles))
