"""
Casino V2 - Main Entry Point

Nueva arquitectura unificada:
- Una sola TradingSession para todos los modos
- Data sources intercambiables (backtest, testing, live)
- Pipeline limpio y testeable
"""

import asyncio
import logging
import sys

from core import config
from core.data_sources import BacktestDataSource, LiveDataSource, TestingDataSource
from core.trading import TradingSession
from players import fixed_player, kelly_player, paroli_player
from tables.connectors import KrakenConnector, ResilientConnector

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("Casino-V2")

# Available players
PLAYERS = {
    "paroli": paroli_player,
    "kelly": kelly_player,
    "fixed": fixed_player,
}


def parse_args():
    """Parse command line arguments."""
    mode = getattr(config, "MODE", "backtest").lower()
    player_name = "paroli"
    symbol = None
    interval = None
    max_candles = None
    data_file = None

    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=")[1].lower()
        elif arg.startswith("--player="):
            player_name = arg.split("=")[1].lower()
        elif arg.startswith("--symbol="):
            symbol = arg.split("=")[1]
        elif arg.startswith("--interval="):
            interval = arg.split("=")[1]
        elif arg.startswith("--max-candles="):
            max_candles = int(arg.split("=")[1])
        elif arg.startswith("--data="):
            data_file = arg.split("=")[1]
        elif arg in ["--help", "-h"]:
            print_help()
            sys.exit(0)

    return mode, player_name, symbol, interval, max_candles, data_file


def print_help():
    """Print help message."""
    print(
        """
Casino V2 - Trading Bot

Usage:
    python main.py [options]

Options:
    --mode=<mode>           Trading mode: backtest, testing, live
                            Default: backtest

    --player=<player>       Player strategy: paroli, kelly, fixed
                            Default: paroli

    --symbol=<symbol>       Trading pair (for testing/live)
                            Default: BTC/USD

    --interval=<interval>   Candle interval (for testing/live)
                            Default: 5m

    --max-candles=<n>       Maximum candles to process
                            Default: unlimited

    --data=<file>           Data file for backtest (CSV or Parquet)
                            Default: tables/data/raw/BTCUSDT_1m__30d.csv

Examples:
    # Backtest with Paroli
    python main.py --mode=backtest --player=paroli --data=BTC_1h.csv

    # Testing with Kraken Demo
    python main.py --mode=testing --player=paroli --symbol=BTC/USD --interval=5m

    # Live trading (REAL MONEY)
    python main.py --mode=live --player=paroli --symbol=BTC/USD --interval=5m
"""
    )


async def run_backtest(player_module, data_file, max_candles):
    """
    Run backtest mode.

    Note:
        Symbols are automatically normalized (USDT/USDC/BUSD → USD) for
        Gemini memory compatibility. Timeframe is forced to 1m to match
        existing Gemini memory trained on 1m data.
    """
    logger.info("🎰 Starting BACKTEST mode")

    # Create backtest data source
    if not data_file:
        data_file = getattr(config, "DATASET_PATH", "tables/data/raw/BTCUSDT_1m__30d.csv")

    logger.info(f"📁 Loading data from: {data_file}")

    if data_file.endswith(".parquet"):
        source = BacktestDataSource.from_parquet(data_file)
    else:
        # Force timeframe to 1m for Gemini memory compatibility
        # Gemini's memory was trained on 1m data, so we pretend any data is 1m
        source = BacktestDataSource.from_csv(
            data_file,
            normalize_symbol=True,  # USDT/USDC/BUSD → USD
            force_timeframe="1m",  # Force to 1m for memory compatibility
        )

    # Create session
    session = TradingSession(source, player_module, max_candles)

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


async def run_testing(player_module, symbol, interval, max_candles):
    """Run testing mode (demo exchange)."""
    logger.info("🎰 Starting TESTING mode (Demo Exchange)")

    # Default values
    if not symbol:
        symbol = "BTC/USD"
    if not interval:
        interval = "5m"

    logger.info(f"📊 Symbol: {symbol} | Interval: {interval}")

    # Create connector with resilience
    kraken = KrakenConnector(mode="testing")
    connector = ResilientConnector(
        connector=kraken,
        enable_state_recovery=True,
        state_recovery_config={
            "state_dir": "./state/testing",
            "auto_save_interval": 60.0,
        },
    )

    # Create testing data source
    source = TestingDataSource(connector, symbol, interval)

    # Create session
    session = TradingSession(source, player_module, max_candles)

    # Run
    await session.run()


async def run_live(player_module, symbol, interval, max_candles):
    """Run live mode (REAL MONEY)."""
    logger.warning("⚠️" * 20)
    logger.warning("⚠️ LIVE MODE - REAL MONEY ⚠️")
    logger.warning("⚠️" * 20)

    # Confirmation
    print("\n" + "=" * 60)
    print("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY")
    print("=" * 60)
    print(f"Symbol:   {symbol or 'BTC/USD'}")
    print(f"Interval: {interval or '5m'}")
    print(f"Player:   {player_module.__name__}")
    print("\nThis will execute REAL trades with REAL money.")
    print("=" * 60)

    confirm = input("\nType 'YES' to continue: ")
    if confirm != "YES":
        logger.info("❌ Live mode cancelled by user")
        return

    # Default values
    if not symbol:
        symbol = "BTC/USD"
    if not interval:
        interval = "5m"

    logger.info(f"📊 Symbol: {symbol} | Interval: {interval}")

    # Create connector with resilience
    kraken = KrakenConnector(mode="live")
    connector = ResilientConnector(
        connector=kraken,
        enable_state_recovery=True,
        state_recovery_config={
            "state_dir": "./state/live",
            "auto_save_interval": 30.0,  # More frequent for live
        },
    )

    # Create live data source
    source = LiveDataSource(connector, symbol, interval)

    # Create session
    session = TradingSession(source, player_module, max_candles)

    # Run
    await session.run()


async def main():
    """Main entry point."""
    # Parse arguments
    mode, player_name, symbol, interval, max_candles, data_file = parse_args()

    # Get player module
    if player_name not in PLAYERS:
        logger.error(f"❌ Unknown player: {player_name}")
        logger.info(f"Available players: {', '.join(PLAYERS.keys())}")
        return

    player_module = PLAYERS[player_name]

    # Print header
    print("\n" + "=" * 60)
    print("🎰 CASINO V2 - Trading Bot")
    print("=" * 60)
    print(f"Mode:   {mode.upper()}")
    print(f"Player: {player_name.upper()}")
    print("=" * 60 + "\n")

    # Run appropriate mode
    try:
        if mode == "backtest":
            await run_backtest(player_module, data_file, max_candles)
        elif mode == "testing":
            await run_testing(player_module, symbol, interval, max_candles)
        elif mode == "live":
            await run_live(player_module, symbol, interval, max_candles)
        else:
            logger.error(f"❌ Unknown mode: {mode}")
            print_help()

    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
