#!/usr/bin/env python3
"""Test which endpoints CCXT is calling for Demo Trading."""
import asyncio
import os

import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()


async def test():
    api_key = os.getenv("BYBIT_API_KEY")
    secret = os.getenv("BYBIT_API_SECRET")

    print("=" * 60)
    print("TEST: CCXT Endpoint Mapping for Demo Trading")
    print("=" * 60)

    # Create demo exchange
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
            "verbose": True,  # Enable verbose to see actual API calls
        }
    )

    try:
        print("\n1. Testing fetch_balance()...")
        try:
            balance = await exchange.fetch_balance()
            print(f"   ✅ Success: {list(balance.keys())[:5]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print("\n2. Testing fetch_positions()...")
        try:
            positions = await exchange.fetch_positions()
            print(f"   ✅ Success: {len(positions)} positions")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print("\n3. Testing fetch_my_trades()...")
        try:
            trades = await exchange.fetch_my_trades("ETH/USDT:USDT", limit=5)
            print(f"   ✅ Success: {len(trades)} trades")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print("\n4. Testing fetch_open_orders()...")
        try:
            orders = await exchange.fetch_open_orders("ETH/USDT:USDT")
            print(f"   ✅ Success: {len(orders)} orders")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    finally:
        await exchange.close()

    print("=" * 60)


asyncio.run(test())
