import asyncio
import logging
import sys

# Add project root to path
sys.path.append("/home/chesterbelle/Casino-V2")

from core.data_sources.backtest import BacktestDataSource  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Verification")


async def run_verification():
    csv_path = "/home/chesterbelle/Casino-V2/data/validation/historical_ltc_30d_1m.csv"

    logger.info(f"🚀 Starting verification with {csv_path}")

    # 1. Initialize DataSource
    source = BacktestDataSource.from_csv(csv_path, initial_balance=1000.0, normalize_symbol=True)

    await source.connect()

    logger.info(f"Initial Balance: {source.get_balance()}")

    # 2. Process some candles
    for i in range(5):
        candle = await source.next_candle()
        logger.info(f"🕯️ Candle {i}: {candle.close} | Time: {candle.timestamp}")

    # 3. Place a Strategy Order (LONG)
    logger.info("🛒 Placing Strategy Order (LONG)...")
    order_payload = {
        "symbol": source.symbol,
        "side": "LONG",
        "size": 0.1,  # 10% of equity
        "take_profit": 0.01,  # +1%
        "stop_loss": 0.01,  # -1%
    }

    # Execute via Croupier
    result = await source.execute_order(order_payload)
    logger.info(f"✅ Order Result: {result}")

    logger.info(f"Balance after order: {source.get_balance()}")

    # 4. Process more candles to see PnL update and TP hit
    logger.info("⏳ Running loop to hit TP...")
    hit = False

    # Calculate expected TP price for logging
    entry_price = result.get("entry_price", 0)
    tp_price = entry_price * 1.01
    logger.info(f"🎯 Target TP Price: {tp_price:.2f}")

    for i in range(100):
        candle = await source.next_candle()
        if not candle:
            break

        # Check if we have open positions
        positions = await source.connector.fetch_positions()

        if not positions and i > 0:
            # Position closed (TP hit)
            logger.info(f"🎉 Position closed at candle {i} | High: {candle.high}")
            hit = True
            break

        if i % 10 == 0:
            equity = source.get_equity()
            logger.info(f"Candle {i}: Close {candle.close} | Equity: {equity:.2f}")

    if not hit:
        logger.warning("⚠️ TP not hit in 100 candles")

    # 7. Get Stats
    stats = await source.get_stats()
    logger.info(f"📊 Final Stats: {stats}")

    await source.disconnect()


if __name__ == "__main__":
    asyncio.run(run_verification())
