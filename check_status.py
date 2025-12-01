#!/usr/bin/env python3
"""
Check status of positions and orders on Binance Testnet.
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.connectors.binance.binance_connector import BinanceConnector


async def check():
    """Check status for LTC/USDT:USDT"""
    print("🔍 Checking status...")
    
    # Initialize connector
    connector = BinanceConnector(mode="demo")
    await connector.connect()
    
    symbol = "LTC/USDT:USDT"
    
    try:
        # 1. Fetch open orders
        print(f"\n📋 Open Orders for {symbol}:")
        orders = await connector.fetch_open_orders(symbol)
        if not orders:
            print("   None")
        for order in orders:
            print(f"   - ID: {order['id']}, Type: {order['type']}, Side: {order['side']}, Price: {order.get('price')}, Stop: {order.get('stopPrice')}")
        
        # 2. Fetch open positions
        print(f"\n📊 Open Positions for {symbol}:")
        positions = await connector.fetch_positions([symbol])
        active_positions = [p for p in positions if abs(float(p.get("contracts", 0))) > 0]
        
        if not active_positions:
            print("   None")
        for pos in active_positions:
            print(f"   - Side: {pos['side']}, Contracts: {pos['contracts']}, Entry: {pos['entryPrice']}, PnL: {pos['unrealizedPnl']}")
            
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(check())
