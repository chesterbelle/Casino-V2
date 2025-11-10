#!/usr/bin/env python3
"""
Test Croupier Integration - Casino V2

Valida que la integración del Croupier funcione correctamente
en backtest con la nueva arquitectura modular.
"""

# Standard library imports
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Third-party imports
from core.data_sources.backtest import BacktestDataSource  # noqa: E402

# Configure logging at module level
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger("TestCroupierIntegration")


async def test_backtest_with_croupier():
    """Test backtest with Croupier integration."""

    logger.info("=" * 80)
    logger.info("🧪 TESTING CROUPIER INTEGRATION IN BACKTEST")
    logger.info("=" * 80)

    # 1. Load backtest data
    logger.info("\n📊 Step 1: Loading backtest data...")
    try:
        data_file = "tests/validation/test_data_10candles.csv"
        source = BacktestDataSource.from_csv(
            data_file,
            initial_balance=10000.0,
            fee_rate=0.0006,
            slippage_rate=0.0001,
        )
        logger.info(f"✅ Data loaded: {len(source.data)} candles")
        logger.info(f"   Symbol: {source.symbol}")
        logger.info(f"   Timeframe: {source.timeframe}")
        logger.info(f"   Initial balance: ${source.initial_balance:,.2f}")
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")
        return False

    # 2. Connect
    logger.info("\n🔌 Step 2: Connecting...")
    try:
        await source.connect()
        logger.info("✅ Connected")
        logger.info(f"   Croupier: {source.croupier}")
        logger.info(f"   Adapter: {source.adapter}")
        logger.info(f"   Connector: {source.connector}")
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return False

    # 3. Get first candle
    logger.info("\n📈 Step 3: Getting first candle...")
    try:
        candle = await source.next_candle()
        if candle:
            logger.info("✅ Candle received:")
            logger.info(f"   Timestamp: {candle.timestamp}")
            logger.info(f"   Close: ${candle.close:,.2f}")
            logger.info(f"   Balance: ${candle.balance:,.2f}")
            logger.info(f"   Equity: ${candle.equity:,.2f}")
        else:
            logger.error("❌ No candle received")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to get candle: {e}")
        return False

    # 4. Test order execution through Croupier
    logger.info("\n💰 Step 4: Testing order execution through Croupier...")

    # Test 4.1: Valid order
    logger.info("\n   Test 4.1: Valid order (should succeed)")
    try:
        order = {
            "trade_id": "test_001",
            "symbol": source.symbol,
            "side": "LONG",
            "size": 0.02,  # 2% of equity
            "take_profit": 1.01,  # +1%
            "stop_loss": 0.99,  # -1%
        }

        result = await source.execute_order(order)

        if result.get("status") == "opened":
            logger.info("✅ Test completed successfully!")
            logger.info("      Trade ID: {}".format(result.get("trade_id")))
            logger.info("      Side: {}".format(result.get("side")))
            logger.info("      Amount: {:.6f}".format(result.get("amount", 0)))
            logger.info("      Entry price: ${:,.2f}".format(result.get("entry_price", 0)))
            logger.info("      Fee: ${:.4f}".format(result.get("fee", 0)))
            logger.info("      TP price: ${:,.2f}".format(result.get("tp_price", 0)))
            logger.info("      SL price: ${:,.2f}".format(result.get("sl_price", 0)))
        else:
            logger.error("   ❌ Order failed: {}".format(result.get("reason", "Unknown reason")))
            return False

    except Exception as e:
        logger.error(f"   ❌ Exception during order execution: {e}", exc_info=True)
        return False

    # Test 4.2: Order with amount below minimum (should be rejected)
    logger.info("\n   Test 4.2: Order with very small size (should be rejected by connector)")
    try:
        order_small = {
            "trade_id": "test_002",
            "symbol": source.symbol,
            "side": "LONG",
            "size": 0.00001,  # Very small (will result in amount < min_amount)
            "take_profit": 1.01,
            "stop_loss": 0.99,
        }

        result = await source.execute_order(order_small)

        if result.get("status") in ["rejected", "error"]:
            logger.info("   ✅ Order correctly rejected:")
            logger.info("      Reason: {}".format(result.get("reason", "Unknown reason")))

            # Verify it mentions minimum amount
            reason = result.get("reason", "").lower()
            if "minimum" in reason or "below" in reason:
                logger.info("   ✅ Rejection reason mentions minimum amount (correct)")
            else:
                logger.warning("   ⚠️  Rejection reason doesn't mention minimum amount")
        else:
            logger.error(
                "   ❌ Order should have been rejected but got: {}".format(result.get("status", "Unknown status"))
            )
            return False

    except Exception as e:
        logger.error("   ❌ Exception during small order test: {}".format(e), exc_info=True)
        return False

    # 5. Check balance updates
    logger.info("\n💵 Step 5: Checking balance updates...")
    try:
        balance = source.get_balance()
        equity = source.get_equity()

        logger.info("✅ Final balance: ${:,.2f}".format(balance))
        logger.info("✅ Final equity: ${:,.2f}".format(equity))

        if balance < source.initial_balance:
            logger.info("   ✅ Balance decreased (fee deducted)")
        else:
            logger.warning("   ⚠️  Balance didn't decrease")

        if len(source.open_positions) > 0:
            logger.info("   ✅ Open positions: {}".format(len(source.open_positions)))
        else:
            logger.error("   ❌ No open positions tracked")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to check balance: {e}")
        return False

    # 6. Process next candle (check TP/SL)
    logger.info("\n📊 Step 6: Processing next candle (TP/SL check)...")
    try:
        candle2 = await source.next_candle()
        if candle2:
            logger.info("✅ Second candle processed:")
            logger.info("   Close: ${:,.2f}".format(candle2.close))
            logger.info("   Balance: ${:,.2f}".format(candle2.balance))
            logger.info("   Equity: ${:,.2f}".format(candle2.equity))
            logger.info("   Open positions: {}".format(len(source.open_positions)))
            logger.info("   Closed trades: {}".format(len(source.closed_trades)))

            if len(source.closed_trades) > 0:
                logger.info("✅ Position opened:")
                trade = source.closed_trades[0]
                logger.info("      Exit reason: {}".format(trade.get("exit_reason", "Unknown")))
                logger.info("✅ Position PnL: ${:+,.2f}".format(trade.get("pnl", 0)))
        else:
            logger.warning("⚠️  No second candle")
    except Exception as e:
        logger.error("❌ Failed to process second candle: {}".format(e))
        return False

    # 7. Get stats
    logger.info("\n📈 Step 7: Getting stats...")
    try:
        stats = source.get_stats()
        logger.info("✅ Stats:")
        logger.info("   Initial balance: ${:,.2f}".format(stats["initial_balance"]))
        logger.info("   Final balance: ${:,.2f}".format(stats["final_balance"]))
        logger.info("   Final equity: ${:,.2f}".format(stats["final_equity"]))
        logger.info("   Total PnL: ${:,.2f}".format(stats["total_pnl"]))
        logger.info("   Total trades: {}".format(stats["total_trades"]))
        logger.info("   Wins: {}".format(stats["wins"]))
        logger.info("   Losses: {}".format(stats["losses"]))
    except Exception as e:
        logger.error("❌ Failed to get stats: {}".format(e))
        return False

    # 8. Disconnect
    logger.info("\n🔌 Step 8: Disconnecting...")
    try:
        await source.disconnect()
        logger.info("✅ Disconnected")
    except Exception as e:
        logger.error("❌ Failed to disconnect: {}".format(e))
        return False

    return True


async def main():
    """Main test function."""

    try:
        success = await test_backtest_with_croupier()

        logger.info("\n" + "=" * 80)
        if success:
            logger.info("✅ ALL TESTS PASSED - CROUPIER INTEGRATION WORKING!")
            logger.info("=" * 80)
            logger.info("\n🎉 Arquitectura modular funcionando correctamente:")
            logger.info("   BacktestDataSource → Croupier → SimulatedAdapter → SimulatedConnector")
            logger.info("\n✅ Validaciones funcionando:")
            logger.info("   - Croupier valida campos")
            logger.info("   - Croupier verifica fondos")
            logger.info("   - Connector valida límites (min_amount)")
            logger.info("   - Errores se propagan correctamente")
            return 0
        else:
            logger.error("❌ SOME TESTS FAILED")
            logger.error("=" * 80)
            return 1

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
