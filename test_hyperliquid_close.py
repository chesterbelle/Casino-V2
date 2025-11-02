"""
Script de prueba para verificar el cierre de posiciones en Hyperliquid.

Este script:
1. Se conecta a Hyperliquid Testnet
2. Abre una posición de prueba pequeña
3. Cierra la posición usando el método close_all_positions
4. Verifica que la posición se cerró correctamente
"""

import asyncio
import logging

from tables.table_ccxt_pro import TableCCXTPro

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HyperliquidTest")

# Configuración
SYMBOL = "BTC/USDC:USDC"
TEST_AMOUNT = 0.001  # Cantidad pequeña para pruebas


async def test_hyperliquid_close():
    """Prueba el cierre de posiciones en Hyperliquid."""
    table = None

    try:
        logger.info("🚀 Iniciando prueba de cierre de posiciones en Hyperliquid")

        # Inicializar la mesa de trading
        table = TableCCXTPro(exchange_id="hyperliquid", symbols=[SYMBOL], testnet=True)  # Usar testnet

        # Conectar al exchange
        logger.info("🔌 Conectando a Hyperliquid Testnet...")
        await table.connect()

        # Verificar conexión
        if not table.is_connected:
            raise Exception("No se pudo conectar al exchange")

        # Obtener balance inicial
        balance_before = await table.exchange.fetch_balance()
        logger.info(f"💰 Balance inicial: {balance_before['USDC']['free']:.4f} USDC")

        # Obtener el precio actual
        logger.info(f"🔍 Obteniendo precio actual para {SYMBOL}...")
        ticker = await table.exchange.fetch_ticker(SYMBOL)
        current_price = ticker["last"]
        logger.info(f"💵 Precio actual: {current_price}")

        # Calcular precio de compra (1% por encima para asegurar ejecución)
        buy_price = current_price * 1.01

        # Abrir posición de prueba (comprar) con orden limit
        logger.info(f"📈 Abriendo posición de prueba ({TEST_AMOUNT} {SYMBOL} @ {buy_price:.2f})...")
        order = await table.exchange.create_order(
            symbol=SYMBOL,
            type="limit",
            side="buy",
            amount=TEST_AMOUNT,
            price=buy_price,
            params={"timeInForce": "GTC"},  # Good Till Cancelled
        )

        logger.info(f"✅ Orden ejecutada: {order}")

        # Verificar que la posición se abrió
        positions = await table.exchange.fetch_positions([SYMBOL])
        open_positions = [p for p in positions if float(p["contracts"]) > 0]

        if not open_positions:
            raise Exception("No se pudo abrir la posición de prueba")

        logger.info(f"📊 Posición abierta: {open_positions[0]}")

        # Cerrar todas las posiciones
        logger.info("🔒 Cerrando todas las posiciones...")
        await table.close_all_positions()

        # Verificar que no hay posiciones abiertas
        positions = await table.exchange.fetch_positions([SYMBOL])
        open_positions = [p for p in positions if float(p["contracts"]) > 0]

        if open_positions:
            logger.error(f"❌ Error: Todavía hay posiciones abiertas: {open_positions}")
        else:
            logger.info("✅ Todas las posiciones cerradas correctamente")

        # Obtener balance final
        balance_after = await table.exchange.fetch_balance()
        logger.info(f"💰 Balance final: {balance_after['USDC']['free']:.4f} USDC")

        # Mostrar resumen
        logger.info("\n📊 Resumen de la prueba:")
        logger.info(f"- Balance inicial: {balance_before['USDC']['free']:.4f} USDC")
        logger.info(f"- Balance final:   {balance_after['USDC']['free']:.4f} USDC")
        logger.info("✅ Prueba completada exitosamente")

    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {e}", exc_info=True)
    finally:
        if table and hasattr(table, "disconnect"):
            logger.info("🔌 Desconectando del exchange...")
            await table.disconnect()

        # Cerrar el event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()


if __name__ == "__main__":
    asyncio.run(test_hyperliquid_close())
