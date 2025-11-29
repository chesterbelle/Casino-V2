#!/usr/bin/env python3
"""
Debug script to test fetch_positions() for Binance Testnet
"""
import asyncio
import logging

from exchanges.adapters.exchange_state_sync import ExchangeStateSync
from exchanges.connectors.binance import BinanceConnector

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 80)
    logger.info("DEBUG: Testing fetch_positions() for Binance Testnet")
    logger.info("=" * 80)

    # Create connector in demo mode
    connector = BinanceConnector(mode="demo", enable_websocket=False)

    try:
        # Connect
        logger.info("\n1️⃣ Connecting to Binance Testnet...")
        await connector.connect()
        logger.info("✅ Connected")

        # Fetch positions via ExchangeStateSync
        logger.info("\n2️⃣ Fetching ALL positions via ExchangeStateSync...")
        sync = ExchangeStateSync(connector)
        all_positions = await sync.sync_positions()
        # Convert to dict for compatibility
        all_positions = [p.__dict__ for p in all_positions]
        logger.info(f"✅ Fetched {len(all_positions)} total positions")

        if all_positions:
            logger.info("\n📊 All positions:")
            for i, pos in enumerate(all_positions):
                logger.info(f"\n  Position {i+1}:")
                logger.info(f"    Symbol: {pos.get('symbol')}")
                logger.info(f"    Side: {pos.get('side')}")
                logger.info(f"    Contracts: {pos.get('contracts')}")
                logger.info(f"    Entry Price: {pos.get('info', {}).get('entryPrice')}")
                logger.info(f"    Mark Price: {pos.get('info', {}).get('markPrice')}")
                logger.info(f"    Unrealized PnL: {pos.get('info', {}).get('unRealizedProfit')}")
        else:
            logger.info("⚠️ No positions found")

        # Fetch positions for specific symbol
        logger.info("\n3️⃣ Fetching positions for LTC/USD:USD...")
        ltc_positions = await sync.sync_positions()
        ltc_positions = [p.__dict__ for p in ltc_positions if p.symbol == "LTC/USD:USD"]
        logger.info(f"✅ Fetched {len(ltc_positions)} positions for LTC/USD:USD")

        if ltc_positions:
            logger.info("\n📊 LTC/USD:USD positions:")
            for i, pos in enumerate(ltc_positions):
                logger.info(f"\n  Position {i+1}:")
                logger.info(f"    Symbol: {pos.get('symbol')}")
                logger.info(f"    Side: {pos.get('side')}")
                logger.info(f"    Contracts: {pos.get('contracts')}")
                logger.info(f"    Entry Price: {pos.get('info', {}).get('entryPrice')}")
        else:
            logger.info("⚠️ No positions found for LTC/USD:USD")

        # Fetch positions for normalized symbol
        logger.info("\n4️⃣ Fetching positions for LTCUSDT...")
        ltc_norm_positions = await sync.sync_positions()
        ltc_norm_positions = [
            p.__dict__ for p in ltc_norm_positions if p.symbol == "LTCUSDT" or p.symbol == "LTC/USDT:USDT"
        ]
        logger.info(f"✅ Fetched {len(ltc_norm_positions)} positions for LTCUSDT")

        if ltc_norm_positions:
            logger.info("\n📊 LTCUSDT positions:")
            for i, pos in enumerate(ltc_norm_positions):
                logger.info(f"\n  Position {i+1}:")
                logger.info(f"    Symbol: {pos.get('symbol')}")
                logger.info(f"    Side: {pos.get('side')}")
                logger.info(f"    Contracts: {pos.get('contracts')}")
        else:
            logger.info("⚠️ No positions found for LTCUSDT")

        # Fetch open orders
        logger.info("\n5️⃣ Fetching open orders for LTC/USD:USD...")
        open_orders = await connector.fetch_open_orders("LTC/USD:USD")
        logger.info(f"✅ Fetched {len(open_orders)} open orders")

        if open_orders:
            logger.info("\n📋 Open orders:")
            for i, order in enumerate(open_orders):
                logger.info(f"\n  Order {i+1}:")
                logger.info(f"    ID: {order.get('id')}")
                logger.info(f"    Type: {order.get('type')}")
                logger.info(f"    Side: {order.get('side')}")
                logger.info(f"    Status: {order.get('status')}")
                logger.info(f"    Amount: {order.get('amount')}")
        else:
            logger.info("⚠️ No open orders found")

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await connector.close()
        logger.info("\n✅ Closed connector")


if __name__ == "__main__":
    asyncio.run(main())
