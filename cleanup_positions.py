#!/usr/bin/env python3

import asyncio

from exchanges.connectors.binance.binance_connector import BinanceConnector


async def cleanup():
    connector = BinanceConnector(mode="testnet")
    await connector.connect()

    # Get open positions
    positions = await connector.fetch_positions()
    print(f"Found {len(positions)} positions")

    for pos in positions:
        if pos.get("contracts", 0) != 0:
            symbol = pos["symbol"]
            size = abs(pos["contracts"])
            side = "sell" if pos["side"] == "long" else "buy"
            print(f'Closing position: {symbol} {pos["side"]} {size} contracts')

            # Create market order to close
            result = await connector.create_order(
                symbol=symbol, type="market", side=side, amount=size, params={"reduceOnly": True}
            )
            print(f"Close order result: {result}")

    await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(cleanup())
