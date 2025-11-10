import asyncio

import ccxt.async_support as ccxt


async def test():
    # Test 1: Con testnet=True (old way)
    print("Test 1: testnet=True")
    ex1 = ccxt.bybit({"options": {"testnet": True}})
    print(f"  URLs: {ex1.urls}")
    await ex1.close()

    # Test 2: Con URLs custom (new way)
    print("\nTest 2: URLs custom")
    ex2 = ccxt.bybit({"urls": {"api": "https://api-demo.bybit.com"}})
    print(f"  URLs: {ex2.urls}")
    await ex2.close()

    # Test 3: Verificar estructura completa
    print("\nTest 3: Estructura completa de URLs")
    ex3 = ccxt.bybit()
    print(f"  Default URLs keys: {list(ex3.urls.keys())}")
    print(f"  Default API: {ex3.urls.get('api')}")
    await ex3.close()


asyncio.run(test())
