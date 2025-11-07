"""
Test para Order Tracker

Verifica que el tracking de órdenes funciona correctamente.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.kraken import KrakenConnector
from exchanges.connectors.resilient_connector import ResilientConnector


async def test_order_tracking():
    """Test básico de order tracking."""
    print("=" * 80)
    print("🧪 TEST: Order Tracking")
    print("=" * 80)

    # 1. Crear conector
    kraken = KrakenConnector(mode="testing")
    connector = ResilientConnector(
        connector=kraken,
        enable_state_recovery=False,  # Deshabilitado para test
    )

    await connector.connect()

    # 2. Verificar que OrderTracker está inicializado
    tracker = connector.get_order_tracker()
    print(f"\n✅ OrderTracker inicializado")
    print(f"   Métricas iniciales: {tracker.get_metrics()}")

    # 3. Simular creación de orden (sin enviar realmente)
    print("\n📝 Simulando tracking de orden...")

    client_order_id = connector._generate_client_order_id()
    print(f"   Client Order ID: {client_order_id}")

    tracked_order = tracker.start_tracking(
        client_order_id=client_order_id,
        symbol="BTC/USD",
        side="buy",
        amount=0.001,
        order_type="market",
    )

    print(f"   ✅ Orden trackeada | Status: {tracked_order.status.value}")

    # 4. Verificar que está en in_flight
    in_flight = tracker.get_all_in_flight()
    print(f"\n📊 Órdenes en vuelo: {len(in_flight)}")
    assert len(in_flight) == 1, "Debe haber 1 orden en vuelo"

    # 5. Simular envío exitoso
    print("\n✅ Simulando envío exitoso...")
    tracker.update_order_submitted(client_order_id, "EXCHANGE_ORDER_123")

    order = tracker.get_order(client_order_id)
    print(f"   Status: {order.status.value}")
    print(f"   Exchange Order ID: {order.exchange_order_id}")

    # 6. Simular fill
    print("\n✅ Simulando fill...")
    tracker.update_from_exchange(
        client_order_id,
        {
            "id": "EXCHANGE_ORDER_123",
            "status": "closed",
            "filled": 0.001,
            "remaining": 0.0,
            "average": 95000.0,
        },
    )

    # 7. Verificar métricas finales
    metrics = tracker.get_metrics()
    print(f"\n📊 Métricas finales:")
    print(f"   Total tracked: {metrics['total_tracked']}")
    print(f"   Total filled: {metrics['total_filled']}")
    print(f"   In flight: {metrics['in_flight_orders']}")
    print(f"   Completed: {metrics['completed_orders']}")
    print(f"   Fill rate: {metrics['fill_rate']:.2%}")

    assert metrics["total_tracked"] == 1, "Debe haber 1 orden trackeada"
    assert metrics["total_filled"] == 1, "Debe haber 1 orden filled"
    assert metrics["in_flight_orders"] == 0, "No debe haber órdenes en vuelo"
    assert metrics["completed_orders"] == 1, "Debe haber 1 orden completada"

    await connector.close()

    print("\n" + "=" * 80)
    print("✅ TEST PASSED: Order Tracking funciona correctamente")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_order_tracking())
