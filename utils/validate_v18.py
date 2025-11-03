#!/usr/bin/env python3
"""
Validation Script for v1.8 - Mesa + Conectores Architecture.

This script validates that the new architecture works correctly:
1. KrakenConnector connects to testnet
2. TableCCXTPro uses the connector
3. Balance is fetched correctly
4. Candles are fetched correctly
5. Integration with BrokerInterface works

Run:
    python utils/validate_v18.py
"""

import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("ValidateV18")


async def test_connector():
    """Test KrakenConnector directly."""
    logger.info("=" * 60)
    logger.info("TEST 1: KrakenConnector")
    logger.info("=" * 60)

    try:
        from tables.connectors import KrakenConnector

        # Create connector
        connector = KrakenConnector(testnet=True)
        logger.info(f"✅ Connector created: {connector.exchange_name}")

        # Connect
        await connector.connect()
        logger.info("✅ Connected to Kraken testnet")

        # Fetch balance
        balance = await connector.fetch_balance()
        free_usd = balance.get("free", {}).get("USD", 0.0)
        logger.info(f"✅ Balance fetched: {free_usd} USD")

        # Fetch OHLCV
        candles = await connector.fetch_ohlcv("BTC/USD", "1m", limit=5)
        logger.info(f"✅ Fetched {len(candles)} candles")
        logger.info(f"   Latest close: ${candles[-1]['close']:,.2f}")

        # Close
        await connector.close()
        logger.info("✅ Connector closed")

        return True

    except Exception as e:
        logger.error(f"❌ Connector test failed: {e}", exc_info=True)
        return False


async def test_table():
    """Test TableCCXTPro with KrakenConnector."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: TableCCXTPro + KrakenConnector")
    logger.info("=" * 60)

    try:
        from tables.connectors import KrakenConnector
        from tables.table_ccxt_pro import TableCCXTPro

        # Create connector and table
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")
        logger.info("✅ Table created with connector")

        # Connect
        await table.connect()
        logger.info("✅ Table connected")

        # Check balance
        balance = table.get_balance()
        logger.info(f"✅ Balance: ${balance:,.2f}")

        # Fetch candle
        candle = await table.next_candle()
        logger.info(f"✅ Candle fetched: ${candle['close']:,.2f}")

        # Refresh balance
        new_balance = await table.refresh_balance()
        logger.info(f"✅ Balance refreshed: ${new_balance:,.2f}")

        # Close
        await table.close()
        logger.info("✅ Table closed")

        return True

    except Exception as e:
        logger.error(f"❌ Table test failed: {e}", exc_info=True)
        return False


def test_broker_interface():
    """Test BrokerInterface integration."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: BrokerInterface Integration")
    logger.info("=" * 60)

    try:
        # Temporarily set config for testing
        import os
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from core import config

        # Save original values
        original_mode = getattr(config, "MODE", None)
        original_exchange = getattr(config, "EXCHANGE", None)

        # Set test values
        config.MODE = "live"
        config.EXCHANGE = "KRAKEN_DEMO"

        from croupier.broker_interface import BrokerInterface

        # Create broker
        broker = BrokerInterface(symbol="BTC/USD", interval="1m")
        logger.info("✅ BrokerInterface created")

        # Check table
        table = broker.engine.table
        logger.info(f"✅ Table type: {type(table).__name__}")
        logger.info(f"✅ Exchange: {table.exchange_name}")
        logger.info(f"✅ Symbol: {table.symbol}")

        # Restore original values
        if original_mode:
            config.MODE = original_mode
        if original_exchange:
            config.EXCHANGE = original_exchange

        return True

    except Exception as e:
        logger.error(f"❌ BrokerInterface test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all validation tests."""
    logger.info("\n" + "🎯" * 30)
    logger.info("VALIDACIÓN v1.8 - Mesa + Conectores")
    logger.info("🎯" * 30 + "\n")

    results = []

    # Test 1: Connector
    result1 = await test_connector()
    results.append(("KrakenConnector", result1))

    # Test 2: Table
    result2 = await test_table()
    results.append(("TableCCXTPro", result2))

    # Test 3: BrokerInterface
    result3 = test_broker_interface()
    results.append(("BrokerInterface", result3))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN DE VALIDACIÓN")
    logger.info("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name:20s} {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 60)

    if all_passed:
        logger.info("🎉 TODAS LAS VALIDACIONES PASARON!")
        logger.info("✅ v1.8 está funcionando correctamente")
        return 0
    else:
        logger.error("❌ ALGUNAS VALIDACIONES FALLARON")
        logger.error("⚠️ Revisa los errores arriba")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
