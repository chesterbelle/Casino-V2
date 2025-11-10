import asyncio

import ccxt.async_support as ccxt


async def test():
    # Test Demo Trading API (real prices)
    print("=" * 60)
    print("DEMO TRADING API (real market prices)")
    print("=" * 60)
    ex_demo = ccxt.bybit({"urls": {"api": "https://api-demo.bybit.com"}, "options": {"defaultType": "linear"}})
    await ex_demo.load_markets()

    print("\nTesting ETH/USDT:USDT ticker...")
    ticker_eth = await ex_demo.fetch_ticker("ETH/USDT:USDT")
    print(f"ETH Symbol: {ticker_eth['symbol']}")
    print(f"ETH Last: {ticker_eth['last']}")
    print(f"ETH Bid: {ticker_eth.get('bid')}")
    print(f"ETH Ask: {ticker_eth.get('ask')}")

    print("\nTesting BTC/USDT:USDT ticker...")
    ticker_btc = await ex_demo.fetch_ticker("BTC/USDT:USDT")
    print(f"BTC Symbol: {ticker_btc['symbol']}")
    print(f"BTC Last: {ticker_btc['last']}")
    print(f"BTC Bid: {ticker_btc.get('bid')}")
    print(f"BTC Ask: {ticker_btc.get('ask')}")

    await ex_demo.close()

    # Test Testnet API (fake prices)
    print("\n" + "=" * 60)
    print("TESTNET API (fake/simulated prices)")
    print("=" * 60)
    ex_testnet = ccxt.bybit({"options": {"testnet": True}})
    await ex_testnet.load_markets()

    print("\nTesting ETH/USDT:USDT ticker...")
    ticker_eth_test = await ex_testnet.fetch_ticker("ETH/USDT:USDT")
    print(f"ETH Symbol: {ticker_eth_test['symbol']}")
    print(f"ETH Last: {ticker_eth_test['last']}")

    print("\nTesting BTC/USDT:USDT ticker...")
    ticker_btc_test = await ex_testnet.fetch_ticker("BTC/USDT:USDT")
    print(f"BTC Symbol: {ticker_btc_test['symbol']}")
    print(f"BTC Last: {ticker_btc_test['last']}")

    await ex_testnet.close()


asyncio.run(test())
