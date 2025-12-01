#!/usr/bin/env python3
"""
Sweep Dust Script
Increases dust positions to minimum notional size and then closes them.
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.connectors.binance.binance_connector import BinanceConnector


async def sweep_dust():
    """Sweep dust positions for LTC/USDT:USDT"""
    print("🧹 Starting dust sweep...")
    
    # Initialize connector
    connector = BinanceConnector(mode="demo")
    await connector.connect()
    
    symbol = "LTC/USDT:USDT"
    
    try:
        # 1. Fetch positions
        print(f"\n📊 Fetching positions for {symbol}...")
        positions = await connector.fetch_positions([symbol])
        active_positions = [p for p in positions if abs(float(p.get("contracts", 0))) > 0]
        print(f"   Found {len(active_positions)} active positions")
        
        for pos in active_positions:
            contracts = float(pos.get("contracts", 0))
            side = pos.get("side", "").lower() # long or short
            
            print(f"   🔍 Found {side.upper()} position: {contracts} contracts")
            
            # Target size to reach min notional (approx $10 to be safe)
            # LTC price ~78, so 0.15 LTC is ~$11.7
            TARGET_SIZE = 0.15
            
            if abs(contracts) < TARGET_SIZE:
                diff = TARGET_SIZE - abs(contracts)
                print(f"      ⚠️ Position is dust (< {TARGET_SIZE}). Increasing by {diff:.4f}...")
                
                # Increase position
                # If LONG, buy more. If SHORT, sell more.
                increase_side = "buy" if side == "long" else "sell"
                position_side = "LONG" if side == "long" else "SHORT"
                
                try:
                    await connector.create_order(
                        symbol=symbol,
                        side=increase_side,
                        amount=diff,
                        order_type="market",
                        params={"positionSide": position_side}
                    )
                    print(f"      ✅ Increased position")
                    await asyncio.sleep(2) # Wait for update
                except Exception as e:
                    print(f"      ❌ Failed to increase position: {e}")
                    continue
            
            # Now close the full position
            # Re-fetch to get exact new size
            positions_new = await connector.fetch_positions([symbol])
            pos_new = next((p for p in positions_new if p.get("side", "").lower() == side), None)
            
            if not pos_new:
                print("      ⚠️ Position disappeared?")
                continue
                
            new_contracts = float(pos_new.get("contracts", 0))
            print(f"      🔄 Closing full position ({new_contracts} contracts)...")
            
            close_side = "sell" if side == "long" else "buy"
            position_side = "LONG" if side == "long" else "SHORT"
            
            try:
                await connector.create_order(
                    symbol=symbol,
                    side=close_side,
                    amount=abs(new_contracts),
                    order_type="market",
                    params={"positionSide": position_side}
                )
                print(f"      ✅ Closed successfully")
            except Exception as e:
                print(f"      ❌ Failed to close: {e}")

        # Final check
        print(f"\n🔍 Verifying...")
        await asyncio.sleep(2)
        final_positions = await connector.fetch_positions([symbol])
        final_active = [p for p in final_positions if abs(float(p.get("contracts", 0))) > 0]
        print(f"   Remaining positions: {len(final_active)}")
        
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(sweep_dust())
