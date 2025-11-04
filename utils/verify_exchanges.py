import asyncio
import logging
from typing import List

from tables.ccxt_adapter import CCXTAdapter

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ExchangeVerifier")


async def test_exchange(exchange_id: str, symbols: List[str]):
    """Prueba la conexión, obtención de balance y ejecución de una orden de prueba."""
    logger.info(f"\n{'='*60}\n🔬 Probando Exchange: {exchange_id.upper()}\n{'='*60}")
    table = None
    try:
        # 1. Inicializar la mesa en modo Testnet
        # 1. Inicialización
        logger.info("1.1. Iniciando inicialización de CCXTAdapter...")
        table = CCXTAdapter(exchange_id=exchange_id, symbols=symbols, timeframe="1m", testnet=True)
        logger.info("1.2. ✅ CCXTAdapter inicializada.")

        # 2. Conexión
        logger.info("2.1. Iniciando table.connect()...")
        await table.connect()
        logger.info(f"2.2. ✅ Conexión a {exchange_id} completada.")

        # 3. Balance
        logger.info("3.1. Iniciando fetch_balance()...")
        balance = await table.exchange.fetch_balance()
        logger.info("3.2. ✅ Balance obtenido.")
        if not balance or not balance.get("total"):
            raise RuntimeError("El balance está vacío o no tiene el formato esperado.")

        base_currency = table.base_currency
        total_balance = balance.get(base_currency, {}).get("total", 0)
        logger.info(f"3.3. ✅ Balance procesado: {total_balance:.4f} {base_currency}")

        # 4. Orden de prueba
        logger.info("4.1. Iniciando creación de orden de prueba...")
        test_symbol = symbols[0]
        price = None
        if exchange_id == "hyperliquid":
            logger.info("4.2. Obteniendo precio de ticker para Hyperliquid...")
            ticker = await table.exchange.fetch_ticker(test_symbol)
            if ticker and "last" in ticker and ticker["last"] is not None:
                price = ticker["last"]
                logger.info(f"4.3. ✅ Precio de referencia para Hyperliquid: {price}")
            else:
                raise RuntimeError("No se pudo obtener el precio del ticker para Hyperliquid.")

        order_params = {
            "symbol": test_symbol,
            "type": "market",
            "side": "buy",
            "amount": 0.001,
            "price": price,  # Necesario para Hyperliquid
            "params": {"test": True},
        }

        logger.info("4.4. Enviando orden a través de la lógica de la mesa...")
        # Llamar al método de la mesa, no directamente a ccxt
        # Este método es síncrono, pero lo llamamos desde un contexto async
        # lo que es aceptable para esta prueba de diagnóstico.
        order_result = await table.async_execute_order(order_params)
        logger.info(f"✅ Orden de prueba ejecutada: {order_result['id']}")

        logger.info(f"\n{'='*25} 🎉 ÉXITO: {exchange_id.upper()} funciona correctamente {'='*25}")

    except Exception as e:
        logger.error(f"\n{'='*25} 🔥 FALLO: {exchange_id.upper()} no pasó la prueba {'='*25}")
        if "Wallet" in str(e) and "does not exist" in str(e):
            logger.error("Error: La wallet de Hyperliquid no existe o no está fondeada en el Testnet.")
            logger.warning("SOLUCIÓN: Visita https://app.hyperliquid-testnet.xyz/ y conecta tu wallet para activarla.")
        else:
            logger.error(f"Error: {e}", exc_info=True)
    finally:
        if table and table.exchange:
            await table.close()


async def main():
    """Punto de entrada principal para verificar todos los exchanges."""
    # Lista de exchanges y símbolos de prueba
    exchanges_to_test = [
        {"id": "binance", "symbols": ["BTC/USDT"]},
        {"id": "kraken", "symbols": ["BTC/USD:USD"]},  # Formato para Kraken Futures
        {"id": "hyperliquid", "symbols": ["BTC/USDC"]},
    ]

    for exchange_info in exchanges_to_test:
        await test_exchange(exchange_info["id"], exchange_info["symbols"])


if __name__ == "__main__":
    asyncio.run(main())
