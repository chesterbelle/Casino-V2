#!/usr/bin/env python3
"""
Verificar balance de Binance Futures Testnet con SSL deshabilitado
"""
import asyncio
import ssl
import ccxt.async_support as ccxt_async
from utils.exchanges.binance_env_loader import get_binance_credentials

async def check_balance_no_ssl():
    creds = get_binance_credentials()

    # Crear contexto SSL que no verifica certificados
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    exchange = ccxt_async.binance({
        "apiKey": creds["apiKey"],
        "secret": creds["secret"],
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
        "urls": {
            "api": {
                "fapiPublic": "https://demo-fapi.binance.com/fapi/v1",
                "fapiPrivate": "https://demo-fapi.binance.com/fapi/v1",
                "fapiPublicV2": "https://demo-fapi.binance.com/fapi/v2",
                "fapiPrivateV2": "https://demo-fapi.binance.com/fapi/v2",
                "fapiPublicV3": "https://demo-fapi.binance.com/fapi/v3",
                "fapiPrivateV3": "https://demo-fapi.binance.com/fapi/v3",
            }
        },
        "sandbox": True,
        "ssl": ssl_context  # Deshabilitar verificación SSL
    })

    try:
        print("🔍 Intentando conectar a Binance Testnet con SSL deshabilitado...")

        # Obtener balance
        balance = await exchange.fetch_balance()

        print("\n" + "="*60)
        print("✅ ¡CONEXIÓN EXITOSA!")
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

        await exchange.close()

    except Exception as e:
        print(f"\n❌ Error incluso con SSL deshabilitado: {e}")
        import traceback
        traceback.print_exc()
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_balance_no_ssl())
