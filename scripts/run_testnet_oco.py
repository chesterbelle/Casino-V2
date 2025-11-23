"""
Run a single real OCO-like order on Binance Testnet using Croupier.

Usage (Bash):
  export BINANCE_DEMO_API_KEY=your_key
  export BINANCE_DEMO_SECRET=your_secret
  python3 scripts/run_testnet_oco.py

Notes:
- This connects to Binance Testnet (demo) and places a MARKET entry + TP/SL.
- Use small `size` to avoid large exposure. Testnet funds must be available.
"""

import asyncio
import logging
import os
import sys

from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.binance.binance_connector import BinanceConnector


async def main():
    logging.basicConfig(level=logging.INFO)

    api_key = os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
    secret = os.getenv("BINANCE_DEMO_SECRET") or os.getenv("BINANCE_TESTNET_SECRET")

    if not api_key or not secret:
        print("ERROR: Binance testnet API keys not found. Export BINANCE_DEMO_API_KEY and BINANCE_DEMO_SECRET.")
        sys.exit(1)

    # Configure parameters for the test
    SYMBOL = "LTC/USDT:USDT"
    TIMEFRAME = "1m"
    INITIAL_BALANCE = 200.0  # USDT virtual starting point for croupier bookkeeping

    # Safety: choose a very small fraction to avoid using too much notional
    ORDER = {
        "symbol": SYMBOL,
        "side": "LONG",
        "size": 0.02,  # fraction of equity (2% of INITIAL_BALANCE)
        "take_profit": 1.01,  # +1%
        "stop_loss": 0.99,  # -1%
        "leverage": 5,
    }

    connector = BinanceConnector(api_key=api_key, secret=secret, mode="demo", enable_websocket=True)

    # Adapter delegates execution to connector
    adapter = CCXTAdapter(connector=connector, symbol=SYMBOL, timeframe=TIMEFRAME, prefer_ws=True)

    # Connect to the exchange
    print("Connecting to Binance testnet...")
    await connector.connect()

    # Create croupier with a modest starting balance for internal calculations
    croupier = Croupier(adapter, initial_balance=INITIAL_BALANCE)

    print("Placing order via Croupier:", ORDER)
    result = await croupier.execute_order(ORDER, wait_for_fill_confirmation=True)

    print("Order result:")
    print(result)

    # Give some time (and do a few monitor cycles) so PositionTracker/monitor can process OCO lifecycle
    print("Monitoring for a short period to allow TP/SL processing...")
    for i in range(10):
        await asyncio.sleep(2)
        try:
            await croupier.monitor_positions()
        except Exception as e:
            print("Monitor error:", e)

    # Show final state
    print("Final portfolio state:")
    print(croupier.get_portfolio_state())

    # Close connections
    print("Closing connector...")
    await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
