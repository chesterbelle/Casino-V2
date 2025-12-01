#!/usr/bin/env python3
"""
Cleanup script for orphaned positions and orders on Binance Testnet.
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.connectors.binance.binance_connector import BinanceConnector


async def cleanup():
    """Clean up all positions and orders for LTC/USDT:USDT"""
    print("🧹 Starting cleanup...")
    
    # Initialize connector
    connector = BinanceConnector(mode="demo")
    await connector.connect()
    
    symbol = "LTC/USDT:USDT"
    
    try:
        # 1. Cancel all open orders
        print(f"\n📋 Fetching open orders for {symbol}...")
        orders = await connector.fetch_open_orders(symbol)
        print(f"   Found {len(orders)} open orders")
        
        for order in orders:
            order_id = order.get("id")
            print(f"   ❌ Cancelling order {order_id}...")
            try:
                await connector.cancel_order(order_id, symbol)
                print(f"      ✅ Cancelled")
            except Exception as e:
                print(f"      ⚠️ Error: {e}")
        
        # 2. Close all open positions
        print(f"\n📊 Fetching open positions for {symbol}...")
        positions = await connector.fetch_positions([symbol])
        active_positions = [p for p in positions if abs(float(p.get("contracts", 0))) > 0]
        print(f"   Found {len(active_positions)} active positions")
        
        for pos in active_positions:
            contracts = float(pos.get("contracts", 0))
            side = pos.get("side", "").lower()
            
            # Determine close side and positionSide
            if side == "long":
                close_side = "sell"
                position_side = "LONG"
            else:
                close_side = "buy"
                position_side = "SHORT"
            
            print(f"   🔄 Closing {side.upper()} position ({abs(contracts)} contracts)...")
            try:
                # In Hedge Mode, use explicit positionSide to close
                await connector.create_order(
                    symbol=symbol,
                    side=close_side,
                    amount=abs(contracts),
                    order_type="market",
                    params={"positionSide": position_side}
                )
                print(f"      ✅ Closed")
            except Exception as e:
                print(f"      ⚠️ Error: {e}")
        
        # 3. Verify cleanup
        print(f"\n🔍 Verifying cleanup...")
        await asyncio.sleep(2)
        
        final_orders = await connector.fetch_open_orders(symbol)
        final_positions = await connector.fetch_positions([symbol])
        final_active = [p for p in final_positions if abs(float(p.get("contracts", 0))) > 0]
        
        print(f"   Open orders: {len(final_orders)}")
        print(f"   Active positions: {len(final_active)}")
        
        if len(final_orders) == 0 and len(final_active) == 0:
            print("\n✅ Cleanup successful!")
        else:
            print("\n⚠️ Some items remain - may need manual cleanup")
        
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(cleanup())
