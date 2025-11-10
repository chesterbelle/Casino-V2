import asyncio

import ccxt.async_support as ccxt


async def test():
    print("=" * 60)
    print("TESTNET - Verificando si podemos obtener datos de mainnet")
    print("=" * 60)

    # Testnet exchange
    ex_testnet = ccxt.bybit({"options": {"testnet": True, "defaultType": "linear"}})
    await ex_testnet.load_markets()

    # Mainnet exchange (solo para market data, sin API keys)
    ex_mainnet = ccxt.bybit({"options": {"defaultType": "linear"}})
    await ex_mainnet.load_markets()

    print("\n--- TESTNET TICKER ---")
    ticker_test = await ex_testnet.fetch_ticker("ETH/USDT:USDT")
    print(f"ETH Last: {ticker_test['last']}")
    print(f"ETH Bid: {ticker_test.get('bid')}")
    print(f"ETH Ask: {ticker_test.get('ask')}")

    print("\n--- MAINNET TICKER (sin autenticación) ---")
    ticker_main = await ex_mainnet.fetch_ticker("ETH/USDT:USDT")
    print(f"ETH Last: {ticker_main['last']}")
    print(f"ETH Bid: {ticker_main.get('bid')}")
    print(f"ETH Ask: {ticker_main.get('ask')}")

    print("\n--- COMPARACIÓN ---")
    print(f"Testnet price: ${ticker_test['last']:,.2f}")
    print(f"Mainnet price: ${ticker_main['last']:,.2f}")
    print(f"Difference: ${abs(ticker_test['last'] - ticker_main['last']):,.2f}")

    await ex_testnet.close()
    await ex_mainnet.close()


asyncio.run(test())
