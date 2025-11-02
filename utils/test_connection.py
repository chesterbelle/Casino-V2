"""
Test Connection Utility
Prueba conexión básica con exchanges via CCXT
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import asyncio
import logging

from tables.table_ccxt_pro import TableCCXTPro

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConnectionTester")


async def test_exchange_connection(exchange: str, testnet: bool = True):
    """Prueba conexión WebSocket y REST con el exchange."""
    try:
        logger.info(f"🔄 Probando conexión con {exchange.upper()} (testnet={testnet})")

        # 1. Conexión básica
        table = TableCCXTPro(exchange_id=exchange, symbols=["BTC/USDT"], timeframe="1m", testnet=testnet)

        # 2. WebSocket
        logger.info("🌐 Probando WebSocket...")
        await table.connect()

        # 3. REST API
        logger.info("📡 Probando API REST...")
        markets = await table.exchange.load_markets()
        logger.info(f"✅ {len(markets)} mercados disponibles")

        # 4. Balance (solo si es testnet)
        if testnet:
            balance = await table.exchange.fetch_balance()
            logger.info(f"💰 Balance de prueba: {balance['total']['USDT']} USDT")

        logger.info("🎉 ¡Prueba exitosa!")

    except Exception as e:
        logger.error(f"❌ Error de conexión: {e}", exc_info=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", required=True, choices=["binance", "kraken", "hyperliquid"])
    parser.add_argument("--testnet", type=bool, default=True)
    args = parser.parse_args()

    asyncio.run(test_exchange_connection(args.exchange, args.testnet))


if __name__ == "__main__":
    main()
