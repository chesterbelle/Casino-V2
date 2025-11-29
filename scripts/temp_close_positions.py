import asyncio
import logging

from exchanges.adapters.exchange_state_sync import ExchangeStateSync
from exchanges.connectors.binance.binance_connector import BinanceConnector

logger = logging.getLogger(__name__)


async def close_positions():
    connector = BinanceConnector(demo=True)
    await connector.connect()

    # Get open positions via ExchangeStateSync to ensure normalized positions
    sync = ExchangeStateSync(connector)
    positions = await sync.sync_positions()
    positions = [p.__dict__ for p in positions]
    logger.info(f"Found {len(positions)} positions")

    for pos in positions:
        if pos["contracts"] != 0:
            logger.info(f"Closing position: {pos['symbol']} - {pos['contracts']} contracts")
            try:
                result = await connector.close_position(pos["symbol"])
                logger.info(f"Close result: {result}")
            except Exception as e:
                logger.error(f"Error closing: {e}")

    await connector.close()


if __name__ == "__main__":
    asyncio.run(close_positions())
