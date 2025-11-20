#!/usr/bin/env python3
"""
Force a single order via Croupier for testing instrumentation.
Saves result to `logs/force_order_result.json`.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.binance.binance_connector import BinanceConnector

LOGS = Path("logs")
LOGS.mkdir(exist_ok=True)


async def run_once():
    # Load API keys from env if present; BinanceConnector will warn if missing
    api_key = os.environ.get("BINANCE_API_KEY")
    secret = os.environ.get("BINANCE_API_SECRET")

    connector = BinanceConnector(api_key=api_key, secret=secret, mode="demo", enable_websocket=True)
    try:
        await connector.connect()
    except Exception as e:
        print("Connector connect failed (continuing):", e)

    adapter = CCXTAdapter(connector=connector, symbol="BTC/USDT:USDT", timeframe="1m")

    # Start croupier with a modest initial balance (will sync later)
    croupier = Croupier(adapter, initial_balance=1000.0)

    # Build an order that is small but above min notional
    order = {
        "symbol": "BTC/USDT:USDT",
        "side": "LONG",
        "size": 0.0005,  # fraction of equity — small
        "take_profit": 1.001,  # +0.1%
        "stop_loss": 0.999,  # -0.1%
        "leverage": 1,
        "ghost": False,
        "ws_timeout_ms": 3000,
    }

    print("Executing order via Croupier...")
    try:
        result = await croupier.execute_order(order)
        print("Result:", result)
    except Exception as e:
        result = {"error": str(e)}
        print("Execution failed:", e)

    out_path = LOGS / f'force_order_result_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
    with out_path.open("w") as f:
        json.dump(result, f, indent=2, default=str)
    print("Saved result to", out_path)

    try:
        await connector.close()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(run_once())
