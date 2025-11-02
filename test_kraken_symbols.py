"""Script para listar símbolos disponibles en Kraken Futures Demo"""

import asyncio

import ccxt.async_support as ccxt_async

from utils.exchanges.kraken_env_loader import load_kraken_config


async def list_symbols():
    config = load_kraken_config()

    exchange = ccxt_async.krakenfutures(
        {
            "apiKey": config["api_key"],
            "secret": config["api_secret"],
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
            "sandbox": True,  # Usar demo environment
        }
    )

    try:
        markets = await exchange.load_markets()
        print(f"\n📊 Símbolos disponibles en Kraken Futures Demo ({len(markets)} total):\n")

        # Filtrar solo perpetuals
        perpetuals = [symbol for symbol, market in markets.items() if market.get("type") == "swap"]

        print("🔄 Perpetual Futures:")
        for symbol in sorted(perpetuals)[:20]:  # Mostrar primeros 20
            market = markets[symbol]
            print(f"  - {symbol:30} | Base: {market.get('base'):8} | Quote: {market.get('quote')}")

        print(f"\n... y {len(perpetuals) - 20} más")

        # Buscar BTC y LTC específicamente
        print("\n🔍 Buscando BTC y LTC:")
        for symbol in markets:
            if "BTC" in symbol or "LTC" in symbol:
                market = markets[symbol]
                print(f"  - {symbol:30} | Type: {market.get('type'):10} | Active: {market.get('active')}")

    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(list_symbols())
