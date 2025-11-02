"""Test del flujo async completo"""

import asyncio
import sys

sys.path.insert(0, "/home/pedro/ProyectosGITHUB/Casino-V2")

from tables.table_ccxt_pro import TableCCXTPro


async def main():
    print("🔧 Creando mesa...")
    table = TableCCXTPro(exchange_id="krakenfutures", symbols=["LTC/USD:USD"], timeframe="1m", testnet=False)

    print("🔌 Conectando...")
    await table.connect()

    print("📊 Obteniendo balance...")
    balance = await table.exchange.fetch_balance()
    print(f"✅ Balance: USD = {balance.get('USD', {}).get('total', 0)}")

    print("📡 Iniciando polling (5 iteraciones)...")
    for i in range(5):
        print(f"\n🔄 Poll #{i+1}")
        ohlcv = await table.exchange.fetch_ohlcv("LTC/USD:USD", "1m", limit=1)
        if ohlcv:
            print(f"✅ Datos recibidos: Close = {ohlcv[-1][4]}")
        await asyncio.sleep(2)

    print("\n🔌 Desconectando...")
    await table.disconnect()
    print("✅ Test completado!")


if __name__ == "__main__":
    asyncio.run(main())
