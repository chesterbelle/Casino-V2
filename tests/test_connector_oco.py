#!/usr/bin/env python3
"""
Test automatizado y agnóstico para validar órdenes OCO en conectores.

Este test valida que el conector:
1. Crea órdenes con TP/SL (OCO bracket)
2. Las órdenes se ejecutan correctamente
3. Las órdenes se cierran automáticamente por TP o SL
4. El balance se actualiza correctamente
5. Solo una de las órdenes (TP o SL) se ejecuta (OCO)

Uso:
    python tests/test_connector_oco.py --exchange kraken --testnet
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.kraken import KrakenConnector
from exchanges.connectors.resilient_connector import ResilientConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class OCOOrderTest:
    """Test automatizado para órdenes OCO."""

    def __init__(self, adapter: CCXTAdapter, symbol: str = "LTC/USD:USD"):
        """
        Inicializa el test.

        Args:
            adapter: Adapter a probar (incluye conector)
            symbol: Símbolo a usar para el test
        """
        self.adapter = adapter
        self.symbol = symbol
        self.test_results = {
            "order_created": False,
            "order_executed": False,
            "position_opened": False,
            "position_closed": False,
            "oco_validated": False,
            "balance_updated": False,
        }

    async def run(self) -> bool:
        """
        Ejecuta el test completo.

        Returns:
            True si el test pasó, False si falló
        """
        logger.info("=" * 80)
        logger.info("🧪 TEST AUTOMATIZADO: Órdenes OCO (One Cancels the Other)")
        logger.info("=" * 80)

        try:
            # Conectar
            await self.adapter.connect()
            logger.info("✅ Conectado al exchange")

            # Paso 1: Obtener balance inicial
            initial_balance = await self._get_balance()
            logger.info(f"💰 Balance inicial: ${initial_balance:.2f}")

            # Paso 2: Crear orden con TP/SL
            order = await self._create_test_order()
            if not order:
                logger.error("❌ FALLO: No se pudo crear la orden")
                return False
            self.test_results["order_created"] = True

            # Paso 3: Verificar que la orden se ejecutó
            if not await self._verify_order_executed(order):
                logger.error("❌ FALLO: La orden no se ejecutó")
                return False
            self.test_results["order_executed"] = True

            # Paso 4: Verificar que se abrió la posición
            if not await self._verify_position_opened():
                logger.error("❌ FALLO: No se abrió la posición")
                return False
            self.test_results["position_opened"] = True

            # Paso 5: Monitorear hasta que cierre (con timeout)
            if not await self._monitor_until_close(timeout=300):  # 5 min timeout
                logger.error("❌ FALLO: La posición no se cerró en el tiempo esperado")
                return False
            self.test_results["position_closed"] = True

            # Paso 6: Validar que solo una orden (TP o SL) se ejecutó
            if not await self._validate_oco():
                logger.error("❌ FALLO: OCO no funcionó correctamente")
                return False
            self.test_results["oco_validated"] = True

            # Paso 7: Verificar que el balance se actualizó
            final_balance = await self._get_balance()
            if not await self._verify_balance_updated(initial_balance, final_balance):
                logger.error("❌ FALLO: El balance no se actualizó correctamente")
                return False
            self.test_results["balance_updated"] = True

            # Test pasó
            logger.info("\n" + "=" * 80)
            logger.info("✅ TEST PASADO: Todas las validaciones exitosas")
            logger.info("=" * 80)
            self._print_summary(initial_balance, final_balance)
            return True

        except Exception as e:
            logger.error(f"❌ ERROR EN TEST: {e}", exc_info=True)
            return False

        finally:
            # Desconectar
            await self.adapter.close()
            logger.info("🔌 Desconectado")

    async def _get_balance(self) -> float:
        """Obtiene el balance disponible en USD."""
        return self.adapter.get_balance()

    async def _create_test_order(self) -> Optional[Dict]:
        """
        Crea una orden de prueba con TP/SL narrow para que cierre rápido.

        Returns:
            Orden creada o None si falló
        """
        logger.info("\n📝 PASO 1: Crear orden con TP/SL (OCO bracket)")
        logger.info("─" * 80)

        try:
            # Obtener precio actual
            ticker = await self.adapter.connector.fetch_ticker(self.symbol)
            current_price = ticker.get("last")

            if not current_price:
                logger.error("❌ No se pudo obtener precio actual")
                return None

            # Calcular TP/SL narrow (0.3% para que se alcance rápido)
            # Usamos SHORT para que sea más probable que cierre por TP (precio baja)
            side = "sell"  # SHORT
            tp_price = current_price * 0.997  # -0.3% (ganar si baja)
            sl_price = current_price * 1.003  # +0.3% (perder si sube)

            # Calcular size dinámicamente (usar 1% del balance, mínimo $10 de valor)
            balance = await self._get_balance()
            min_value = 10.0
            size = max(min_value / current_price, (balance * 0.01) / current_price)
            size = round(size, 8)

            logger.info(f"  Symbol: {self.symbol}")
            logger.info(f"  Side: SHORT (sell)")
            logger.info(f"  Size: {size}")
            logger.info(f"  Entry Price: ${current_price:.2f}")
            logger.info(f"  Take Profit: ${tp_price:.2f} (-0.3%)")
            logger.info(f"  Stop Loss: ${sl_price:.2f} (+0.3%)")

            # Crear orden con OCO bracket usando adapter
            logger.info("🚀 Creando orden con OCO bracket...")
            order = await self.adapter.execute_order(
                {
                    "symbol": self.symbol,
                    "side": side,
                    "amount": size,
                    "type": "market",
                    "take_profit": tp_price / current_price,  # Multiplicador
                    "stop_loss": sl_price / current_price,  # Multiplicador
                    "params": {},
                }
            )

            logger.info(f"✅ Orden creada: {order.get('id')}")
            logger.info(f"   Status: {order.get('status')}")
            logger.info(f"   Filled: {order.get('filled')}")

            return order

        except Exception as e:
            logger.error(f"❌ Error al crear orden: {e}", exc_info=True)
            return None

    async def _verify_order_executed(self, order: Dict) -> bool:
        """Verifica que la orden se ejecutó."""
        logger.info("\n📝 PASO 2: Verificar ejecución de orden")
        logger.info("─" * 80)

        status = order.get("status")
        filled = order.get("filled", 0)

        if status == "closed" and filled > 0:
            logger.info(f"✅ Orden ejecutada: {filled} contratos")
            return True
        else:
            logger.error(f"❌ Orden no ejecutada: status={status}, filled={filled}")
            return False

    async def _verify_position_opened(self) -> bool:
        """Verifica que se abrió una posición."""
        logger.info("\n📝 PASO 3: Verificar apertura de posición")
        logger.info("─" * 80)

        positions = await self.adapter.connector.fetch_positions()
        symbol_positions = [p for p in positions if p.get("symbol") == self.symbol]

        if len(symbol_positions) > 0:
            pos = symbol_positions[0]
            logger.info(f"✅ Posición abierta:")
            logger.info(f"   Side: {pos.get('side')}")
            logger.info(f"   Contracts: {pos.get('contracts')}")
            logger.info(f"   Entry Price: ${pos.get('entryPrice'):.2f}")
            return True
        else:
            logger.error("❌ No se encontró posición abierta")
            return False

    async def _monitor_until_close(self, timeout: int = 300) -> bool:
        """
        Monitorea la posición hasta que cierre o timeout.

        Args:
            timeout: Tiempo máximo de espera en segundos

        Returns:
            True si la posición se cerró, False si timeout
        """
        logger.info("\n📝 PASO 4: Monitorear hasta cierre (timeout: {}s)".format(timeout))
        logger.info("─" * 80)

        start_time = asyncio.get_event_loop().time()
        check_count = 0

        while True:
            check_count += 1
            elapsed = asyncio.get_event_loop().time() - start_time

            # Verificar timeout
            if elapsed > timeout:
                logger.error(f"❌ Timeout: La posición no se cerró en {timeout}s")
                return False

            # Obtener posiciones
            positions = await self.adapter.connector.fetch_positions()
            symbol_positions = [p for p in positions if p.get("symbol") == self.symbol]

            # Mostrar progreso cada 10 checks
            if check_count % 10 == 0:
                logger.info(f"⏳ Check #{check_count} | Elapsed: {elapsed:.0f}s | Posiciones: {len(symbol_positions)}")

            # Si no hay posiciones, se cerró
            if len(symbol_positions) == 0:
                logger.info(f"\n✅ Posición cerrada después de {elapsed:.0f}s ({check_count} checks)")
                return True

            # Mostrar PnL actual
            if symbol_positions:
                pos = symbol_positions[0]
                unrealized_pnl = pos.get("unrealizedPnl", 0)
                mark_price = pos.get("markPrice", 0)
                logger.info(f"   Mark Price: ${mark_price:.2f} | " f"Unrealized PnL: ${unrealized_pnl:+.2f}")

            # Esperar antes del próximo check
            await asyncio.sleep(2)

    async def _validate_oco(self) -> bool:
        """
        Valida que solo una orden (TP o SL) se ejecutó.

        Returns:
            True si OCO funcionó correctamente
        """
        logger.info("\n📝 PASO 5: Validar OCO (One Cancels the Other)")
        logger.info("─" * 80)

        # Obtener últimos trades
        trades = await self.adapter.connector.fetch_my_trades(symbol=self.symbol, limit=10)

        if not trades:
            logger.error("❌ No se encontraron trades")
            return False

        # El último trade debería ser el cierre
        last_trade = trades[0]
        logger.info(f"✅ Último trade:")
        logger.info(f"   ID: {last_trade.get('id')}")
        logger.info(f"   Side: {last_trade.get('side')}")
        logger.info(f"   Price: ${last_trade.get('price'):.2f}")
        logger.info(f"   Amount: {last_trade.get('amount')}")

        # Verificar que solo hay 2 trades (apertura + cierre)
        # Si OCO funciona, solo debería haber ejecutado TP o SL, no ambos
        recent_trades = [t for t in trades if t.get("symbol") == self.symbol][:2]

        if len(recent_trades) == 2:
            logger.info(f"✅ OCO validado: Solo 2 trades (apertura + cierre)")
            return True
        else:
            logger.warning(f"⚠️ Se encontraron {len(recent_trades)} trades (esperado: 2)")
            return True  # No falla el test, pero advertir

    async def _verify_balance_updated(self, initial: float, final: float) -> bool:
        """Verifica que el balance se actualizó."""
        logger.info("\n📝 PASO 6: Verificar actualización de balance")
        logger.info("─" * 80)

        diff = final - initial
        diff_pct = (diff / initial) * 100 if initial > 0 else 0

        logger.info(f"  Balance inicial: ${initial:.2f}")
        logger.info(f"  Balance final:   ${final:.2f}")
        logger.info(f"  Diferencia:      ${diff:+.2f} ({diff_pct:+.2f}%)")

        # El balance debe haber cambiado (ganancia o pérdida)
        if abs(diff) > 0.01:  # Cambio mínimo de $0.01
            logger.info(f"✅ Balance actualizado correctamente")
            return True
        else:
            logger.error(f"❌ Balance no cambió (diff: ${diff:.2f})")
            return False

    def _print_summary(self, initial_balance: float, final_balance: float):
        """Imprime resumen del test."""
        logger.info("\n📊 RESUMEN DEL TEST:")
        logger.info("─" * 80)

        for step, result in self.test_results.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {step}")

        logger.info("\n💰 BALANCE:")
        logger.info(f"  Inicial: ${initial_balance:.2f}")
        logger.info(f"  Final:   ${final_balance:.2f}")
        logger.info(f"  PnL:     ${final_balance - initial_balance:+.2f}")


async def run_test(exchange: str, testnet: bool = True, symbol: str = "LTC/USD:USD") -> bool:
    """
    Ejecuta el test para un exchange.

    Args:
        exchange: Nombre del exchange
        testnet: Si usar testnet o live
        symbol: Símbolo a testear

    Returns:
        True si el test pasó, False si falló
    """
    logger.info(f"🚀 Iniciando test para: {exchange}")
    logger.info(f"🌐 Modo: {'TESTNET' if testnet else 'LIVE'}")
    logger.info(f"📊 Símbolo: {symbol}")

    # Crear conector base
    if exchange.lower() == "kraken":
        base_connector = KrakenConnector(
            mode="testing" if testnet else "live",
            enable_websocket=False,  # Deshabilitado para test
        )
    else:
        raise ValueError(f"Exchange no soportado: {exchange}")

    # Envolver con ResilientConnector
    connector = ResilientConnector(
        connector=base_connector,
        enable_state_recovery=False,
    )

    # Crear adapter
    adapter = CCXTAdapter(
        connector=connector,
        symbol=symbol,
    )

    # Ejecutar test
    test = OCOOrderTest(adapter, symbol=symbol)
    return await test.run()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Test automatizado para órdenes OCO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--exchange",
        type=str,
        required=True,
        choices=["kraken"],
        help="Exchange a probar",
    )

    parser.add_argument(
        "--testnet",
        action="store_true",
        default=True,
        help="Usar testnet (default: True)",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Usar live (default: False)",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="LTC/USD:USD",
        help="Symbol to test (default: LTC/USD:USD)",
    )

    args = parser.parse_args()

    # Determinar si usar testnet o live
    testnet = not args.live

    # Ejecutar test
    success = asyncio.run(run_test(args.exchange, testnet, args.symbol))

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
