"""
Casino V2 - Main Entry Point

Nueva arquitectura unificada:
- Una sola TradingSession para todos los modos
- Data sources intercambiables (backtest, testing, live)
- Pipeline limpio y testeable
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import exchange as exchange_config
from config import system
from core.data_sources.testing import TestingDataSource
from core.trading import TradingSession
from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors import BybitConnector, KrakenConnector, ResilientConnector
from players import kelly_player, paroli_player

# Setup logging
logging.basicConfig(
    level=getattr(logging, system.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

# Add file logging for debugging
log_filename = f"logs/main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
Path("logs").mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
file_handler.setFormatter(file_formatter)

# Add file handler to root logger
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.DEBUG)

logger = logging.getLogger("Casino-V2")
logger.info(f"📝 Logging to file: {log_filename}")

# Available players
PLAYERS = {
    "paroli": paroli_player,
    "kelly": kelly_player,
}


def parse_args():
    """Parse command line arguments."""
    mode = "backtest"
    player_name = "paroli"
    symbol = None
    interval = None
    max_candles = None
    data_file = None
    initial_balance = None  # Must be provided explicitly
    exchange = None

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
        elif arg.startswith("--initial-balance="):
            initial_balance = float(arg.split("=")[1].rstrip("~"))
        elif arg.startswith("--exchange="):
            exchange = arg.split("=")[1].lower()
        elif arg in ["--help", "-h"]:
            print_help()
            sys.exit(0)

    return mode, player_name, symbol, interval, max_candles, data_file, initial_balance, exchange


def print_help():
    """Print help message."""
    logger.info(
        """
Casino V2 - Trading Bot

Usage:
    python main.py [options]

