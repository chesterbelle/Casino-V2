#!/usr/bin/env python3
"""List available trading symbols on Binance testnet"""

import asyncio
import logging

from exchanges.connectors.binance import BinanceConnector

logger = logging.getLogger(__name__)


async def main():
    connector = BinanceConnector(mode="demo", enable_websocket=False)
    await connector.connect()

    # Get all markets
    markets = connector.exchange.symbols

    # Filter for USDT futures
    usdt_symbols = [s for s in markets if "USDT" in s and ":" in s]

    logger.info(f"\n📊 Available USDT Futures Symbols on Binance Testnet ({len(usdt_symbols)} total):\n")

    # Show first 50
    for i, symbol in enumerate(sorted(usdt_symbols)[:50], 1):
        logger.info(f"{i:2d}. {symbol}")

    if len(usdt_symbols) > 50:
        logger.info(f"\n... and {len(usdt_symbols) - 50} more")

    await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
