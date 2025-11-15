#!/usr/bin/env python3
"""
Debug script to test fetch_positions() raw API response
"""
import asyncio
import json
import logging

from exchanges.connectors.binance import BinanceConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 80)
    logger.info("DEBUG: Testing fetch_positions() raw API response")
    logger.info("=" * 80)

    # Create connector in demo mode
    connector = BinanceConnector(mode="demo", enable_websocket=False)

    try:
        # Connect
        logger.info("\n1️⃣ Connecting to Binance Testnet...")
        await connector.connect()
        logger.info("✅ Connected")

        # Call raw API directly
        logger.info("\n2️⃣ Calling raw Binance API: fapiPrivateV2GetPositionRisk...")
        try:
            raw_response = await connector._safe_ccxt_call("fapiPrivateV2GetPositionRisk")
            logger.info("✅ Raw response received")
            logger.info("\n📊 Raw positions (JSON):")
            logger.info(json.dumps(raw_response, indent=2))
        except Exception as e:
            logger.error(f"❌ Error calling raw API: {e}", exc_info=True)

        # Try with symbol parameter
        logger.info("\n3️⃣ Calling raw API with symbol parameter...")
        try:
            raw_response_with_symbol = await connector._safe_ccxt_call(
                "fapiPrivateV2GetPositionRisk", {"symbol": "LTCUSDT"}
            )
            logger.info("✅ Raw response received")
            logger.info("\n📊 Raw positions for LTCUSDT (JSON):")
            logger.info(json.dumps(raw_response_with_symbol, indent=2))
        except Exception as e:
            logger.error(f"❌ Error calling raw API with symbol: {e}", exc_info=True)

        # Check exchange.positions attribute
        logger.info("\n4️⃣ Checking exchange.positions attribute...")
        if hasattr(connector.exchange, "positions"):
            logger.info(f"✅ exchange.positions exists: {connector.exchange.positions}")
        else:
            logger.info("⚠️ exchange.positions does not exist")

        # Check what fetch_positions returns
        logger.info("\n5️⃣ Calling fetch_positions() again...")
        positions = await connector.fetch_positions()
        logger.info(f"✅ fetch_positions() returned {len(positions)} positions")
        if positions:
            logger.info("\n📊 Positions (JSON):")
            logger.info(json.dumps(positions, indent=2, default=str))

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await connector.close()
        logger.info("\n✅ Closed connector")


if __name__ == "__main__":
    asyncio.run(main())