Options:
    --mode=MODE              Trading mode: backtest, demo, live (default: backtest)
    --player=PLAYER          Player strategy: paroli, kelly, fixed
                            Default: paroli

    --symbol=SYMBOL          Trading pair (for testing/live)
                            Default: BTC/USD

    --interval=INTERVAL      Candle interval (for testing/live)
                            Default: 5m

    --max-candles=N          Maximum candles to process
                            Default: unlimited

    --data=FILE              Data file path (for backtest mode)
                                Default: tables/data/raw/BTCUSDT_1m__30d.csv
    --initial-balance=AMOUNT Initial balance in USD (REQUIRED for backtest ONLY)
                                ⚠️ Demo/Live modes: IGNORED (always uses exchange's real balance)
                                🎯 Backtest mode: MANDATORY (no default to avoid hardcoded values)

Examples:
    # Backtest with Paroli (initial-balance REQUIRED)
    python main.py --mode=backtest --player=paroli --data=BTC_1h.csv --initial-balance=10000.0

    # Demo with Bybit Demo Trading
    python main.py --mode=demo --player=paroli --symbol=BTC/USDT:USDT --interval=1m

    # Live trading (REAL MONEY)
    python main.py --mode=live --player=paroli --symbol=BTC/USD --interval=5m
"""
    )


def save_results_json(mode: str, stats: dict, player_name: str, symbol: str = None, timeframe: str = None):
    """
    Save session results to JSON file for validation.

    Args:
        mode: Trading mode (backtest, demo, live)
        stats: Statistics dictionary from data source
        player_name: Name of the player strategy
        symbol: Trading symbol (optional)
        timeframe: Candle timeframe (optional)
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = logs_dir / f"{mode}_{timestamp}.json"

        # Prepare data
        data = {
            "mode": mode,
            "player": player_name,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol or "BTC/USD",
            "timeframe": timeframe or "1m",
            "initial_balance": stats.get("initial_balance", 0),
            "final_balance": stats.get("final_balance", 0),
            "final_equity": stats.get("final_equity", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "total_trades": stats.get("total_trades", 0),
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "win_rate": stats.get("win_rate", 0),
            "open_positions": stats.get("open_positions", 0),
            "orders_rejected": stats.get("orders_rejected", 0),
            "orders_error": stats.get("orders_error", 0),
            "rejection_reasons": stats.get("rejection_reasons", []),
            "candle_timestamps": stats.get("candle_timestamps", []),
            "closed_trades": stats.get("closed_trades", []),
        }

        # Save to file
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"📝 Results saved to: {filename}")
        return filename

    except Exception as e:
        logger.error(f"❌ Failed to save results JSON: {e}")
        return None


async def _force_close_open_positions_and_orders(connector, croupier, symbol: str):
    try:
        logger.info(f"🧹 Force closing positions and orders for {symbol}")

        # Step 1: PRIMERO cerrar todas las posiciones abiertas via Croupier
        # (esto asegura que se contabilicen como trades cerrados)
        try:
            open_positions = croupier.get_open_positions()
            logger.info(f"📊 Found {len(open_positions)} open positions in Croupier")

            closed_count = 0
            for position in open_positions[:]:  # Copy to avoid modification during iteration
                try:
                    trade_id = position.trade_id if hasattr(position, "trade_id") else position.get("trade_id")
                    pos_symbol = position.symbol if hasattr(position, "symbol") else position.get("symbol")

                    # Check if this position matches our symbol
                    if pos_symbol != symbol:
                        logger.debug(f"⏭️ Symbol mismatch: {pos_symbol} != {symbol}")
                        continue

                    logger.info(f"🔒 Closing position via Croupier: {trade_id} for {pos_symbol}")

                    # Close via Croupier (which handles TP/SL cancellation and accounting)
                    await croupier.close_position(trade_id)

                    logger.info(f"✅ Force-closed position {trade_id} via Croupier")
                    closed_count += 1

                except Exception as e:
                    logger.warning(f"⚠️ Error force-closing position via Croupier: {e}")
                    # Continue with other positions even if one fails

            if closed_count > 0:
                logger.info(f"✅ Closed {closed_count} position(s) via Croupier")
            else:
                logger.info("ℹ️ No positions to close")

        except Exception as e:
            logger.warning(f"⚠️ Error during Croupier position closure: {e}")

        # Step 2: DESPUÉS cancelar todas las órdenes abiertas
        try:
            open_orders = await connector.fetch_open_orders(symbol)
            logger.info(f"📋 Found {len(open_orders)} open orders")
        except Exception as e:
            logger.warning(f"⚠️ Error fetching open orders: {e}")
            open_orders = []

        if open_orders:
            for o in open_orders:
                try:
                    order_id = o.get("id")
                    logger.info(f"❌ Cancelling order {order_id}...")
                    await connector.cancel_order(order_id, symbol)
                    logger.info(f"✅ Cancelled order {order_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to cancel order {o.get('id')}: {e}")

        # Step 3: Sync croupier balance with exchange after closures
        try:
            balance = await connector.fetch_balance()
            base = getattr(exchange_config, "BASE_CURRENCY", "USDT")
            new_balance = balance.get("free", {}).get(base, 0.0)
            if new_balance:
                try:
                    croupier.balance_manager.set_balance(new_balance)
                    logger.info(f"💰 Balance synced from exchange: ${new_balance:,.2f}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not sync croupier balance: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error fetching final balance: {e}")

    except Exception as e:
        logger.warning(f"⚠️ Force close cleanup failed: {e}")


def _print_human_summary(mode: str, stats: dict, session_stats: dict):
    def fmt(n):
        try:
            return f"{float(n):,.2f}".replace(",", "_").replace("_", ",")
        except Exception:
            return str(n)

    initial_balance = float(stats.get("initial_balance", 0.0))
    final_balance = float(stats.get("final_balance", stats.get("final_equity", 0.0)))
    total_pnl = float(stats.get("total_pnl", stats.get("net_pnl", final_balance - initial_balance)))
    pnl_pct = (total_pnl / initial_balance * 100.0) if initial_balance else 0.0

    candles = int(session_stats.get("candles_processed", 0))
    bets = int(session_stats.get("bets", 0))
    ghosts = int(session_stats.get("ghosts", 0))
    skips = int(session_stats.get("skips", 0))

    wins = int(stats.get("wins", session_stats.get("wins", 0)))
    losses = int(stats.get("losses", session_stats.get("losses", 0)))

    # Prefer backtest win_rate when present; otherwise compute from bets
    if "win_rate" in stats and stats.get("win_rate") not in (None, 0):
        win_rate_bet = float(stats.get("win_rate", 0.0)) * 100.0
    else:
        denom = bets if bets else (wins + losses)
        win_rate_bet = (wins / denom * 100.0) if denom else 0.0

    total_fees = stats.get("total_fees")
    funding_total = stats.get("funding_total")  # may be None if not tracked
    liquidations = stats.get("liquidations", 0)

    logger.info("-" * 59)
    logger.info(f"   Balance inicial       : {fmt(initial_balance)}")
    logger.info(f"   Velas procesadas      : {candles}")
    logger.info(f"   Trades BET            : {bets}")
    logger.info(f"   Trades GHOST          : {ghosts}")
    logger.info(f"   Trades SKIP           : {skips}")
    logger.info(f"   Wins / Losses         : {wins} / {losses}")
    logger.info(f"   WinRate (BET)         : {win_rate_bet:.2f}%")
    logger.info(f"   Comisiones totales    : {fmt(total_fees) if total_fees is not None else 'N/A'}")
    logger.info(f"   Funding total         : {fmt(funding_total) if funding_total is not None else 'N/A'}")
    logger.info(f"   Liquidaciones         : {liquidations}")
    logger.info(f"   Balance final         : {fmt(final_balance)}")
    logger.info(
        f"   PnL Total             : {('+' if total_pnl >= 0 else '')}{fmt(total_pnl)} ({('+' if pnl_pct >= 0 else '')}{pnl_pct:.2f}%)"
    )
    logger.info("")

    # Extras for demo/testing to clarify rejections/errors
    if mode == "demo":
        orders_rejected = int(stats.get("orders_rejected", session_stats.get("orders_rejected", 0)))
        orders_error = int(stats.get("orders_error", session_stats.get("orders_error", 0)))
        rejection_reasons = stats.get("rejection_reasons", []) or []
        rejected_due_to_open_pos = sum(
            1 for r in rejection_reasons if isinstance(r, dict) and "Position already open" in str(r.get("reason", ""))
        )
        # Calculate other rejection reasons
        other_rejections = max(0, orders_rejected - rejected_due_to_open_pos)
        # Calculate total order attempts
        order_attempts = session_stats.get("executed_trades", 0) + orders_rejected + orders_error
        _ = order_attempts  # Prevent unused variable warning
        logger.info(
            f"   Rechazos              : {orders_rejected} (pos. existente: {rejected_due_to_open_pos}, otros: {other_rejections})"
        )
        logger.info(f"   Errores de orden      : {orders_error}")
        logger.info("-" * 59)
    else:
        logger.info("-" * 59)


async def run_backtest(player_module, data_file, max_candles, initial_balance=None):
    """
    Run backtest mode.

    Args:
        player_module: Player strategy module (paroli, kelly, etc.)
        data_file: Path to CSV/Parquet file with historical data
        max_candles: Maximum number of candles to process (None = all)
        initial_balance: Starting balance in USD (REQUIRED - no default)

    Raises:
        ValueError: If initial_balance is None (must be provided explicitly)

    Note:
        - Symbols are automatically normalized (USDT/USDC/BUSD → USD) for
          Gemini memory compatibility
        - Timeframe is forced to 1m to match existing Gemini memory
        - initial_balance MUST be provided via --initial-balance parameter
          to avoid hardcoded defaults and ensure explicit balance control
    """
    logger.info("🎰 Starting BACKTEST mode")
    from core.data_sources.backtest import BacktestDataSource

    # Create backtest data source
    if not data_file:
        data_file = getattr(system, "DATASET_PATH", "tables/data/raw/BTCUSDT_1m__30d.csv")

    logger.info(f"📁 Loading data from: {data_file}")

    # Validate that initial_balance is provided for backtest mode
    if initial_balance is None:
        logger.error("❌ --initial-balance parameter is required for backtest mode")
        logger.error("   Example: python main.py --mode=backtest --initial-balance=10000.0 --data=data.csv")
        raise ValueError("initial_balance parameter is required for backtest mode")

    logger.info(f"💰 Using initial balance: ${initial_balance:,.2f}")

    if data_file.endswith(".parquet"):
        source = BacktestDataSource.from_parquet(data_file, initial_balance=initial_balance)
    else:
        # Force timeframe to 1m for Gemini memory compatibility
        # Gemini's memory was trained on 1m data, so we pretend any data is 1m
        source = BacktestDataSource.from_csv(
            data_file,
            normalize_symbol=True,  # USDT/USDC/BUSD → USD
            force_timeframe="1m",  # Force to 1m for memory compatibility
            initial_balance=initial_balance,
        )

    # Create session
    session = TradingSession(source, player_module, max_candles)

    # Run
    session_stats = None
    try:
        session_stats = await session.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("⚠️ Backtest interrupted by user - finalizing stats and saving results...")

        # Try to collect best-effort stats from source and session
        try:
            stats = source.get_stats()
        except Exception:
            stats = {}

        try:
            session_stats = session.get_stats().summary() if hasattr(session, "get_stats") else {}
        except Exception:
            session_stats = {}

        # Merge session stats (orders_rejected, orders_error, rejection_reasons)
        stats.update(
            {
                "orders_rejected": session_stats.get("orders_rejected", 0),
                "orders_error": session_stats.get("orders_error", 0),
                "rejection_reasons": session_stats.get("rejection_reasons", []),
            }
        )

        # Ensure we save a results JSON so the run is recorded for validation
        try:
            save_results_json(
                mode="backtest",
                stats=stats,
                player_name=player_module.__name__.split(".")[-1],
                symbol=source.symbol,
                timeframe=source.timeframe,
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save interrupted backtest results: {e}")

        # Re-raise to allow upper-level handlers to log/exit as before
        raise

    # Print stats - combine session stats with data source stats
    stats = source.get_stats()

    # Merge session stats (orders_rejected, orders_error, rejection_reasons)
    stats.update(
        {
            "orders_rejected": session_stats.get("orders_rejected", 0),
            "orders_error": session_stats.get("orders_error", 0),
            "rejection_reasons": session_stats.get("rejection_reasons", []),
        }
    )
    # Unified human-readable summary
    _print_human_summary("backtest", stats, session_stats)

    # Save results to JSON for validation
    save_results_json(
        mode="backtest",
        stats=stats,
        player_name=player_module.__name__.split(".")[-1],
        symbol=source.symbol,
        timeframe=source.timeframe,
    )


async def run_demo(player_module, symbol, interval, max_candles, exchange=None, initial_balance=None):
    """
    Run demo mode (Exchange Demo Trading with real prices).

    Args:
        player_module: Player strategy module
        symbol: Trading symbol (optional, uses exchange defaults)
        interval: Candle interval (optional, uses exchange defaults)
        max_candles: Maximum candles to process (None = unlimited)
        exchange: Exchange name (optional, uses config default)
        initial_balance: IGNORED - Demo mode ALWAYS uses exchange's real balance

    Note:
        - Demo mode ALWAYS uses the exchange's real balance (no override allowed)
        - Uses exchange testnet/demo accounts with real price feeds
        - The initial_balance parameter is ignored for safety
    """

    # SAFETY: Demo mode NEVER uses custom initial_balance
    if initial_balance is not None:
        logger.warning(f"⚠️ initial_balance={initial_balance} IGNORED in demo mode")
        logger.warning("   Demo mode ALWAYS uses exchange's real balance for safety")
    # Use exchange from argument or fall back to config
    exchange_name = exchange.upper() if exchange else exchange_config.EXCHANGE
    logger.info(f"🎰 Starting DEMO mode (Exchange: {exchange_name})")

    # Default values based on exchange
    if not symbol:
        if exchange_name == "BYBIT":
            symbol = exchange_config.BYBIT_DEFAULT_SYMBOL
        elif exchange_name == "KRAKEN":
            symbol = "BTC/USD"
        elif exchange_name == "BINANCE":
            symbol = "LTC/USD:USD"
        else:
            symbol = exchange_config.SYMBOL

    if not interval:
        if exchange_name == "BYBIT":
            interval = exchange_config.BYBIT_DEFAULT_INTERVAL
        elif exchange_name == "KRAKEN":
            interval = "5m"
        elif exchange_name == "BINANCE":
            interval = "1m"
        else:
            interval = exchange_config.TIMEFRAME

    logger.info(f"📊 Symbol: {symbol} | Interval: {interval}")

    # Create connector based on exchange
    if exchange_name == "BYBIT":
        base_connector = BybitConnector(mode="demo")
    elif exchange_name == "KRAKEN":
        base_connector = KrakenConnector(mode="demo")
    elif exchange_name == "BINANCE":
        from exchanges.connectors.binance import BinanceConnector

        base_connector = BinanceConnector(mode="demo", enable_websocket=True)
    else:
        raise ValueError(f"Exchange {exchange_name} not supported in demo mode")

    connector = ResilientConnector(
        connector=base_connector,
        enable_state_recovery=True,
        state_recovery_config={
            "state_dir": "./state/testing",
            "auto_save_interval": 60.0,
        },
    )

    # Conectar al exchange ANTES de crear los componentes dependientes
    await connector.connect()

    # --- Nueva Arquitectura: Croupier como Cerebro ---
    # 1. Obtener balance inicial REAL del exchange
    logger.info("Obteniendo balance inicial real del exchange...")
    balance_data = await connector.fetch_balance()
    # Extraer el balance de la moneda base (ej. USDT)
    # Esta lógica puede necesitar ajuste según la respuesta del conector
    initial_balance_real = balance_data.get("free", {}).get(exchange_config.BASE_CURRENCY, 0.0)
    if initial_balance_real == 0.0:
        raise RuntimeError(f"No se pudo obtener un balance inicial válido para {exchange_config.BASE_CURRENCY}")
    logger.info(f"Balance inicial real obtenido: ${initial_balance_real:,.2f}")

    # 2. Crear el Adapter (sin estado)
    adapter = CCXTAdapter(connector, symbol, interval)

    # 3. Crear el Croupier (con estado)
    croupier = Croupier(exchange_adapter=adapter, initial_balance=initial_balance_real)

    # 4. CLEANUP: Cerrar cualquier posición abierta del trading anterior
    logger.info("🧹 Cleaning up any open positions from previous sessions...")
    try:
        await _force_close_open_positions_and_orders(connector, croupier, symbol)
        logger.info("✅ Cleanup completed")
    except Exception as e:
        logger.warning(f"⚠️ Cleanup error (continuing anyway): {e}")

    # 5. Crear el DataSource (que usa el Croupier para ejecutar órdenes)
    source = TestingDataSource(croupier, symbol, interval)

    # Create session
    session = TradingSession(source, player_module, max_candles)

    # Run
    try:
        session_stats = await session.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("⚠️ Demo interrupted by user - finalizing stats and will save results after cleanup...")
        # let finally run to perform cleanup, then we'll re-raise after saving
        interrupted = True
        session_stats = None
    else:
        interrupted = False
    finally:

        # End-of-session forced cleanup for demo: cancel TP/SL and close open positions
        logger.info("🧹 Final cleanup: Closing any remaining open positions and orders...")
        try:
            await _force_close_open_positions_and_orders(connector, croupier, symbol)
            logger.info("✅ Final cleanup completed")

            # Additional cleanup: Cancel any remaining orphaned orders
            logger.info("🧹 Cleanup: Cancelling any remaining orphaned TP/SL orders...")
            try:
                open_orders = await connector.fetch_open_orders(symbol)
                if open_orders:
                    logger.info(f"📋 Found {len(open_orders)} remaining orders to cancel")
                    for order in open_orders:
                        try:
                            order_id = order.get("id")
                            order_type = order.get("type", "unknown")
                            logger.info(f"❌ Cancelling orphaned {order_type} order {order_id}...")
                            await connector.cancel_order(order_id, symbol)
                            logger.info(f"✅ Cancelled orphaned order {order_id}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to cancel orphaned order: {e}")
                else:
                    logger.info("ℹ️ No orphaned orders found")
            except Exception as e:
                logger.warning(f"⚠️ Error during orphaned orders cleanup: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Demo end-session cleanup error: {e}")

        try:
            # Close the main connector
            await connector.close()
            logger.info("🔌 Connector closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing connector: {e}")

        # Small drain to let aiohttp/ccxt settle
        try:
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # Show final stats - combine session stats with data source stats
    stats = await source.get_stats()

    # Ensure we have a session_stats dict (best-effort if interrupted)
    if session_stats is None:
        try:
            session_stats = session.get_stats().summary() if hasattr(session, "get_stats") else {}
        except Exception:
            session_stats = {}

    # Merge session stats (orders_rejected, orders_error, rejection_reasons)
    stats.update(
        {
            "orders_rejected": session_stats.get("orders_rejected", 0),
            "orders_error": session_stats.get("orders_error", 0),
            "rejection_reasons": session_stats.get("rejection_reasons", []),
        }
    )

    # Derived metrics for clearer reporting in demo mode
    _ = int(stats.get("total_trades", 0))  # executed_trades
    # Calculate rejection reasons for the summary
    _ = stats.get("orders_rejected", 0)  # orders_rejected
    _ = stats.get("orders_error", 0)  # orders_error
    rejection_reasons = stats.get("rejection_reasons", []) or []
    _ = sum(  # rejected_due_to_open_pos
        1 for r in rejection_reasons if isinstance(r, dict) and "Position already open" in str(r.get("reason", ""))
    )
    _ = stats.get("executed_trades", 0)  # executed_trades

    # Unified human-readable summary (demo/testing)
    _print_human_summary("demo", stats, session_stats)

    # Save results to JSON for validation
    save_results_json(
        mode="demo", stats=stats, player_name=player_module.__name__.split(".")[-1], symbol=symbol, timeframe=interval
    )

    if interrupted:
        # If the demo was interrupted by user, re-raise to let outer handlers/loggers know
        raise KeyboardInterrupt()


async def run_live(player_module, symbol, interval, max_candles, initial_balance=None):
    """
    Run live mode (REAL MONEY).

    Args:
        player_module: Player strategy module
        symbol: Trading symbol (optional, defaults to BTC/USD)
        interval: Candle interval (optional, defaults to 5m)
        max_candles: Maximum candles to process (None = unlimited)
        initial_balance: IGNORED - Live mode ALWAYS uses exchange's real balance

    Note:
        - Live mode ALWAYS uses the exchange's real balance (no override allowed)
        - Uses real exchange accounts with REAL MONEY
        - The initial_balance parameter is ignored for safety
    """

    # SAFETY: Live mode NEVER uses custom initial_balance
    if initial_balance is not None:
        logger.warning(f"⚠️ initial_balance={initial_balance} IGNORED in live mode")
        logger.warning("   Live mode ALWAYS uses exchange's real balance for safety")
    logger.warning("⚠️" * 20)
    logger.warning("⚠️ LIVE MODE - REAL MONEY ⚠️")
    logger.warning("⚠️" * 20)

    # Confirmation
    logger.warning("\n" + "=" * 60)
    logger.warning("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY")
    logger.warning("=" * 60)
    logger.warning(f"Symbol:   {symbol or 'BTC/USD'}")
    logger.warning(f"Interval: {interval or '5m'}")
    logger.warning(f"Player:   {player_module.__name__}")
    logger.warning("\nThis will execute REAL trades with REAL money.")
    logger.warning("=" * 60)

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
    from core.data_sources.live import LiveDataSource

    source = LiveDataSource(connector, symbol, interval)

    # Create session
    session = TradingSession(source, player_module, max_candles)

    # Run
    try:
        await session.run()
    finally:
        # Cleanup: Close data source connection
        try:
            await source.disconnect()
            logger.info("🔌 Data source disconnected")
        except Exception as e:
            logger.warning(f"⚠️ Error closing data source: {e}")


async def main():
    """Main entry point."""
    # Parse arguments
    mode, player_name, symbol, interval, max_candles, data_file, initial_balance, exchange = parse_args()

    # Get player module
    if player_name not in PLAYERS:
        logger.error(f"❌ Unknown player: {player_name}")
        logger.info(f"Available players: {', '.join(PLAYERS.keys())}")
        return

    player_module = PLAYERS[player_name]

    # Print header
    logger.info("\n" + "=" * 60)
    logger.info("🎰 CASINO V2 - Trading Bot")
    logger.info("=" * 60)
    logger.info(f"Mode:   {mode.upper()}")
    logger.info(f"Player: {player_name.upper()}")
    logger.info("=" * 60 + "\n")

    # Run mode
    try:
        if mode == "backtest":
            await run_backtest(player_module, data_file, max_candles, initial_balance)
        elif mode == "demo":
            await run_demo(player_module, symbol, interval, max_candles, exchange, initial_balance)
        elif mode == "live":
            await run_live(player_module, symbol, interval, max_candles, initial_balance)
        else:
            logger.error(f"❌ Unknown mode: {mode}")
            print_help()

    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
