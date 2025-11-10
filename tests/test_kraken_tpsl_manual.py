#!/usr/bin/env python3
"""
Test manual para crear órdenes TP/SL en Kraken Futures
Valores hardcodeados para entender el problema real
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.kraken import KrakenConnector


async def test_manual_tpsl():
    """Test manual con valores hardcodeados."""

    connector = KrakenConnector(mode="testing")

    try:
        # Conectar
        print("🔌 Conectando...")
        await connector.connect()
        print("✅ Conectado\n")

        # Obtener precio actual
        ticker = await connector.fetch_ticker("BTC/USD")
        current_price = ticker.get("last")
        print(f"💰 Precio actual BTC: ${current_price:,.2f}\n")

        # PASO 1: Crear orden SELL (SHORT) pequeña
        print("=" * 60)
        print("PASO 1: Crear orden SHORT (SELL)")
        print("=" * 60)

        amount = 0.001  # Muy pequeña

        main_order = await connector.create_order(
            symbol="BTC/USD",
            side="sell",
            amount=amount,
            order_type="market",
        )

        entry_price = main_order.get("price") or main_order.get("average") or current_price
        print(f"✅ Orden SHORT ejecutada")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Amount: {amount}")
        print(f"   Order ID: {main_order.get('id')}\n")

        # PASO 2: Crear orden TAKE PROFIT (BUY más abajo)
        print("=" * 60)
        print("PASO 2: Crear orden TAKE PROFIT - Probando variantes")
        print("=" * 60)

        # Para SHORT: TP debe estar ABAJO (ganamos si baja)
        tp_price = entry_price * 0.998  # 0.2% abajo

        # VARIANTE 1: type="limit" + triggerPrice
        print(f"\n[Variante 1] type='limit' + triggerPrice en params")
        print(f"   Trigger: ${tp_price:,.2f}\n")
        try:
            tp_order = await connector.exchange.create_order(
                symbol="BTC/USD:USD",
                type="limit",
                side="buy",
                amount=amount,
                price=tp_price,
                params={
                    "triggerPrice": tp_price,
                    "reduceOnly": True,
                },
            )
            print(f"✅ TP creado (variante 1): {tp_order.get('id')}\n")
        except Exception as e:
            print(f"❌ Error (variante 1): {e}\n")

        # VARIANTE 2: type="limit" + stopPrice
        print(f"[Variante 2] type='limit' + stopPrice en params")
        try:
            tp_order = await connector.exchange.create_order(
                symbol="BTC/USD:USD",
                type="limit",
                side="buy",
                amount=amount,
                price=tp_price,
                params={
                    "stopPrice": tp_price,
                    "reduceOnly": True,
                },
            )
            print(f"✅ TP creado (variante 2): {tp_order.get('id')}\n")
        except Exception as e:
            print(f"❌ Error (variante 2): {e}\n")

        # PASO 3: Crear orden STOP LOSS (BUY más arriba)
        print("=" * 60)
        print("PASO 3: Crear orden STOP LOSS")
        print("=" * 60)

        # Para SHORT: SL debe estar ARRIBA (perdemos si sube)
        sl_price = entry_price * 1.002  # 0.2% arriba

        print(f"Intentando crear SL:")
        print(f"   Type: stp (stop)")
        print(f"   Side: buy (para cerrar SHORT)")
        print(f"   Trigger: ${sl_price:,.2f}")
        print(f"   Amount: {amount}\n")

        try:
            sl_order = await connector.create_order(
                symbol="BTC/USD",
                side="buy",  # Cerrar SHORT
                amount=amount,
                price=sl_price,
                order_type="stp",
                params={
                    "stopPrice": sl_price,
                    "reduceOnly": True,
                },
            )
            print(f"✅ SL creado: {sl_order.get('id')}\n")
        except Exception as e:
            print(f"❌ Error creando SL: {e}\n")

        # PASO 4: Verificar órdenes abiertas
        print("=" * 60)
        print("PASO 4: Verificar órdenes abiertas")
        print("=" * 60)

        open_orders = await connector.fetch_open_orders(symbol="BTC/USD")
        print(f"Órdenes abiertas: {len(open_orders)}")
        for order in open_orders:
            print(f"  - {order.get('type')} {order.get('side')} @ ${order.get('price')}")
        print()

        # PASO 5: Verificar posición
        print("=" * 60)
        print("PASO 5: Verificar posición")
        print("=" * 60)

        positions = await connector.fetch_positions()
        btc_positions = [p for p in positions if p.get("symbol") == "BTC/USD"]

        if btc_positions:
            pos = btc_positions[0]
            print(f"✅ Posición abierta:")
            print(f"   Side: {pos.get('side')}")
            print(f"   Size: {pos.get('contracts')}")
            print(f"   Entry: ${pos.get('entryPrice')}")
        else:
            print("❌ No hay posición abierta")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await connector.close()
        print("\n🔌 Desconectado")


if __name__ == "__main__":
    asyncio.run(test_manual_tpsl())
