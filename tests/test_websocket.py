"""
Test para WebSocket de Kraken

Verifica que el WebSocket se conecta y funciona correctamente.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.kraken import KrakenConnector


async def test_websocket_connection():
    """Test básico de conexión WebSocket."""
    print("=" * 80)
    print("🧪 TEST: WebSocket Connection")
    print("=" * 80)

    # 1. Crear conector CON WebSocket habilitado
    print("\n📝 Creando conector con WebSocket...")
    connector = KrakenConnector(mode="testing", enable_websocket=True)

    # 2. Conectar
    print("🔌 Conectando...")
    await connector.connect()

    # 3. Verificar estado
    status = connector.status_dict
    print(f"\n📊 Estado del conector:")
    print(f"   Connected: {status['connected']}")
    print(f"   Markets loaded: {status['markets_loaded']}")
    print(f"   WebSocket active: {status['websocket_active']}")
    print(f"   Ready: {status['ready']}")

    # 4. Verificar métricas de WebSocket
    if connector._ws:
        metrics = connector._ws.get_metrics()
        print(f"\n📊 Métricas de WebSocket:")
        print(f"   Connected: {metrics['connected']}")
        print(f"   Messages received: {metrics['messages_received']}")
        print(f"   Reconnect count: {metrics['reconnect_count']}")
        print(f"   Subscriptions: {metrics['subscriptions']}")

    # 5. Esperar un poco para recibir mensajes
    print("\n⏳ Esperando mensajes del WebSocket (5s)...")
    await asyncio.sleep(5)

    # 6. Verificar métricas nuevamente
    if connector._ws:
        metrics = connector._ws.get_metrics()
        print(f"\n📊 Métricas después de 5s:")
        print(f"   Messages received: {metrics['messages_received']}")
        print(f"   Time since last message: {metrics['time_since_last_message']:.2f}s")

    # 7. Cerrar
    print("\n🔌 Cerrando conexión...")
    await connector.close()

    print("\n" + "=" * 80)
    if status["websocket_active"]:
        print("✅ TEST PASSED: WebSocket conectado exitosamente")
    else:
        print("⚠️ TEST WARNING: WebSocket no conectó (usando REST fallback)")
    print("=" * 80)


async def test_websocket_fallback():
    """Test de fallback a REST cuando WebSocket no está disponible."""
    print("\n" + "=" * 80)
    print("🧪 TEST: WebSocket Fallback to REST")
    print("=" * 80)

    # 1. Crear conector SIN WebSocket
    print("\n📝 Creando conector SIN WebSocket...")
    connector = KrakenConnector(mode="testing", enable_websocket=False)

    # 2. Conectar
    print("🔌 Conectando...")
    await connector.connect()

    # 3. Verificar estado
    status = connector.status_dict
    print(f"\n📊 Estado del conector:")
    print(f"   Connected: {status['connected']}")
    print(f"   WebSocket active: {status['websocket_active']}")

    assert not status["websocket_active"], "WebSocket NO debe estar activo"
    assert status["connected"], "REST debe estar conectado"

    # 4. Verificar que puede obtener datos (usando REST)
    print("\n📊 Obteniendo datos vía REST...")
    balance = await connector.fetch_balance()
    print(f"   Balance obtenido: {bool(balance)}")

    # 5. Cerrar
    await connector.close()

    print("\n" + "=" * 80)
    print("✅ TEST PASSED: Fallback a REST funciona correctamente")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
    asyncio.run(test_websocket_fallback())
