#!/usr/bin/env python3
"""
Verificar balance real de Binance Futures Testnet
"""
import asyncio
import ccxt.async_support as ccxt_async
from utils.exchanges.binance_env_loader import get_binance_credentials

async def check_balance():
    creds = get_binance_credentials()
    
    exchange = ccxt_async.binance({
        "apiKey": creds["apiKey"],
        "secret": creds["secret"],
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })
    
    # Activar testnet
    exchange.set_sandbox_mode(True)
    
    try:
        # Obtener balance
        balance = await exchange.fetch_balance()
        
        print("\n" + "="*60)
        print("📊 BALANCE COMPLETO DE BINANCE TESTNET")
        print("="*60)
        
        # Mostrar todas las monedas con balance
        print("\n🔍 Monedas con balance:")
        for currency, amounts in balance.items():
            if currency not in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
                if isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    free = amounts.get('free', 0)
                    used = amounts.get('used', 0)
                    if total > 0 or free > 0 or used > 0:
                        print(f"\n  {currency}:")
                        print(f"    Total: {total}")
                        print(f"    Free:  {free}")
                        print(f"    Used:  {used}")
        
        # Verificar USDT específicamente
        print("\n" + "="*60)
        print("💰 BALANCE USDT DETALLADO:")
        print("="*60)
        if 'USDT' in balance:
            usdt = balance['USDT']
            print(f"  Total: {usdt.get('total', 0)}")
            print(f"  Free:  {usdt.get('free', 0)}")
            print(f"  Used:  {usdt.get('used', 0)}")
        else:
            print("  ⚠️ No se encontró USDT en el balance")
        
        # Mostrar info raw
        print("\n" + "="*60)
        print("🔧 INFO RAW (primeros 5 items):")
        print("="*60)
        if 'info' in balance:
            info = balance['info']
            if isinstance(info, dict):
                for i, (key, value) in enumerate(info.items()):
                    if i >= 5:
                        break
                    print(f"  {key}: {value}")
            elif isinstance(info, list):
                print(f"  Lista con {len(info)} elementos")
                if len(info) > 0:
                    print(f"  Primer elemento: {info[0]}")
        
        await exchange.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_balance())
