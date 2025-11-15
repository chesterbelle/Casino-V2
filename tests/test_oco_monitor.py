"""
Test OCO Monitor - Verificar que el OCO manual funciona correctamente en demo mode

Este es el test más importante para validar que el bot funciona end-to-end:
1. Crear una orden a través del Croupier
2. Verificar que se crean órdenes TP/SL
3. Monitorear si el OCO se ejecuta correctamente
4. Verificar que la posición se cierra con TP o SL
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set PYTHONPATH
os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent)

# Import after path is set
from config import exchange as exchange_config
from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.binance import BinanceConnector

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OCOMonitorTest:
    """Test para validar OCO Monitor en demo mode"""

    def __init__(self):
        self.connector: Optional[BinanceConnector] = None
        self.adapter: Optional[CCXTAdapter] = None
        self.croupier: Optional[Croupier] = None
        self.symbol = "LTC/USD:USD"
        self.timeframe = "1m"

    async def setup(self):
        """Inicializar conexiones"""

        logger.info("=" * 80)
        logger.info("🧪 OCO MONITOR TEST - Setup")
        logger.info("=" * 80)

        # Crear conector
        self.connector = BinanceConnector(
            api_key=exchange_config.BINANCE_API_KEY,
            api_secret=exchange_config.BINANCE_API_SECRET,
            testnet=True,
            enable_websocket=True,  # CRÍTICO: WebSocket para OCO manual
        )

        # Conectar
        await self.connector.connect()
        logger.info("✅ Connector connected")

        # Obtener balance
        balance_data = await self.connector.fetch_balance()
        initial_balance = balance_data.get("free", {}).get("USDT", 0.0)
        logger.info(f"💰 Initial balance: ${initial_balance:,.2f}")

        # Crear adapter
        self.adapter = CCXTAdapter(self.connector, self.symbol, self.timeframe)
        logger.info("✅ Adapter created")

        # Crear Croupier
        self.croupier = Croupier(exchange_adapter=self.adapter, initial_balance=initial_balance)
        logger.info("✅ Croupier created")

    async def cleanup(self):
        """Limpiar conexiones"""
        logger.info("\n🧹 Cleanup...")
        try:
            if self.connector:
                await self.connector.disconnect()
                logger.info("✅ Connector disconnected")
        except Exception as e:
            logger.warning(f"⚠️ Error disconnecting: {e}")

    async def test_oco_execution(self):
        """
        Test principal: Crear orden y monitorear OCO

        Flujo:
        1. Crear orden LONG con TP/SL
        2. Verificar que se crean órdenes TP/SL
        3. Monitorear OCO durante 2 minutos
        4. Verificar que la posición se cierra
        """
        logger.info("\n" + "=" * 80)
        logger.info("🎯 TEST: OCO Execution")
        logger.info("=" * 80)

        # Obtener precio actual
        ticker = await self.adapter.fetch_ticker(self.symbol)
        current_price = ticker.get("last", 0.0)
        logger.info(f"📊 Current price: ${current_price:.2f}")

        # Crear orden
        order = {
            "symbol": self.symbol,
            "side": "LONG",
            "size": 0.01,  # 1% del equity
            "take_profit": 1.005,  # +0.5%
            "stop_loss": 0.995,  # -0.5%
            "timestamp": None,
            "ghost": False,
        }

        logger.info(f"\n📝 Creating order:")
        logger.info(f"  Symbol: {order['symbol']}")
        logger.info(f"  Side: {order['side']}")
        logger.info(f"  Size: {order['size']}")
        logger.info(f"  TP: {order['take_profit']} (${current_price * order['take_profit']:.2f})")
        logger.info(f"  SL: {order['stop_loss']} (${current_price * order['stop_loss']:.2f})")

        # Ejecutar orden
        result = await self.croupier.execute_order(order)
        logger.info(f"\n✅ Order executed: {result.get('status')}")
        logger.info(f"  Order ID: {result.get('id')}")
        logger.info(f"  Price: ${result.get('price', 0):.2f}")

        if result.get("status") not in ["open", "opened", "closed"]:
            logger.error(f"❌ Order failed: {result}")
            return False

        # Verificar posiciones abiertas
        positions = await self.adapter.fetch_positions([self.symbol])
        logger.info(f"\n📊 Open positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos.get('symbol')}: {pos.get('contracts')} @ ${pos.get('entry_price', 0):.2f}")

        if not positions:
            logger.error("❌ No positions opened")
            return False

        # Verificar que se registraron órdenes TP/SL
        open_position = (
            self.croupier.position_tracker.open_positions[0] if self.croupier.position_tracker.open_positions else None
        )
        if not open_position:
            logger.error("❌ No position tracked")
            return False

        logger.info(f"\n📍 Position tracked:")
        logger.info(f"  Trade ID: {open_position.trade_id}")
        logger.info(f"  Symbol: {open_position.symbol}")
        logger.info(f"  Side: {open_position.side}")
        logger.info(f"  Entry: ${open_position.entry_price:.2f}")
        logger.info(f"  TP Order ID: {open_position.tp_order_id}")
        logger.info(f"  SL Order ID: {open_position.sl_order_id}")

        if not open_position.tp_order_id or not open_position.sl_order_id:
            logger.error("❌ TP/SL orders not created")
            return False

        # Monitorear OCO durante 2 minutos
        logger.info(f"\n⏱️ Monitoring OCO for 120 seconds...")
        start_time = asyncio.get_event_loop().time()
        monitoring_duration = 120  # 2 minutos
        check_interval = 5  # Chequear cada 5 segundos

        while asyncio.get_event_loop().time() - start_time < monitoring_duration:
            # Llamar OCO monitor
            await self.croupier.monitor_oco_manual()

            # Chequear si la posición se cerró
            open_positions = self.croupier.position_tracker.open_positions
            if not open_positions:
                logger.info(f"✅ Position closed!")
                break

            # Mostrar progreso
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            logger.debug(f"  [{elapsed}s] Monitoring... {len(open_positions)} position(s) open")

            await asyncio.sleep(check_interval)

        # Verificar resultado final
        open_positions = self.croupier.position_tracker.open_positions
        stats = self.croupier.position_tracker.get_stats()

        logger.info(f"\n📊 Final stats:")
        logger.info(f"  Open positions: {len(open_positions)}")
        logger.info(f"  Wins: {stats.get('total_wins', 0)}")
        logger.info(f"  Losses: {stats.get('total_losses', 0)}")
        logger.info(f"  Total closed: {stats.get('total_closed', 0)}")

        if len(open_positions) == 0:
            logger.info("✅ OCO Monitor WORKS - Position closed successfully!")
            return True
        else:
            logger.warning("⚠️ OCO Monitor did NOT close position (might need more time or manual execution)")
            # Forzar cierre para cleanup
            logger.info("🧹 Force-closing position for cleanup...")
            try:
                await self.croupier.position_tracker.force_close_all_positions({"close": current_price})
            except Exception as e:
                logger.warning(f"⚠️ Error force-closing: {e}")
            return False

    async def run(self):
        """Ejecutar test completo"""
        try:
            await self.setup()
            success = await self.test_oco_execution()

            logger.info("\n" + "=" * 80)
            if success:
                logger.info("✅ OCO MONITOR TEST PASSED")
            else:
                logger.info("❌ OCO MONITOR TEST FAILED")
            logger.info("=" * 80)

            return success
        finally:
            await self.cleanup()


async def main():
    """Entry point"""
    test = OCOMonitorTest()
    success = await test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
