"""Test rápido para verificar que get_balance_sync funciona"""

import sys

sys.path.insert(0, "/home/pedro/ProyectosGITHUB/Casino-V2")

from tables.table_ccxt_pro import TableCCXTPro

print("🔧 Creando mesa...")
table = TableCCXTPro(
    exchange_id="krakenfutures",
    symbols=["BTC/USD:USD"],
    timeframe="1m",
    testnet=False,  # Usará sandbox=True internamente para Kraken
)

print("📊 Obteniendo balance...")
try:
    balance = table.get_balance_sync()
    print(f"✅ Balance obtenido: {balance}")

    # Buscar USD
    if "USD" in balance:
        print(f"💰 USD Balance: {balance['USD']}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
