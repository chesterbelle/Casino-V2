#!/usr/bin/env python3
"""
Test Binance Connector - Casino V2

Valida que el conector de Binance funcione correctamente.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.binance import BinanceConnector  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TestBinanceConnector")


async def test_connection():
    """Test basic connection to Binance Testnet."""
    logger.info("=" * 60)
    logger.info("🧪 Testing Binance Connector")
    logger.info("=" * 60)

    connector = None
    try:
        # Initialize connector (testnet mode)
        logger.info("📝 Initializing Binance connector (testnet)...")
        connector = BinanceConnector(mode="testnet")

        # Connect
        logger.info("🔌 Connecting to Binance Testnet...")
        await connector.connect()

        # Test balance fetch
        logger.info("💰 Fetching balance...")
        balance = await connector.fetch_balance()
        usdt_balance = balance.get("total", {}).get("USDT", 0)
        logger.info(f"✅ Balance: {usdt_balance} USDT")

        # Test ticker fetch
        logger.info("📊 Fetching ticker for BTC/USD:USD...")
        ticker = await connector.fetch_ticker("BTC/USD:USD")
        last_price = ticker.get("last", 0)
        logger.info(f"✅ BTC Price: ${last_price:,.2f}")

        # Test positions fetch
        logger.info("📊 Fetching positions...")
        positions = await connector.fetch_positions()
        logger.info(f"✅ Open positions: {len(positions)}")

        # Test symbol normalization
        logger.info("🔄 Testing symbol normalization...")
        bot_symbol = "BTC/USD:USD"
        binance_symbol = connector.normalize_symbol(bot_symbol)
        denormalized = connector.denormalize_symbol("BTCUSDT")
        logger.info(f"✅ Bot format: {bot_symbol} → Binance format: {binance_symbol}")
        logger.info(f"✅ Binance format: BTCUSDT → Bot format: {denormalized}")

        logger.info("=" * 60)
        logger.info("✅ All tests passed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

    finally:
        if connector:
            logger.info("🔌 Closing connection...")
            await connector.close()

    return True


async def test_order_creation_dry_run():
    """Test order creation logic (without actually placing orders)."""
    logger.info("=" * 60)
    logger.info("🧪 Testing Order Creation Logic (Dry Run)")
    logger.info("=" * 60)

    connector = None
    try:
        # Initialize connector (testnet mode)
        connector = BinanceConnector(mode="testnet")
        await connector.connect()

        # Get current price
        ticker = await connector.fetch_ticker("BTC/USD:USD")
        current_price = ticker.get("last", 0)
        logger.info(f"📊 Current BTC price: ${current_price:,.2f}")

        # Calculate TP/SL prices
        tp_price = current_price * 1.02  # +2%
        sl_price = current_price * 0.98  # -2%

        print("")
        print("📊 Ticker:")
        print(f"  Symbol: {ticker.get('symbol')}")
        print(f"  Last: {ticker.get('last')}")
        print(f"  Bid: {ticker.get('bid')}")
        print(f"  Ask: {ticker.get('ask')}")
        logger.info(f"   TP: ${tp_price:,.2f} (+2%)")
        logger.info(f"   SL: ${sl_price:,.2f} (-2%)")

        logger.info("✅ Order creation logic validated (dry run)")

        # Note: To actually test order creation, uncomment below:
        # order = await connector.create_order_with_tpsl(
        #     symbol="BTC/USD:USD",
        #     side="buy",
        #     amount=0.001,
        #     order_type="market",
        #     tp_price=tp_price,
        #     sl_price=sl_price,
        # )
        # logger.info(f"✅ Order created: {order['id']}")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

    finally:
        if connector:
            await connector.close()

    return True


async def main():
    """Run all tests."""
    logger.info("🚀 Starting Binance Connector Tests")
    logger.info("")

    # Test 1: Connection
    success1 = await test_connection()

    logger.info("")

    # Test 2: Order creation (dry run)
    success2 = await test_order_creation_dry_run()

    logger.info("")
    if success1 and success2:
        logger.info("✅ All tests completed successfully!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
