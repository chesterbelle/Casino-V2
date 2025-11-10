#!/usr/bin/env python3
"""
Validación rápida de órdenes OCO con TP/SL en Kraken Futures
"""

import asyncio
import os
import sys

# Agregar raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from exchanges.connectors.kraken.kraken_connector import KrakenConnector


async def main():
    """
    Prueba de creación de orden con OCO bracket
    """
    # Crear conector en modo testing
    connector = KrakenConnector(mode="testing")

    try:
        # Conectar
        print("🔌 Conectando a Kraken Futures...")
        await connector.connect()
        print("✅ Conectado")

        # Parámetros de prueba
        symbol = "BTC/USD"
        side = "sell"
        amount = 0.01  # Aumentado de 0.001 a 0.01 para cumplir requisitos mínimos
        price = None  # Market order
        tp_price = 95000.0
        sl_price = 105000.0

        # Crear orden con OCO bracket
        print(f"🚀 Creando orden OCO bracket: {side.upper()} {amount} {symbol}")
        print(f"   TP: {tp_price}, SL: {sl_price}")

        order_result = await connector.create_order_with_tpsl(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type="market",
            tp_price=tp_price,
            sl_price=sl_price,
        )

        print("✅ Orden creada exitosamente")
        print("Resultado:", order_result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Desconectar
        print("🔌 Desconectando...")
        await connector.close()
        print("✅ Desconectado")


if __name__ == "__main__":
    asyncio.run(main())
