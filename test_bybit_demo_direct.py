#!/usr/bin/env python3
"""Test Bybit Demo Trading connection directly."""
import asyncio
import os

import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()


async def test():
    api_key = os.getenv("BYBIT_API_KEY")
    secret = os.getenv("BYBIT_API_SECRET")

    print("=" * 60)
    print("TEST: Bybit Demo Trading Direct Connection")
    print("=" * 60)
    print(f"API Key: {api_key[:15]}..." if api_key else "NOT FOUND")
    print(f"Secret: {secret[:15]}..." if secret else "NOT FOUND")
    print()

    # Test with Demo Trading URLs
    print("Creating exchange with Demo Trading URLs...")
    exchange = ccxt.bybit(
        {
            "apiKey": api_key,
            "secret": secret,
            "hostname": "bybit.com",
            "options": {
                "defaultType": "linear",
            },
            "urls": {
                "api": {
                    "spot": "https://api-demo.bybit.com",
                    "futures": "https://api-demo.bybit.com",
                    "v2": "https://api-demo.bybit.com",
                    "public": "https://api-demo.bybit.com",
                    "private": "https://api-demo.bybit.com",
                }
            },
        }
    )

    print(f"Exchange URLs: {exchange.urls.get('api')}")
    print()

    try:
        # Test public endpoint (no auth)
        print("1. Testing public endpoint (ticker)...")
        ticker = await exchange.fetch_ticker("ETH/USDT:USDT")
        print(f"   ✅ Ticker: ETH = ${ticker['last']:,.2f}")

        # Test private endpoint (auth required)
        print("\n2. Testing private endpoint (balance)...")
        balance = await exchange.fetch_balance()
        print(f"   ✅ Balance loaded: {len(balance)} currencies")

        # Show USDT balance
        if "USDT" in balance:
            usdt = balance["USDT"]
            print(f"   💰 USDT: free={usdt.get('free', 0)}, used={usdt.get('used', 0)}, total={usdt.get('total', 0)}")

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await exchange.close()

    print("=" * 60)


asyncio.run(test())
