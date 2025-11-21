#!/usr/bin/env python3
# Copied from tests/test_bybit_connector.py

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from exchanges.connectors.bybit import BybitConnector  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def test_basic_connection(connector: BybitConnector) -> bool:
    try:
        logger.info("🔌 Testing connection...")
        await connector.connect()
        logger.info("✅ Connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False


async def run_all_tests(mode: str = "testing", symbol: str = "BTC/USD:USD") -> bool:
    logger.info("=" * 80)
    logger.info("🚀 BYBIT CONNECTOR TESTS")
    logger.info("=" * 80)

    connector = BybitConnector(mode=mode)

    tests = [
        ("Connection", test_basic_connection(connector)),
    ]

    results = []
    for test_name, test_coro in tests:
        result = await test_coro
        results.append((test_name, result))
        if result:
            logger.info(f"✅ {test_name} PASSED")
        else:
            logger.error(f"❌ {test_name} FAILED")

    await connector.close()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status} | {test_name}")

    logger.info(f"Result: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--testnet", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--symbol", type=str, default="BTC/USD:USD")
    args = parser.parse_args()
    mode = "live" if args.live else "testing"
    success = asyncio.run(run_all_tests(mode, args.symbol))
    sys.exit(0 if success else 1)
