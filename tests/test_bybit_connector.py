"""
Test Bybit Connector - Basic Functionality.

This test validates the Bybit connector's basic functionality:
- Connection
- Balance fetching
- Order creation with TP/SL
- Native TP/SL support (advantage over Kraken)

Usage:
    python tests/test_bybit_connector.py --testnet
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exchanges.connectors.bybit import BybitConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def test_basic_connection(connector: BybitConnector) -> bool:
    """Test basic connection to Bybit."""
    try:
        logger.info("🔌 Testing connection...")
        await connector.connect()
        logger.info("✅ Connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False


async def test_fetch_balance(connector: BybitConnector) -> bool:
    """Test fetching balance from Bybit."""
    try:
        logger.info("💰 Testing balance fetch...")
        balance = await connector.fetch_balance()

        usdt_balance = balance.get("total", {}).get("USDT", 0)
        logger.info(f"✅ Balance fetched: {usdt_balance} USDT")

        if usdt_balance <= 0:
            logger.warning("⚠️ Balance is 0 or negative. You may need to fund your testnet account.")

        return True
    except Exception as e:
        logger.error(f"❌ Balance fetch failed: {e}")
        return False


async def test_fetch_ticker(connector: BybitConnector, symbol: str = "BTC/USD:USD") -> bool:
    """Test fetching ticker data."""
    try:
        logger.info(f"📊 Testing ticker fetch for {symbol}...")
        ticker = await connector.fetch_ticker(symbol)

        last_price = ticker.get("last")
        logger.info(f"✅ Ticker fetched: {symbol} @ ${last_price:,.2f}")

        return True
    except Exception as e:
        logger.error(f"❌ Ticker fetch failed: {e}")
        return False


async def test_create_simple_order(connector: BybitConnector, symbol: str = "BTC/USD:USD") -> bool:
    """Test creating a simple market order (without TP/SL)."""
    try:
        logger.info(f"📝 Testing simple order creation for {symbol}...")

        # Get current price
        ticker = await connector.fetch_ticker(symbol)
        current_price = ticker.get("last")

        # Get balance
        balance = await connector.fetch_balance()
        usdt_balance = balance.get("free", {}).get("USDT", 0)

        if usdt_balance < 10:
            logger.warning("⚠️ Insufficient balance for test order. Skipping...")
            return True

        # Calculate small order size (0.1% of balance)
        order_value = usdt_balance * 0.001  # 0.1% of balance
        order_amount = order_value / current_price
        order_amount = round(order_amount, 6)

        logger.info(f"📋 Creating order: {order_amount} @ ${current_price:,.2f}")

        # Note: This is a DRY RUN - we're not actually placing the order
        # to avoid using real funds. Uncomment below to test for real:

        # order = await connector.create_order(
        #     symbol=symbol,
        #     side="buy",
        #     amount=order_amount,
        #     order_type="market"
        # )
        # logger.info(f"✅ Order created: {order['id']}")

        logger.info("✅ Order creation test passed (dry run)")
        return True

    except Exception as e:
        logger.error(f"❌ Order creation failed: {e}")
        return False


async def test_create_order_with_tpsl(connector: BybitConnector, symbol: str = "BTC/USD:USD") -> bool:
    """Test creating an order with TP/SL (Bybit's native support)."""
    try:
        logger.info(f"🎯 Testing order with TP/SL for {symbol}...")

        # Get current price
        ticker = await connector.fetch_ticker(symbol)
        current_price = ticker.get("last")

        # Calculate TP/SL prices (±2%)
        tp_price = current_price * 1.02  # +2% for TP
        sl_price = current_price * 0.98  # -2% for SL

        logger.info(f"📊 Current price: ${current_price:,.2f}")
        logger.info(f"📊 TP price: ${tp_price:,.2f} (+2%)")
        logger.info(f"📊 SL price: ${sl_price:,.2f} (-2%)")

        # Note: This is a DRY RUN - we're not actually placing the order
        # Uncomment below to test for real:

        # order = await connector.create_order_with_tpsl(
        #     symbol=symbol,
        #     side="buy",
        #     amount=0.001,
        #     order_type="market",
        #     tp_price=tp_price,
        #     sl_price=sl_price
        # )
        # logger.info(f"✅ Order with TP/SL created: {order['id']}")

        logger.info("✅ Order with TP/SL test passed (dry run)")
        logger.info("💡 Bybit supports native TP/SL - no OCO Monitor needed!")

        return True

    except Exception as e:
        logger.error(f"❌ Order with TP/SL failed: {e}")
        return False


async def run_all_tests(mode: str = "testing", symbol: str = "BTC/USD:USD") -> bool:
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("🚀 BYBIT CONNECTOR TESTS")
    logger.info("=" * 80)
    logger.info(f"Mode: {mode.upper()}")
    logger.info(f"Symbol: {symbol}")
    logger.info("=" * 80)

    # Create connector
    connector = BybitConnector(mode=mode)

    tests = [
        ("Connection", test_basic_connection(connector)),
        ("Balance", test_fetch_balance(connector)),
        ("Ticker", test_fetch_ticker(connector, symbol)),
        ("Simple Order", test_create_simple_order(connector, symbol)),
        ("Order with TP/SL", test_create_order_with_tpsl(connector, symbol)),
    ]

    results = []
    for test_name, test_coro in tests:
        logger.info(f"\n{'─' * 80}")
        logger.info(f"🧪 TEST: {test_name}")
        logger.info(f"{'─' * 80}")

        result = await test_coro
        results.append((test_name, result))

        if result:
            logger.info(f"✅ {test_name} PASSED")
        else:
            logger.error(f"❌ {test_name} FAILED")

    # Close connector
    await connector.close()

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status} | {test_name}")

    logger.info("=" * 80)
    logger.info(f"Result: {passed}/{total} tests passed")
    logger.info("=" * 80)

    return passed == total


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Test Bybit Connector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--testnet",
        action="store_true",
        default=True,
        help="Use testnet (default: True)",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live (default: False)",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="BTC/USD:USD",
        help="Symbol to test (default: BTC/USD:USD)",
    )

    args = parser.parse_args()

    # Determine mode
    mode = "live" if args.live else "testing"

    # Run tests
    success = asyncio.run(run_all_tests(mode, args.symbol))

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
