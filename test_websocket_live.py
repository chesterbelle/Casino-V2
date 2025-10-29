#!/usr/bin/env python3
"""
Test script for TableCCXTPro WebSocket Integration with real data
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from tables.table_ccxt_pro import TableCCXTPro

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_websocket_connection():
    """Test WebSocket connection with real data."""

    # Configuration - Using Binance as it has better WebSocket support
    EXCHANGE = 'binance'  # Binance has better WebSocket support
    SYMBOLS = ['BTC/USDT', 'ETH/USDT']
    TIMEFRAME = '1m'
    TESTNET = True

    logger.info(f"🚀 Iniciando test WebSocket con {EXCHANGE}")
    logger.info(f"📊 Símbolos: {SYMBOLS}")
    logger.info(f"⏰ Timeframe: {TIMEFRAME}")

    # Create table instance
    table = TableCCXTPro(
        exchange_id=EXCHANGE,
        symbols=SYMBOLS,
        timeframe=TIMEFRAME,
        testnet=TESTNET
    )

    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("🛑 Señal de interrupción recibida, cerrando...")
        asyncio.create_task(table.disconnect())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Connect to WebSocket
        logger.info("🔌 Conectando a WebSocket...")
        await table.connect()

        # Start listening for data
        logger.info("👂 Iniciando escucha de datos...")
        listen_task = asyncio.create_task(table.start_listening())

        # Monitor data for 60 seconds
        logger.info("📈 Monitoreando datos por 60 segundos...")

        start_time = datetime.now()
        data_count = {symbol: 0 for symbol in SYMBOLS}

        while (datetime.now() - start_time).seconds < 60:
            await asyncio.sleep(5)  # Check every 5 seconds

            # Get current state
            state = table.get_state()
            websocket_info = state.get('websocket', {})

            # Count data updates
            last_candles = state.get('last_candles', {})
            for symbol in SYMBOLS:
                if symbol in last_candles and last_candles[symbol]:
                    data_count[symbol] += 1

            # Log status
            elapsed = (datetime.now() - start_time).seconds
            logger.info(f"📊 Estado {elapsed}s: Conectado={websocket_info.get('connected', False)}, "
                       f"Streams={websocket_info.get('active_streams', 0)}, "
                       f"Datos={websocket_info.get('symbols_with_data', 0)}, "
                       f"Updates={dict(data_count)}")

            # Show sample data
            for symbol in SYMBOLS:
                candle = table.next_candle(symbol)
                if candle:
                    logger.info(f"💎 {symbol}: ${candle['close']:.2f} (vol: {candle['volume']:.4f})")

        # Stop listening
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass

        logger.info("✅ Test completado exitosamente")

        # Final statistics
        total_updates = sum(data_count.values())
        logger.info(f"📈 Estadísticas finales:")
        logger.info(f"   - Total updates: {total_updates}")
        logger.info(f"   - Updates por símbolo: {data_count}")
        logger.info(f"   - Promedio por símbolo: {total_updates / len(SYMBOLS) if SYMBOLS else 0:.1f}")

    except Exception as e:
        logger.error(f"❌ Error durante el test: {e}")
        raise
    finally:
        # Ensure disconnection
        try:
            await table.disconnect()
            logger.info("🔌 Desconectado correctamente")
        except Exception as e:
            logger.error(f"❌ Error al desconectar: {e}")


async def test_multi_symbol_concurrent():
    """Test concurrent multi-symbol data processing."""

    logger.info("🧪 Probando procesamiento multi-símbolo concurrente...")

    # Test with more symbols
    SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'LTC/USDT']
    table = TableCCXTPro(
        exchange_id='binance',
        symbols=SYMBOLS,
        timeframe='1m',
        testnet=True
    )

    try:
        await table.connect()
        listen_task = asyncio.create_task(table.start_listening())

        # Monitor for 30 seconds
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < 30:
            await asyncio.sleep(10)

            state = table.get_state()
            logger.info(f"📊 Multi-symbol estado: {state.get('websocket', {})}")

            # Show data for all symbols
            for symbol in SYMBOLS:
                candle = table.next_candle(symbol)
                if candle:
                    logger.info(f"💎 {symbol}: ${candle['close']:.2f}")

        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass

    finally:
        await table.disconnect()


def main():
    """Main function."""
    print("🎯 Test WebSocket TableCCXTPro con Datos Reales")
    print("=" * 50)

    try:
        # Test basic WebSocket connection
        asyncio.run(test_websocket_connection())

        print("\n" + "=" * 50)
        print("🧪 Probando multi-símbolo...")

        # Test multi-symbol concurrent processing
        asyncio.run(test_multi_symbol_concurrent())

        print("\n" + "=" * 50)
        print("✅ Todos los tests WebSocket pasaron exitosamente!")

    except KeyboardInterrupt:
        print("\n🛑 Test interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error durante los tests: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()