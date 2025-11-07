"""
Script de prueba para validar create_order_with_tpsl() en KrakenConnector.

Este script:
1. Conecta a Kraken testnet
2. Obtiene precio actual de BTC/USD:USD
3. Crea una orden LONG con TP/SL muy narrow (40x leverage simulado)
4. Monitorea la posición hasta que cierre por TP o SL
"""

import asyncio
import logging

from exchanges.connectors import KrakenConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def test_tpsl_order():
    """Test create_order_with_tpsl with narrow TP/SL for quick execution."""

    connector = None

    try:
        # 1. Conectar a Kraken testnet
        logger.info("=" * 80)
        logger.info("🧪 TEST: create_order_with_tpsl() - Kraken Futures")
        logger.info("=" * 80)

        connector = KrakenConnector(testnet=True)
        await connector.connect()

        symbol = "BTC/USD:USD"

        # 2. Obtener precio actual
        logger.info(f"\n📊 Obteniendo precio actual de {symbol}...")
        ticker = await connector.fetch_ticker(symbol)
        current_price = ticker.get("last")

        logger.info(f"💰 Precio actual: ${current_price:,.2f}")

        # 3. Calcular TP/SL narrow (0.5% TP, 0.3% SL con 40x leverage simulado)
        # Con 40x leverage, 0.5% de movimiento = 20% de ganancia
        # Con 40x leverage, 0.3% de movimiento = 12% de pérdida
        tp_percent = 0.005  # 0.5%
        sl_percent = 0.003  # 0.3%

        tp_price = current_price * (1 + tp_percent)
        sl_price = current_price * (1 - sl_percent)

        logger.info("\n🎯 Configuración de orden:")
        logger.info("  Side: LONG (buy)")
        logger.info("  Amount: 0.001 BTC")
        logger.info(f"  Entry: ${current_price:,.2f}")
        logger.info(f"  TP: ${tp_price:,.2f} (+{tp_percent*100:.2f}%)")
        logger.info(f"  SL: ${sl_price:,.2f} (-{sl_percent*100:.2f}%)")
        logger.info("  Leverage simulado: 40x")

        # 4. Confirmar con usuario
        logger.info("\n⚠️  Esta orden se ejecutará en TESTNET (dinero virtual)")
        response = input("\n¿Proceder con la orden? (y/n): ").strip().lower()

        if response != "y":
            logger.info("❌ Orden cancelada por usuario")
            return

        # 5. Crear orden con TP/SL
        logger.info("\n🚀 Creando orden con TP/SL...")

        order_result = await connector.create_order_with_tpsl(
            symbol=symbol,
            side="buy",
            amount=0.001,
            price=None,  # Market order
            order_type="market",
            tp_price=tp_price,
            sl_price=sl_price,
            params={},
        )

        logger.info("\n✅ Orden principal creada:")
        logger.info(f"  ID: {order_result.get('id')}")
        logger.info(f"  Symbol: {order_result.get('symbol')}")
        logger.info(f"  Side: {order_result.get('side')}")
        logger.info(f"  Amount: {order_result.get('amount')}")
        logger.info(f"  Price: ${order_result.get('price', 0):,.2f}")
        logger.info(f"  Status: {order_result.get('status')}")

        # 6. Verificar posición abierta
        logger.info("\n📊 Verificando posición...")
        positions = await connector.fetch_positions()

        btc_position = None
        for pos in positions:
            if pos.get("symbol") == symbol:
                btc_position = pos
                break

        if btc_position:
            logger.info("✅ Posición encontrada:")
            logger.info(f"  Symbol: {btc_position.get('symbol')}")
            logger.info(f"  Side: {btc_position.get('side')}")
            logger.info(f"  Size: {btc_position.get('contracts', 0)}")
            logger.info(f"  Entry Price: ${btc_position.get('entryPrice', 0):,.2f}")
            logger.info(f"  Current Price: ${btc_position.get('markPrice', 0):,.2f}")
            logger.info(f"  PnL: ${btc_position.get('unrealizedPnl', 0):,.2f}")
        else:
            logger.warning("⚠️  Posición no encontrada (puede haberse cerrado inmediatamente)")

        # 7. Verificar órdenes abiertas (TP/SL)
        logger.info("\n📋 Verificando órdenes TP/SL...")
        open_orders = await connector.fetch_open_orders(symbol=symbol)

        if open_orders:
            logger.info(f"✅ {len(open_orders)} órdenes abiertas encontradas:")
            for order in open_orders:
                order_type = order.get("type", "unknown")
                trigger_price = order.get("triggerPrice") or order.get("stopPrice") or 0
                logger.info(f"  - {order_type.upper()}: ${trigger_price:,.2f} | Status: {order.get('status')}")
        else:
            logger.info("ℹ️  No hay órdenes TP/SL abiertas (pueden haberse ejecutado)")

        # 8. Monitorear posición
        logger.info("\n" + "=" * 80)
        logger.info("👀 MONITOREANDO POSICIÓN")
        logger.info("=" * 80)
        logger.info("Presiona Ctrl+C para detener el monitoreo\n")

        monitor_count = 0
        max_monitors = 60  # Máximo 5 minutos (60 * 5 segundos)

        while monitor_count < max_monitors:
            await asyncio.sleep(5)
            monitor_count += 1

            # Obtener precio actual
            ticker = await connector.fetch_ticker(symbol)
            current_price = ticker.get("last")

            # Obtener posición
            positions = await connector.fetch_positions()
            btc_position = None
            for pos in positions:
                if pos.get("symbol") == symbol:
                    btc_position = pos
                    break

            if not btc_position:
                logger.info("\n🎯 POSICIÓN CERRADA - TP o SL alcanzado!")

                # Verificar último trade para ver si fue TP o SL
                my_trades = await connector.fetch_my_trades(symbol=symbol, limit=5)
                if my_trades:
                    last_trade = my_trades[0]
                    exit_price = last_trade.get("price", 0)

                    if exit_price > order_result.get("price", 0):
                        logger.info(f"✅ TAKE PROFIT alcanzado @ ${exit_price:,.2f}")
                        profit = (exit_price - order_result.get("price", 0)) * 0.001
                        logger.info(f"💰 Ganancia: ${profit:,.2f}")
                    else:
                        logger.info(f"🛑 STOP LOSS alcanzado @ ${exit_price:,.2f}")
                        loss = (order_result.get("price", 0) - exit_price) * 0.001
                        logger.info(f"💸 Pérdida: ${loss:,.2f}")

                break

            # Mostrar estado actual
            entry_price = btc_position.get("entryPrice", 0)
            pnl = btc_position.get("unrealizedPnl", 0)
            pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price else 0

            # Calcular distancia a TP/SL
            distance_to_tp = ((tp_price - current_price) / current_price) * 100
            distance_to_sl = ((current_price - sl_price) / current_price) * 100

            logger.info(
                f"[{monitor_count:02d}] "
                f"Price: ${current_price:,.2f} | "
                f"PnL: ${pnl:+,.2f} ({pnl_percent:+.2f}%) | "
                f"TP: {distance_to_tp:+.3f}% | "
                f"SL: {distance_to_sl:+.3f}%"
            )

        if monitor_count >= max_monitors:
            logger.info("\n⏰ Tiempo de monitoreo agotado (5 minutos)")
            logger.info("La posición sigue abierta. Puedes cerrarla manualmente con closeall")

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Monitoreo interrumpido por usuario")

    except Exception as e:
        logger.error(f"\n❌ Error durante el test: {e}", exc_info=True)

    finally:
        # Cleanup
        if connector:
            logger.info("\n🔌 Cerrando conexión...")
            await connector.close()
            logger.info("✅ Conexión cerrada")

        logger.info("\n" + "=" * 80)
        logger.info("🏁 TEST COMPLETADO")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tpsl_order())
