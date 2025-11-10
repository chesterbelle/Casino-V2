import asyncio

import ccxt


async def test():
    ex = ccxt.bybit({"enableRateLimit": True})
    await ex.load_markets()
    print("Symbol exists:", "LTC/USDT:USDT" in ex.markets)
    try:
        ohlcv = await ex.fetch_ohlcv("LTC/USDT:USDT", "1m", limit=1)
        print("OHLCV OK:", ohlcv[0] if ohlcv else None)
    except Exception as e:
        print("Error:", e)
    await ex.close()


asyncio.run(test())
