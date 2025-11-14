import asyncio

from exchanges.connectors.binance.binance_connector import BinanceConnector


async def close_positions():
    connector = BinanceConnector(demo=True)
    await connector.connect()

    # Get open positions
    positions = await connector.fetch_positions()
    print(f"Found {len(positions)} positions")

    for pos in positions:
        if pos["contracts"] != 0:
            print(f"Closing position: {pos['symbol']} - {pos['contracts']} contracts")
            try:
                result = await connector.close_position(pos["symbol"])
                print(f"Close result: {result}")
            except Exception as e:
                print(f"Error closing: {e}")

    await connector.close()


if __name__ == "__main__":
    asyncio.run(close_positions())
