#!/usr/bin/env python3
"""
Test OCO Monitor - Versión simplificada que usa el mismo patrón que main.py

Ejecutar: .venv/bin/python tests/test_oco_monitor_simple.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("OCO_Monitor_Test")


async def main():
    """Test OCO Monitor"""
    logger.info("=" * 80)
    logger.info("🧪 OCO MONITOR TEST - Validar que OCO funciona en demo mode")
    logger.info("=" * 80)

    # Import aquí para evitar circular imports
    from config import exchange as exchange_config
    from croupier.croupier import Croupier
    from exchanges.adapters.ccxt_adapter import CCXTAdapter
    from exchanges.connectors.binance import BinanceConnector

    symbol = "LTC/USD:USD"
    timeframe = "1m"

    # 1. Crear conector
    logger.info("\n📌 Step 1: Crear conector Binance Testnet")
    connector = BinanceConnector(
        api_key=exchange_config.BINANCE_API_KEY,
        api_secret=exchange_config.BINANCE_API_SECRET,
        testnet=True,
        enable_websocket=True,
    )

    try:
        await connector.connect()
        logger.info("✅ Conector conectado")

        # 2. Obtener balance
        logger.info("\n📌 Step 2: Obtener balance inicial")
        balance_data = await connector.fetch_balance()
        initial_balance = balance_data.get("free", {}).get("USDT", 0.0)
        logger.info(f"💰 Balance inicial: ${initial_balance:,.2f}")

        # 3. Crear adapter y Croupier
        logger.info("\n📌 Step 3: Crear Adapter y Croupier")
        adapter = CCXTAdapter(connector, symbol, timeframe)
        croupier = Croupier(exchange_adapter=adapter, initial_balance=initial_balance)
        logger.info("✅ Adapter y Croupier creados")

        # 4. Obtener precio actual
        logger.info("\n📌 Step 4: Obtener precio actual del mercado")
        ticker = await adapter.fetch_ticker(symbol)
        current_price = ticker.get("last", 0.0)
        logger.info(f"📊 Precio actual: ${current_price:.2f}")

        # 5. Crear orden
        logger.info("\n📌 Step 5: Crear orden LONG con TP/SL")
        order = {
            "symbol": symbol,
            "side": "LONG",
            "size": 0.01,
            "take_profit": 1.005,
            "stop_loss": 0.995,
            "timestamp": None,
            "ghost": False,
        }

        logger.info(f"  Symbol: {order['symbol']}")
        logger.info(f"  Side: {order['side']}")
        logger.info(f"  Size: {order['size']}")
        logger.info(f"  TP: {order['take_profit']} (${current_price * order['take_profit']:.2f})")
        logger.info(f"  SL: {order['stop_loss']} (${current_price * order['stop_loss']:.2f})")

        result = await croupier.execute_order(order)
        logger.info(f"✅ Orden ejecutada: {result.get('status')}")
        logger.info(f"  Order ID: {result.get('id')}")
        logger.info(f"  Price: ${result.get('price', 0):.2f}")

        if result.get("status") not in ["open", "opened", "closed"]:
            logger.error(f"❌ Orden falló: {result}")
            return False

        # 6. Verificar posición
        logger.info("\n📌 Step 6: Verificar posición abierta")
        open_position = (
            croupier.position_tracker.open_positions[0] if croupier.position_tracker.open_positions else None
        )

        if not open_position:
            logger.error("❌ No se abrió posición")
            return False

        logger.info(f"✅ Posición abierta:")
        logger.info(f"  Trade ID: {open_position.trade_id}")
        logger.info(f"  Symbol: {open_position.symbol}")
        logger.info(f"  Side: {open_position.side}")
        logger.info(f"  Entry: ${open_position.entry_price:.2f}")
        logger.info(f"  TP Order ID: {open_position.tp_order_id}")
        logger.info(f"  SL Order ID: {open_position.sl_order_id}")

        if not open_position.tp_order_id or not open_position.sl_order_id:
            logger.error("❌ No se crearon órdenes TP/SL")
            return False

        # 7. Monitorear OCO
        logger.info("\n📌 Step 7: Monitorear OCO durante 120 segundos")
        logger.info("⏱️ Esperando que se ejecute TP o SL...")

        start_time = asyncio.get_event_loop().time()
        monitoring_duration = 120
        check_interval = 5

        while asyncio.get_event_loop().time() - start_time < monitoring_duration:
            # Llamar OCO monitor
            await croupier.monitor_oco_manual()

            # Chequear si se cerró
            open_positions = croupier.position_tracker.open_positions
            if not open_positions:
                logger.info("✅ Posición cerrada!")
                break

            elapsed = int(asyncio.get_event_loop().time() - start_time)
            logger.info(f"  [{elapsed}s] Monitoreando... {len(open_positions)} posición(es) abierta(s)")

            await asyncio.sleep(check_interval)

        # 8. Verificar resultado final
        logger.info("\n📌 Step 8: Verificar resultado final")
        open_positions = croupier.position_tracker.open_positions
        stats = croupier.position_tracker.get_stats()

        logger.info(f"📊 Estadísticas finales:")
        logger.info(f"  Posiciones abiertas: {len(open_positions)}")
        logger.info(f"  Wins: {stats.get('total_wins', 0)}")
        logger.info(f"  Losses: {stats.get('total_losses', 0)}")
        logger.info(f"  Total cerrados: {stats.get('total_closed', 0)}")

        if len(open_positions) == 0:
            logger.info("\n✅ OCO MONITOR FUNCIONA - Posición cerrada exitosamente!")
            return True
        else:
            logger.warning("\n⚠️ OCO Monitor NO cerró la posición (podría necesitar más tiempo o ejecución manual)")
            return False

    finally:
        logger.info("\n🧹 Cleanup...")
        try:
            await connector.disconnect()
            logger.info("✅ Conector desconectado")
        except Exception as e:
            logger.warning(f"⚠️ Error desconectando: {e}")


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        logger.info("\n" + "=" * 80)
        if success:
            logger.info("✅ TEST PASSED - OCO Monitor funciona correctamente")
        else:
            logger.info("❌ TEST FAILED - OCO Monitor no funcionó")
        logger.info("=" * 80)
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        exit(1)
