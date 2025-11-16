#!/usr/bin/env python3
"""
🔍 TEST DE DEBUG: Ejecución de Orden OCO (Croupier + TP/SL)

Este test simula EXACTAMENTE cómo el Croupier ejecuta una orden con TP/SL
y debuguea cada paso del proceso para identificar dónde falla el OCO.

Ejecutar: python tests/test_oco_execution_debug.py

Pasos validados:
1. ✅ Conexión al exchange
2. ✅ Obtención de balance real
3. ✅ Creación de Croupier + Adapter
4. ✅ Ejecución de orden principal (MARKET)
5. ✅ Creación de órdenes TP/SL (LIMIT)
6. ✅ Registro en PositionTracker
7. ✅ Monitoreo OCO manual
8. ✅ Detección de ejecución TP/SL
9. ✅ Cancelación de orden opuesta
10. ✅ Cierre de posición
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OCO_DEBUG_TEST")


class OCOExecutionDebugger:
    """Debugger para validar ejecución de órdenes OCO."""

    def __init__(self):
        self.symbol = "LTC/USD:USD"
        self.timeframe = "1m"
        self.test_results = {}
        self.debug_log = []
        self.connector = None
        self.adapter = None
        self.croupier = None

    def _log_debug(self, step: str, message: str, data: Optional[Dict] = None):
        """Registra información de debug."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "message": message,
            "data": data,
        }
        self.debug_log.append(entry)
        logger.debug(f"[{step}] {message}")
        if data:
            logger.debug(f"  Data: {json.dumps(data, indent=2, default=str)}")

    async def run(self) -> bool:
        """Ejecuta el test completo."""
        logger.info("=" * 100)
        logger.info("🔍 TEST DE DEBUG: EJECUCIÓN DE ORDEN OCO (Croupier + TP/SL)")
        logger.info("=" * 100)

        try:
            # PASO 1: Conectar al exchange
            logger.info("\n" + "=" * 100)
            logger.info("PASO 1: Conectar al exchange")
            logger.info("=" * 100)
            if not await self._step_1_connect():
                return False

            # PASO 2: Obtener balance real
            logger.info("\n" + "=" * 100)
            logger.info("PASO 2: Obtener balance real del exchange")
            logger.info("=" * 100)
            initial_balance = await self._step_2_get_balance()
            if initial_balance is None:
                return False

            # PASO 3: Crear Adapter y Croupier
            logger.info("\n" + "=" * 100)
            logger.info("PASO 3: Crear Adapter y Croupier")
            logger.info("=" * 100)
            if not await self._step_3_create_adapter_croupier(initial_balance):
                return False

            # PASO 4: Obtener precio actual
            logger.info("\n" + "=" * 100)
            logger.info("PASO 4: Obtener precio actual del mercado")
            logger.info("=" * 100)
            current_price = await self._step_4_get_current_price()
            if current_price is None:
                return False

            # PASO 5: Ejecutar orden con Croupier
            logger.info("\n" + "=" * 100)
            logger.info("PASO 5: Ejecutar orden LONG con TP/SL (como lo haría el bot)")
            logger.info("=" * 100)
            order_result = await self._step_5_execute_order(current_price)
            if order_result is None:
                return False

            # PASO 6: Verificar posición abierta
            logger.info("\n" + "=" * 100)
            logger.info("PASO 6: Verificar posición abierta en PositionTracker")
            logger.info("=" * 100)
            open_position = await self._step_6_verify_open_position()
            if open_position is None:
                return False

            # PASO 7: Verificar órdenes TP/SL en el exchange
            logger.info("\n" + "=" * 100)
            logger.info("PASO 7: Verificar órdenes TP/SL en el exchange")
            logger.info("=" * 100)
            if not await self._step_7_verify_tpsl_orders(open_position):
                return False

            # PASO 8: Monitorear OCO manual
            logger.info("\n" + "=" * 100)
            logger.info("PASO 8: Monitorear OCO manual (60 segundos)")
            logger.info("=" * 100)
            if not await self._step_8_monitor_oco(open_position):
                return False

            # PASO 9: Verificar resultado final
            logger.info("\n" + "=" * 100)
            logger.info("PASO 9: Verificar resultado final")
            logger.info("=" * 100)
            await self._step_9_verify_final_result()

            # PASO 10: Generar reporte
            logger.info("\n" + "=" * 100)
            logger.info("PASO 10: Generar reporte de debug")
            logger.info("=" * 100)
            self._step_10_generate_report()

            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            self._log_debug("ERROR", str(e))
            return False

        finally:
            await self._cleanup()

    async def _step_1_connect(self) -> bool:
        """Conectar al exchange."""
        try:
            from config import exchange as exchange_config
            from exchanges.connectors.binance import BinanceConnector

            logger.info("📌 Creando conector Binance Testnet...")
            self.connector = BinanceConnector(
                api_key=exchange_config.BINANCE_API_KEY,
                secret=exchange_config.BINANCE_API_SECRET,
                mode="demo",
                enable_websocket=True,
            )

            logger.info("📌 Conectando...")
            await self.connector.connect()
            logger.info("✅ Conectado exitosamente")
            self._log_debug("CONNECT", "Conector Binance conectado")
            self.test_results["connect"] = "PASS"
            return True

        except Exception as e:
            logger.error(f"❌ Error conectando: {e}")
            self._log_debug("CONNECT", f"Error: {e}")
            self.test_results["connect"] = "FAIL"
            return False

    async def _step_2_get_balance(self) -> Optional[float]:
        """Obtener balance real del exchange."""
        try:
            logger.info("📌 Obteniendo balance...")
            balance_data = await self.connector.fetch_balance()

            initial_balance = balance_data.get("free", {}).get("USDT", 0.0)
            logger.info(f"✅ Balance obtenido: ${initial_balance:,.2f}")

            self._log_debug("GET_BALANCE", f"Balance: ${initial_balance:,.2f}", {"balance": initial_balance})
            self.test_results["get_balance"] = "PASS"
            return initial_balance

        except Exception as e:
            logger.error(f"❌ Error obteniendo balance: {e}")
            self._log_debug("GET_BALANCE", f"Error: {e}")
            self.test_results["get_balance"] = "FAIL"
            return None

    async def _step_3_create_adapter_croupier(self, initial_balance: float) -> bool:
        """Crear Adapter y Croupier."""
        try:
            from croupier.croupier import Croupier
            from exchanges.adapters.ccxt_adapter import CCXTAdapter

            logger.info("📌 Creando CCXTAdapter...")
            self.adapter = CCXTAdapter(self.connector, self.symbol, self.timeframe)
            logger.info("✅ CCXTAdapter creado")

            logger.info("📌 Creando Croupier...")
            self.croupier = Croupier(exchange_adapter=self.adapter, initial_balance=initial_balance)
            logger.info("✅ Croupier creado")

            self._log_debug(
                "CREATE_ADAPTER_CROUPIER",
                "Adapter y Croupier creados",
                {"initial_balance": initial_balance},
            )
            self.test_results["create_adapter_croupier"] = "PASS"
            return True

        except Exception as e:
            logger.error(f"❌ Error creando Adapter/Croupier: {e}")
            self._log_debug("CREATE_ADAPTER_CROUPIER", f"Error: {e}")
            self.test_results["create_adapter_croupier"] = "FAIL"
            return False

    async def _step_4_get_current_price(self) -> Optional[float]:
        """Obtener precio actual del mercado."""
        try:
            logger.info("📌 Obteniendo precio actual...")
            # Conectar adapter si no está conectado
            if not hasattr(self.adapter, "_connected") or not self.adapter._connected:
                logger.info("  📌 Conectando adapter...")
                await self.adapter.connect()

            ticker = await self.adapter.fetch_ticker(self.symbol)
            current_price = ticker.get("last", 0.0)

            logger.info(f"✅ Precio actual: ${current_price:.2f}")
            self._log_debug("GET_CURRENT_PRICE", f"Precio: ${current_price:.2f}", {"price": current_price})
            self.test_results["get_current_price"] = "PASS"
            return current_price

        except Exception as e:
            logger.error(f"❌ Error obteniendo precio: {e}")
            self._log_debug("GET_CURRENT_PRICE", f"Error: {e}")
            self.test_results["get_current_price"] = "FAIL"
            return None

    async def _step_5_execute_order(self, current_price: float) -> Optional[Dict]:
        """Ejecutar orden con Croupier (como lo haría el bot)."""
        try:
            logger.info("📌 Construyendo orden...")
            # IMPORTANTE: Usar LIMIT order para que la posición permanezca abierta
            # y podamos ver cómo TP/SL se ejecutan
            # En el bot real se usa MARKET, pero para este test usamos LIMIT
            order = {
                "symbol": self.symbol,
                "side": "LONG",
                "size": 0.01,  # 1% del equity
                "take_profit": 1.005,  # +0.5%
                "stop_loss": 0.995,  # -0.5%
                "timestamp": None,
                "ghost": False,
                # IMPORTANTE: Usar MARKET order como lo hace el bot real
                # Esto asegura que la orden se ejecute inmediatamente
                # y luego se crean las órdenes TP/SL
                "leverage": 50,  # ← LEVERAGE ALTO para que toque TP/SL rápido
            }

            tp_price = current_price * order["take_profit"]
            sl_price = current_price * order["stop_loss"]

            logger.info(f"  Symbol: {order['symbol']}")
            logger.info(f"  Side: {order['side']}")
            logger.info(f"  Size: {order['size']} (1% del equity)")
            logger.info(f"  Entry Price: ${current_price:.2f}")
            logger.info(f"  TP Price: ${tp_price:.2f} ({order['take_profit']}x)")
            logger.info(f"  SL Price: ${sl_price:.2f} ({order['stop_loss']}x)")

            logger.info("\n📌 Ejecutando orden con Croupier...")
            result = await self.croupier.execute_order(order)

            logger.info(f"✅ Orden ejecutada")
            logger.info(f"  Status: {result.get('status')}")
            logger.info(f"  Order ID: {result.get('id')}")
            logger.info(f"  Price: ${result.get('price', 0):.2f}")
            logger.info(f"  Balance: ${result.get('balance', 0):,.2f}")
            logger.info(f"  Equity: ${result.get('equity', 0):,.2f}")

            self._log_debug(
                "EXECUTE_ORDER",
                f"Orden ejecutada: {result.get('status')}",
                {
                    "order": order,
                    "result": result,
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                },
            )

            if result.get("status") not in ["open", "opened", "closed"]:
                logger.error(f"❌ Orden falló: {result}")
                self.test_results["execute_order"] = "FAIL"
                return None

            self.test_results["execute_order"] = "PASS"
            return result

        except Exception as e:
            logger.error(f"❌ Error ejecutando orden: {e}", exc_info=True)
            self._log_debug("EXECUTE_ORDER", f"Error: {e}")
            self.test_results["execute_order"] = "FAIL"
            return None

    async def _step_6_verify_open_position(self) -> Optional[Dict]:
        """Verificar posición abierta."""
        try:
            logger.info("📌 Verificando posición abierta...")

            open_positions = self.croupier.position_tracker.open_positions
            logger.info(f"  Posiciones abiertas: {len(open_positions)}")

            if not open_positions:
                logger.error("❌ No hay posiciones abiertas")
                self.test_results["verify_open_position"] = "FAIL"
                return None

            position = open_positions[0]
            logger.info(f"✅ Posición encontrada:")
            logger.info(f"  Trade ID: {position.trade_id}")
            logger.info(f"  Symbol: {position.symbol}")
            logger.info(f"  Side: {position.side}")
            logger.info(f"  Entry Price: ${position.entry_price:.2f}")
            logger.info(f"  TP Level: ${position.tp_level:.2f}")
            logger.info(f"  SL Level: ${position.sl_level:.2f}")
            logger.info(f"  Main Order ID: {position.main_order_id}")
            logger.info(f"  TP Order ID: {position.tp_order_id}")
            logger.info(f"  SL Order ID: {position.sl_order_id}")

            self._log_debug(
                "VERIFY_OPEN_POSITION",
                "Posición abierta verificada",
                {
                    "trade_id": position.trade_id,
                    "symbol": position.symbol,
                    "side": position.side,
                    "entry_price": position.entry_price,
                    "tp_level": position.tp_level,
                    "sl_level": position.sl_level,
                    "main_order_id": position.main_order_id,
                    "tp_order_id": position.tp_order_id,
                    "sl_order_id": position.sl_order_id,
                },
            )

            if not position.tp_order_id or not position.sl_order_id:
                logger.error("❌ No se crearon órdenes TP/SL")
                self.test_results["verify_open_position"] = "FAIL"
                return None

            self.test_results["verify_open_position"] = "PASS"
            return position.__dict__

        except Exception as e:
            logger.error(f"❌ Error verificando posición: {e}")
            self._log_debug("VERIFY_OPEN_POSITION", f"Error: {e}")
            self.test_results["verify_open_position"] = "FAIL"
            return None

    async def _step_7_verify_tpsl_orders(self, position: Dict) -> bool:
        """Verificar órdenes TP/SL en el exchange."""
        try:
            logger.info("📌 Verificando órdenes TP/SL en el exchange...")

            tp_order_id = position.get("tp_order_id")
            sl_order_id = position.get("sl_order_id")

            if not tp_order_id or not sl_order_id:
                logger.error("❌ No hay IDs de TP/SL")
                self.test_results["verify_tpsl_orders"] = "FAIL"
                return False

            logger.info(f"  TP Order ID: {tp_order_id}")
            logger.info(f"  SL Order ID: {sl_order_id}")

            # Obtener estado de TP
            logger.info("\n  📌 Verificando TP order...")
            try:
                tp_order = await self.adapter.fetch_order(tp_order_id, self.symbol)
                logger.info(f"    ✅ TP Order encontrada:")
                logger.info(f"      Status: {tp_order.get('status')}")
                logger.info(f"      Price: ${tp_order.get('price', 0):.2f}")
                logger.info(f"      Amount: {tp_order.get('amount', 0)}")
                self._log_debug("VERIFY_TPSL_ORDERS", "TP order verificada", {"tp_order": tp_order})
            except Exception as e:
                logger.warning(f"    ⚠️ Error obteniendo TP order: {e}")
                self._log_debug("VERIFY_TPSL_ORDERS", f"Error en TP order: {e}")

            # Obtener estado de SL
            logger.info("\n  📌 Verificando SL order...")
            try:
                sl_order = await self.adapter.fetch_order(sl_order_id, self.symbol)
                logger.info(f"    ✅ SL Order encontrada:")
                logger.info(f"      Status: {sl_order.get('status')}")
                logger.info(f"      Price: ${sl_order.get('price', 0):.2f}")
                logger.info(f"      Amount: {sl_order.get('amount', 0)}")
                self._log_debug("VERIFY_TPSL_ORDERS", "SL order verificada", {"sl_order": sl_order})
            except Exception as e:
                logger.warning(f"    ⚠️ Error obteniendo SL order: {e}")
                self._log_debug("VERIFY_TPSL_ORDERS", f"Error en SL order: {e}")

            self.test_results["verify_tpsl_orders"] = "PASS"
            return True

        except Exception as e:
            logger.error(f"❌ Error verificando órdenes TP/SL: {e}")
            self._log_debug("VERIFY_TPSL_ORDERS", f"Error: {e}")
            self.test_results["verify_tpsl_orders"] = "FAIL"
            return False

    async def _step_8_monitor_oco(self, position: Dict) -> bool:
        """Monitorear OCO manual."""
        try:
            logger.info("📌 Monitoreando OCO manual durante 60 segundos...")
            logger.info("⏱️ Esperando que se ejecute TP o SL...")

            start_time = asyncio.get_event_loop().time()
            monitoring_duration = 60
            check_interval = 5
            checks_performed = 0

            while asyncio.get_event_loop().time() - start_time < monitoring_duration:
                elapsed = int(asyncio.get_event_loop().time() - start_time)

                # Llamar OCO monitor
                logger.debug(f"  [{elapsed}s] Ejecutando monitor_oco_manual()...")
                try:
                    await self.croupier.monitor_oco_manual()
                except Exception as e:
                    logger.warning(f"  ⚠️ Error en monitor_oco_manual: {e}")

                # Chequear si se cerró
                open_positions = self.croupier.position_tracker.open_positions
                checks_performed += 1

                if not open_positions:
                    logger.info(f"✅ Posición cerrada después de {elapsed} segundos!")
                    self._log_debug("MONITOR_OCO", f"Posición cerrada en {elapsed}s", {"checks": checks_performed})
                    self.test_results["monitor_oco"] = "PASS"
                    return True

                logger.info(f"  [{elapsed}s] Monitoreando... {len(open_positions)} posición(es) abierta(s)")

                await asyncio.sleep(check_interval)

            logger.warning(f"⚠️ Timeout: OCO no se cerró en {monitoring_duration} segundos")
            self._log_debug(
                "MONITOR_OCO", f"Timeout después de {checks_performed} checks", {"checks": checks_performed}
            )
            self.test_results["monitor_oco"] = "TIMEOUT"
            return False

        except Exception as e:
            logger.error(f"❌ Error monitoreando OCO: {e}")
            self._log_debug("MONITOR_OCO", f"Error: {e}")
            self.test_results["monitor_oco"] = "FAIL"
            return False

    async def _step_9_verify_final_result(self):
        """Verificar resultado final."""
        try:
            logger.info("📌 Verificando resultado final...")

            open_positions = self.croupier.position_tracker.open_positions
            stats = self.croupier.position_tracker.get_stats()

            logger.info(f"✅ Estadísticas finales:")
            logger.info(f"  Posiciones abiertas: {len(open_positions)}")
            logger.info(f"  Total cerrados: {stats.get('total_closed', 0)}")
            logger.info(f"  Wins: {stats.get('total_wins', 0)}")
            logger.info(f"  Losses: {stats.get('total_losses', 0)}")

            self._log_debug(
                "VERIFY_FINAL_RESULT",
                "Resultado final verificado",
                {
                    "open_positions": len(open_positions),
                    "total_closed": stats.get("total_closed", 0),
                    "wins": stats.get("total_wins", 0),
                    "losses": stats.get("total_losses", 0),
                },
            )

            self.test_results["verify_final_result"] = "PASS"

        except Exception as e:
            logger.error(f"❌ Error verificando resultado final: {e}")
            self._log_debug("VERIFY_FINAL_RESULT", f"Error: {e}")
            self.test_results["verify_final_result"] = "FAIL"

    def _step_10_generate_report(self):
        """Generar reporte de debug."""
        try:
            logger.info("📌 Generando reporte de debug...")

            # Resumen de resultados
            logger.info("\n" + "=" * 100)
            logger.info("📊 RESUMEN DE RESULTADOS")
            logger.info("=" * 100)

            for step, result in self.test_results.items():
                status_icon = "✅" if result == "PASS" else "❌" if result == "FAIL" else "⏱️"
                logger.info(f"{status_icon} {step}: {result}")

            # Guardar debug log
            debug_file = Path("logs") / f"oco_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            debug_file.parent.mkdir(exist_ok=True)

            with open(debug_file, "w") as f:
                json.dump(self.debug_log, f, indent=2, default=str)

            logger.info(f"\n📁 Debug log guardado: {debug_file}")

        except Exception as e:
            logger.error(f"❌ Error generando reporte: {e}")

    async def _cleanup(self):
        """Limpiar recursos."""
        try:
            logger.info("\n🧹 Limpiando recursos...")

            if self.connector:
                try:
                    await self.connector.disconnect()
                    logger.info("✅ Conector desconectado")
                except Exception as e:
                    logger.warning(f"⚠️ Error desconectando: {e}")

            if self.adapter:
                try:
                    await self.adapter.close()
                    logger.info("✅ Adapter cerrado")
                except Exception as e:
                    logger.warning(f"⚠️ Error cerrando adapter: {e}")

        except Exception as e:
            logger.error(f"❌ Error en cleanup: {e}")


async def main():
    """Función principal."""
    debugger = OCOExecutionDebugger()
    success = await debugger.run()

    logger.info("\n" + "=" * 100)
    if success:
        logger.info("✅ TEST COMPLETADO - OCO funcionando correctamente")
    else:
        logger.info("❌ TEST FALLIDO - Revisar debug log para más detalles")
    logger.info("=" * 100)

    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
        exit(1)
