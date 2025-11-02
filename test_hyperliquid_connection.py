"""
Test de conexión básica con Hyperliquid
Verifica que TableCCXTPro puede conectarse y obtener datos
"""

import asyncio
import logging

from tables.table_ccxt_pro import TableCCXTPro

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")


async def test_hyperliquid_connection():
    """Test básico de conexión con Hyperliquid"""
    print("🚀 Iniciando test de conexión Hyperliquid...")

    # Crear tabla con Hyperliquid
    # Usar BTC como símbolo de prueba
    table = TableCCXTPro(
        exchange_id="hyperliquid",
        symbols=["BTC/USDC:USDC"],  # Formato perpetual de Hyperliquid
        timeframe="1m",
        testnet=False,  # Usar mainnet (con cuidado)
    )

    try:
        # Conectar
        print("\n📡 Conectando al exchange...")
        await table.connect()
        print(f"✅ Conectado exitosamente")
        print(f"   Modo de datos: {table.data_mode}")
        print(f"   WebSocket soportado: {table.websocket_supported}")

        # Obtener balance
        print("\n💰 Obteniendo balance...")
        balance_data = await table.exchange.fetch_balance()
        print(f"✅ Balance obtenido")

        # Mostrar algunos datos del balance
        total = balance_data.get("total", {})
        print(f"   Monedas con balance: {list(total.keys())[:5]}")

        # Intentar obtener una vela
        print("\n📊 Obteniendo vela de prueba...")
        candles = await table.exchange.fetch_ohlcv("BTC/USDC:USDC", "1m", limit=1)
        if candles:
            candle = candles[0]
            print(f"✅ Vela obtenida:")
            print(f"   Timestamp: {candle[0]}")
            print(f"   Close: {candle[4]}")

        print("\n✅ Test completado exitosamente!")
        return True

    except Exception as e:
        print(f"\n❌ Error en test: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Desconectar
        print("\n🔌 Desconectando...")
        await table.disconnect()
        print("✅ Desconectado")


if __name__ == "__main__":
    success = asyncio.run(test_hyperliquid_connection())
    exit(0 if success else 1)
