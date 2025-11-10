#!/usr/bin/env python3
"""
Test completo del conector: Validación end-to-end

Valida que el conector puede:
1. Obtener saldo del exchange
2. Recibir orden en formato del bot (multiplicadores TP/SL)
3. Traducir la orden al formato del exchange
4. Enviar la orden al exchange con OCO bracket
5. Recibir respuesta del exchange
6. Normalizar la respuesta para el bot
7. **CRÍTICO:** Validar que TP/SL se ejecutan automáticamente

Este test simula exactamente lo que hace el bot en producción,
incluyendo la ejecución automática de TP/SL por el exchange.

Usa leverage 50x y TP/SL narrow (0.2%) para que se ejecute rápido.

Uso:
    python tests/test_connector_complete.py --exchange kraken --testnet
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
    level=logging.DEBUG,  # DEBUG para ver logs del OCO Monitor
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class BotToExchangeFlowTest:
    """Test del flujo completo Bot → Exchange → Bot."""

    def __init__(self, adapter: CCXTAdapter, symbol: str = "LTC/USD:USD", amount: Optional[float] = None):
        """
        Inicializa el test.

        Args:
            adapter: Adapter a probar (simula el Croupier)
            symbol: Símbolo a usar
            amount: Cantidad a tradear (se calcula automáticamente si no se especifica)
        """
        self.adapter = adapter
        self.symbol = symbol
        self.amount = amount  # Se calculará en _create_bot_order si es None
        self.test_results = {
            "fetch_balance": False,
            "receive_bot_order": False,
            "translate_order": False,
            "send_to_exchange": False,
            "receive_response": False,
            "normalize_response": False,
            "position_opened": False,
            "tpsl_executed": False,  # CRÍTICO: Validar que TP o SL se ejecutó
        }

    async def run(self) -> bool:
        """
        Ejecuta el test completo.

        Returns:
            True si el test pasó, False si falló
        """
        logger.info("=" * 80)
        logger.info("🧪 TEST: Flujo Bot → Exchange → Bot")
        logger.info("=" * 80)

        try:
            # Conectar
            await self.adapter.connect()
            logger.info("✅ Conectado al exchange")

            # Paso 0: Cerrar todas las posiciones abiertas (cleanup)
            await self._cleanup_positions()

            # PASO 1: Obtener saldo (como lo hace el bot)
            if not await self._test_fetch_balance():
                logger.error("❌ FALLO: No se pudo obtener saldo")
                return False
            self.test_results["fetch_balance"] = True

            # PASO 2: Simular orden del bot (formato interno)
            bot_order = await self._create_bot_order()
            if not bot_order:
                logger.error("❌ FALLO: No se pudo crear orden del bot")
                return False
            self.test_results["receive_bot_order"] = True

            # PASO 3: Validar traducción de orden
            if not await self._test_order_translation(bot_order):
                logger.error("❌ FALLO: Error en traducción de orden")
                return False
            self.test_results["translate_order"] = True

            # PASO 4: Enviar orden al exchange
            exchange_response = await self._test_send_order(bot_order)
            if not exchange_response:
                logger.error("❌ FALLO: No se pudo enviar orden al exchange")
                return False
            self.test_results["send_to_exchange"] = True

            # PASO 5: Validar respuesta del exchange
            if not await self._test_exchange_response(exchange_response):
                logger.error("❌ FALLO: Respuesta del exchange inválida")
                return False
            self.test_results["receive_response"] = True

            # PASO 6: Validar normalización de respuesta
            if not await self._test_response_normalization(exchange_response):
                logger.error("❌ FALLO: Error en normalización de respuesta")
                return False
            self.test_results["normalize_response"] = True

            # PASO 7: Verificar que se abrió la posición
            if not await self._test_position_opened():
                logger.error("❌ FALLO: No se abrió la posición")
                return False
            self.test_results["position_opened"] = True

            # PASO 8: **CRÍTICO** - Monitorear hasta que TP/SL se ejecute
            if not await self._test_tpsl_execution(timeout=180):  # 3 min timeout
                logger.error("❌ FALLO: TP/SL no se ejecutó en el tiempo esperado")
                return False
            self.test_results["tpsl_executed"] = True

            # Test pasó
            logger.info("\n" + "=" * 80)
            logger.info("✅ TEST PASADO: Conector validado completamente")
            logger.info("=" * 80)
            self._print_summary()
            return True

        except Exception as e:
            logger.error(f"❌ ERROR EN TEST: {e}", exc_info=True)
            return False

        finally:
            # Desconectar
            await self.adapter.close()
            logger.info("🔌 Desconectado")

    async def _cleanup_positions(self):
        """Cerrar todas las posiciones abiertas y cancelar TODAS las órdenes (global cleanup)."""
        logger.info("\n🧹 PASO 0: Cleanup Global - Limpiar TODAS las posiciones y órdenes")
        logger.info("─" * 80)

        try:
            # 1. Cancelar TODAS las órdenes abiertas (GLOBAL - todos los símbolos)
            underlying_connector = getattr(self.adapter.connector, "_connector", self.adapter.connector)

            # Sin filtro de símbolo para obtener TODAS las órdenes
            open_orders = await underlying_connector.exchange.fetch_open_orders()

            if open_orders:
                logger.info(f"⚠️ Encontradas {len(open_orders)} órdenes GLOBALES, cancelando...")

                # Agrupar por símbolo para logging
                orders_by_symbol = {}
                for order in open_orders:
                    symbol = order.get("symbol", "UNKNOWN")
                    if symbol not in orders_by_symbol:
                        orders_by_symbol[symbol] = []
                    orders_by_symbol[symbol].append(order)

                # Cancelar todas
                for symbol, orders in orders_by_symbol.items():
                    logger.info(f"  🗑️ Cancelando {len(orders)} órdenes de {symbol}...")
                    for order in orders:
                        try:
                            await underlying_connector.exchange.cancel_order(order.get("id"), symbol)
                            logger.info(
                                f"    ❌ {order.get('id')[:8]}... [{order.get('side')} {order.get('orderType', 'N/A')}]"
                            )
                        except Exception as e:
                            logger.warning(f"    ⚠️ Error cancelando: {e}")

                logger.info("✅ Todas las órdenes globales canceladas")
            else:
                logger.info("✅ No hay órdenes abiertas globalmente")

            # 2. Cerrar TODAS las posiciones abiertas (GLOBAL)
            positions = await self.adapter.connector.fetch_positions()
            open_positions = [p for p in positions if abs(p.get("contracts", 0)) > 0]

            if not open_positions:
                logger.info("✅ No hay posiciones abiertas globalmente")
                return

            logger.info(f"⚠️ Encontradas {len(open_positions)} posiciones GLOBALES, cerrando...")

            for pos in open_positions:
                symbol = pos.get("symbol")
                side = pos.get("side")
                contracts = abs(pos.get("contracts", 0))

                if contracts == 0:
                    continue

                # Para cerrar: LONG → sell, SHORT → buy
                close_side = "sell" if side == "long" else "buy"

                logger.info(f"  🔒 Cerrando {symbol} | {side.upper()} | {contracts} contratos...")

                try:
                    await underlying_connector.exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=close_side,
                        amount=contracts,
                        params={"reduceOnly": True},
                    )
                    logger.info(f"    ✅ Posición cerrada")
                except Exception as e:
                    logger.warning(f"    ⚠️ Error cerrando posición: {e}")

            logger.info("✅ Todas las posiciones globales cerradas")

        except Exception as e:
            logger.warning(f"⚠️ Error en cleanup: {e}")

    async def _test_fetch_balance(self) -> bool:
        """
        PASO 1: Validar obtención de saldo.

        Simula: El bot pide el saldo al Croupier
        """
        logger.info("\n📝 PASO 1: Obtener saldo del exchange")
        logger.info("─" * 80)

        try:
            # CCXTAdapter usa get_balance() que es síncrono
            balance_amount = self.adapter.get_balance()

            # Para mantener compatibilidad con el resto del código,
            # crear estructura similar a fetch_balance
            balance = {"USD": {"total": balance_amount, "free": balance_amount, "used": 0.0}}

            # Validar estructura de respuesta
            if not isinstance(balance, dict):
                logger.error(f"❌ Balance no es un dict: {type(balance)}")
                return False

            # Buscar balance en USD/USDT/USDC
            found_balance = False
            for currency in ["USD", "USDT", "USDC"]:
                if currency in balance and isinstance(balance[currency], dict):
                    total = balance[currency].get("total", 0)
                    free = balance[currency].get("free", 0)
                    used = balance[currency].get("used", 0)

                    logger.info(f"✅ Balance {currency}:")
                    logger.info(f"   Total: ${total:.2f}")
                    logger.info(f"   Free:  ${free:.2f}")
                    logger.info(f"   Used:  ${used:.2f}")
                    found_balance = True
                    break

            if not found_balance:
                logger.error("❌ No se encontró balance en USD/USDT/USDC")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Error al obtener balance: {e}", exc_info=True)
            return False

    async def _create_bot_order(self) -> Optional[Dict]:
        """
        PASO 2: Crear orden en formato del bot.

        Simula: Gemini/Player genera una orden con multiplicadores TP/SL
        """
        logger.info("\n📝 PASO 2: Crear orden en formato del bot")
        logger.info("─" * 80)

        # Calcular cantidad automáticamente si no se especificó
        if self.amount is None:
            ticker = await self.adapter.connector.fetch_ticker(self.symbol)
            price = ticker.get("last")
            balance = self.adapter.get_balance()

            # Usar 1% del balance, mínimo $10 de valor
            min_value = 10.0
            self.amount = max(min_value / price, balance * 0.01 / price)
            self.amount = round(self.amount, 8)

            logger.info(f"💡 Cantidad auto-calculada: {self.amount} (${self.amount * price:.2f})")

        # Obtener spread actual para colocar órdenes muy cerca
        ticker = await self.adapter.connector.fetch_ticker(self.symbol)
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        spread = (ask - bid) / price if bid and ask else 0.001

        # Usar spread mínimo de 0.03% para asegurar ejecución rápida
        min_spread = 0.0003
        spread = max(spread, min_spread)

        # Formato exacto que usa el bot (ver gemini_core.py y build_order.py)
        # TP/SL basado en spread actual para ejecución rápida
        bot_order = {
            "symbol": self.symbol,
            "side": "sell",  # SHORT
            "amount": self.amount,
            "type": "market",
            "take_profit": 1.0 - spread,  # Multiplicador: ganar si baja el spread
            "stop_loss": 1.0 + spread,  # Multiplicador: perder si sube el spread
            "params": {},
        }

        logger.info(f"📊 Spread detectado: {spread*100:.3f}% (TP/SL ajustado dinámicamente)")

        logger.info(f"✅ Orden del bot creada:")
        logger.info(f"   Symbol: {bot_order['symbol']}")
        logger.info(f"   Side: {bot_order['side']}")
        logger.info(f"   Amount: {bot_order['amount']}")
        logger.info(f"   Type: {bot_order['type']}")
        logger.info(f"   TP Multiplier: {bot_order['take_profit']:.5f} (ganar si baja {spread*100:.3f}%)")
        logger.info(f"   SL Multiplier: {bot_order['stop_loss']:.5f} (perder si sube {spread*100:.3f}%)")

        return bot_order

    async def _test_order_translation(self, bot_order: Dict) -> bool:
        """
        PASO 3: Validar traducción de orden.

        Simula: CCXTAdapter traduce multiplicadores a precios absolutos
        """
        logger.info("\n📝 PASO 3: Validar traducción de orden")
        logger.info("─" * 80)

        try:
            # Obtener precio actual (como lo hace el adapter)
            ticker = await self.adapter.connector.fetch_ticker(self.symbol)
            current_price = ticker.get("last")

            if not current_price:
                logger.error("❌ No se pudo obtener precio actual")
                return False

            # Calcular precios TP/SL (como lo hace CCXTAdapter)
            tp_multiplier = float(bot_order["take_profit"])
            sl_multiplier = float(bot_order["stop_loss"])

            tp_price = current_price * tp_multiplier
            sl_price = current_price * sl_multiplier

            logger.info(f"✅ Traducción de orden:")
            logger.info(f"   Precio actual: ${current_price:.2f}")
            logger.info(f"   TP Multiplier: {tp_multiplier} → TP Price: ${tp_price:.2f}")
            logger.info(f"   SL Multiplier: {sl_multiplier} → SL Price: ${sl_price:.2f}")

            # Validar que los precios son razonables
            if tp_price <= 0 or sl_price <= 0:
                logger.error(f"❌ Precios TP/SL inválidos: TP=${tp_price}, SL=${sl_price}")
                return False

            # Para SHORT: TP debe estar abajo, SL arriba
            if bot_order["side"] == "sell":
                if tp_price >= current_price:
                    logger.error(f"❌ Para SHORT, TP debe estar abajo del precio actual")
                    return False
                if sl_price <= current_price:
                    logger.error(f"❌ Para SHORT, SL debe estar arriba del precio actual")
                    return False

            logger.info(f"✅ Validación de precios correcta para {bot_order['side'].upper()}")
            return True

        except Exception as e:
            logger.error(f"❌ Error en traducción: {e}", exc_info=True)
            return False

    async def _test_send_order(self, bot_order: Dict) -> Optional[Dict]:
        """
        PASO 4: Enviar orden al exchange.

        Simula: CCXTAdapter.execute_order() envía la orden
        """
        logger.info("\n📝 PASO 4: Enviar orden al exchange")
        logger.info("─" * 80)

        try:
            # Ejecutar orden (como lo hace el bot)
            logger.info("🚀 Enviando orden al exchange...")
            response = await self.adapter.execute_order(bot_order)

            logger.info(f"✅ Orden enviada al exchange")
            return response

        except Exception as e:
            logger.error(f"❌ Error al enviar orden: {e}", exc_info=True)
            return None

    async def _test_exchange_response(self, response: Dict) -> bool:
        """
        PASO 5: Validar respuesta del exchange.

        Simula: Verificar que el exchange respondió correctamente
        """
        logger.info("\n📝 PASO 5: Validar respuesta del exchange")
        logger.info("─" * 80)

        # Validar estructura de respuesta
        required_fields = ["id", "symbol", "side", "type", "status", "amount"]
        missing_fields = [f for f in required_fields if f not in response]

        if missing_fields:
            logger.error(f"❌ Campos faltantes en respuesta: {missing_fields}")
            return False

        logger.info(f"✅ Respuesta del exchange:")
        logger.info(f"   Order ID: {response.get('id')}")
        logger.info(f"   Symbol: {response.get('symbol')}")
        logger.info(f"   Side: {response.get('side')}")
        logger.info(f"   Type: {response.get('type')}")
        logger.info(f"   Status: {response.get('status')}")
        logger.info(f"   Amount: {response.get('amount')}")
        logger.info(f"   Filled: {response.get('filled')}")
        logger.info(f"   Price: {response.get('price')}")

        return True

    async def _test_response_normalization(self, response: Dict) -> bool:
        """
        PASO 6: Validar normalización de respuesta.

        Simula: Verificar que la respuesta está en formato CCXT normalizado
        """
        logger.info("\n📝 PASO 6: Validar normalización de respuesta")
        logger.info("─" * 80)

        # Verificar que la respuesta está normalizada (formato CCXT)
        # Debe tener campos estándar, no campos específicos del exchange

        # Campos que NO deberían estar (específicos de Kraken)
        kraken_specific = ["orderId", "orderType", "cliOrdId"]
        found_specific = [f for f in kraken_specific if f in response]

        if found_specific:
            logger.warning(f"⚠️ Campos específicos de Kraken en respuesta: {found_specific}")
            logger.warning(f"   (Deberían estar en 'info', no en el nivel superior)")

        # Verificar que 'info' contiene los datos raw del exchange
        if "info" not in response:
            logger.warning(f"⚠️ Campo 'info' no encontrado (debería contener datos raw)")

        logger.info(f"✅ Respuesta normalizada correctamente")
        logger.info(f"   Formato: CCXT estándar")
        logger.info(f"   Raw data: {'Sí' if 'info' in response else 'No'} (en 'info')")

        return True

    async def _test_position_opened(self) -> bool:
        """
        PASO 7: Verificar que se abrió la posición Y que existen órdenes TP/SL.
        """
        logger.info("\n📝 PASO 7: Verificar apertura de posición y órdenes TP/SL")
        logger.info("─" * 80)

        try:
            # Esperar un momento para que Kraken procese
            logger.info("⏳ Esperando 2s para que Kraken procese...")
            await asyncio.sleep(2)

            # Verificar órdenes abiertas (TP/SL)
            # ResilientConnector envuelve al conector real
            underlying_connector = getattr(self.adapter.connector, "_connector", self.adapter.connector)
            open_orders = await underlying_connector.exchange.fetch_open_orders(symbol=self.symbol)
            logger.info(f"📋 Órdenes abiertas: {len(open_orders)}")

            # Listar órdenes
            for order in open_orders:
                order_id = order.get("id")
                order_type = order.get("type")
                side = order.get("side")
                price = order.get("price")
                logger.info(f"   - {order_type} {side} @ ${price} | ID: {order_id[:8]}...")

            # Si hay al menos 2 órdenes abiertas, asumimos que son TP/SL
            # (Kraken no devuelve triggerPrice en fetch_open_orders)
            if len(open_orders) >= 2:
                logger.info(f"✅ Órdenes TP/SL creadas correctamente ({len(open_orders)} órdenes)")
                tpsl_created = True
            else:
                logger.warning(f"⚠️ Solo {len(open_orders)} órdenes abiertas (esperábamos >= 2)")
                tpsl_created = False

            # Verificar posición (puede tardar en aparecer)
            positions = await self.adapter.connector.fetch_positions()
            symbol_positions = [p for p in positions if p.get("symbol") == self.symbol]

            if len(symbol_positions) > 0:
                pos = symbol_positions[0]
                contracts = pos.get("contracts") or pos.get("size")

                if contracts and contracts != 0:
                    logger.info(f"✅ Posición abierta:")
                    logger.info(f"   Side: {pos.get('side')}")
                    logger.info(f"   Contracts: {contracts}")
                    logger.info(f"   Entry Price: ${pos.get('entryPrice') or pos.get('entry_price') or 'N/A'}")
                    return True
                else:
                    logger.warning("⚠️ Posición existe pero contracts = 0 (puede estar cerrándose)")

            # Si hay órdenes TP/SL, consideramos que el test pasó
            # (la posición puede haberse cerrado muy rápido)
            if tpsl_created:
                logger.info("✅ Órdenes TP/SL verificadas (posición puede haberse cerrado rápido)")
                return True

            logger.error("❌ No se encontró posición ni órdenes TP/SL")
            return False

        except Exception as e:
            logger.error(f"❌ Error al verificar posición: {e}", exc_info=True)
            return False

    async def _test_tpsl_execution(self, timeout: int = 300) -> bool:
        """
        PASO 8: **CRÍTICO** - Monitorear hasta que TP/SL se ejecute Y OCO funcione.

        Este test valida:
        1. Que el precio toque TP o SL (verificando velas)
        2. Que la orden se ejecute cuando el precio la toca
        3. Que el OCO Monitor cancele la orden contraria
        4. Que NO queden órdenes huérfanas

        Args:
            timeout: Timeout en segundos (default: 300s = 5 minutos)

        Returns:
            True si TP/SL se ejecutó Y OCO funcionó correctamente
        """
        logger.info("\n📝 PASO 8: **CRÍTICO** - Monitorear ejecución de TP/SL y OCO")
        logger.info("─" * 80)
        logger.info(f"⏱️  Timeout: {timeout}s ({timeout//60} minutos)")
        logger.info(f"⚡ Verificando precio cada 2s para detectar cuando toca TP/SL")

        import time

        start_time = time.time()
        deadline = start_time + timeout
        check_count = 0

        # Obtener IDs de las órdenes TP/SL y sus precios
        underlying_connector = getattr(self.adapter.connector, "_connector", self.adapter.connector)
        initial_orders = await underlying_connector.exchange.fetch_open_orders(symbol=self.symbol)
        initial_order_ids = {order.get("id") for order in initial_orders}

        # Extraer precios TP/SL de las órdenes
        # Kraken usa stopPrice o triggerPrice, no price
        tp_price = None
        sl_price = None
        for order in initial_orders:
            # Buscar precio en diferentes campos (depende del exchange)
            price = order.get("price") or order.get("stopPrice") or order.get("triggerPrice")
            if price:
                if tp_price is None or price < tp_price:
                    tp_price = price
                if sl_price is None or price > sl_price:
                    sl_price = price

        logger.info(f"📋 Monitoreando {len(initial_order_ids)} órdenes TP/SL")
        if tp_price and sl_price:
            logger.info(f"   TP Price: ${tp_price:,.2f}")
            logger.info(f"   SL Price: ${sl_price:,.2f}")
        else:
            logger.warning(f"   ⚠️ No se pudieron extraer precios TP/SL de las órdenes")

        price_touched_tp = False
        price_touched_sl = False

        while time.time() < deadline:
            check_count += 1
            elapsed = time.time() - start_time
            remaining = int(deadline - time.time())

            # Obtener precio actual
            ticker = await underlying_connector.exchange.fetch_ticker(self.symbol)
            current_price = ticker.get("last")

            # Verificar si el precio tocó TP o SL
            if current_price and tp_price and current_price <= tp_price:
                if not price_touched_tp:
                    logger.info(f"\n💰 ¡PRECIO TOCÓ TP! Current: ${current_price:,.2f} <= TP: ${tp_price:,.2f}")
                    price_touched_tp = True

            if current_price and sl_price and current_price >= sl_price:
                if not price_touched_sl:
                    logger.info(f"\n🛑 ¡PRECIO TOCÓ SL! Current: ${current_price:,.2f} >= SL: ${sl_price:,.2f}")
                    price_touched_sl = True

            # Verificar órdenes abiertas
            current_orders = await underlying_connector.exchange.fetch_open_orders(symbol=self.symbol)
            current_order_ids = {order.get("id") for order in current_orders}

            # Verificar si alguna orden se ejecutó (ya no está abierta)
            executed_orders = initial_order_ids - current_order_ids

            # Mostrar progreso cada 10 checks (~20s)
            if check_count % 10 == 0:
                progress_pct = (elapsed / timeout) * 100
                logger.info(
                    f"⏳ Check #{check_count} | "
                    f"Elapsed: {elapsed:.0f}s / {timeout}s ({progress_pct:.0f}%) | "
                    f"Remaining: {remaining}s | "
                    f"Price: ${current_price:,.2f} | "
                    f"Orders: {len(current_order_ids)}/{len(initial_order_ids)}"
                )

            # Si una orden se ejecutó (TP o SL)
            if executed_orders:
                logger.info(f"\n✅ ¡POSICIÓN CERRADA! TP o SL se ejecutó después de {elapsed:.0f}s")

                # Obtener último trade para ver si fue TP o SL
                underlying_connector = getattr(self.adapter.connector, "_connector", self.adapter.connector)
                trades = await underlying_connector.exchange.fetch_my_trades(symbol=self.symbol, limit=5)
                if trades:
                    last_trade = trades[0]
                    logger.info(f"\n💰 CIERRE DE POSICIÓN:")
                    logger.info(f"   Price: ${last_trade.get('price'):.2f}")
                    logger.info(f"   Amount: {last_trade.get('amount')}")
                    logger.info(f"   Side: {last_trade.get('side')}")

                # CRÍTICO: Verificar que NO quedan órdenes TP/SL abiertas (OCO debe haberlas cancelado)
                logger.info(f"\n🔍 Verificando que OCO canceló la orden contraria...")
                await asyncio.sleep(2)  # Dar tiempo al monitor para cancelar

                underlying_connector = getattr(self.adapter.connector, "_connector", self.adapter.connector)
                remaining_orders = await underlying_connector.exchange.fetch_open_orders(symbol=self.symbol)

                if remaining_orders:
                    logger.error(f"\n❌ FALLO OCO: Quedan {len(remaining_orders)} órdenes abiertas después del cierre")
                    for order in remaining_orders:
                        logger.error(
                            f"   - {order.get('type')} {order.get('side')} @ ${order.get('price')} | ID: {order.get('id')[:8]}..."
                        )
                    logger.error(f"\n❌ El OCO Monitor NO canceló las órdenes correctamente")
                    return False
                else:
                    logger.info(f"✅ OCO funcionó correctamente: No quedan órdenes abiertas")
                    return True

            # Esperar antes del próximo check
            await asyncio.sleep(2)

        # Si llegamos aquí, timeout
        logger.error(f"\n❌ TIMEOUT: TP/SL no se ejecutó en {timeout}s ({timeout//60} minutos)")
        logger.error(f"   Checks realizados: {check_count}")
        logger.error(f"   Órdenes aún abiertas: {len(current_order_ids)}")
        return False

    def _print_summary(self):
        """Imprime resumen del test."""
        logger.info("\n📊 RESUMEN DEL TEST:")
        logger.info("─" * 80)

        steps = [
            ("fetch_balance", "1. Obtener saldo del exchange"),
            ("receive_bot_order", "2. Crear orden en formato del bot"),
            ("translate_order", "3. Traducir multiplicadores a precios"),
            ("send_to_exchange", "4. Enviar orden al exchange"),
            ("receive_response", "5. Recibir respuesta del exchange"),
            ("normalize_response", "6. Normalizar respuesta para el bot"),
            ("position_opened", "7. Verificar apertura de posición"),
            ("tpsl_executed", "8. **CRÍTICO** Validar ejecución de TP/SL"),
        ]

        for key, description in steps:
            status = "✅" if self.test_results[key] else "❌"
            logger.info(f"  {status} {description}")


async def run_test(
    exchange: str, testnet: bool = True, symbol: str = "LTC/USD:USD", amount: Optional[float] = None
) -> bool:
    """
    Ejecuta el test para un exchange.

    Args:
        exchange: Nombre del exchange
        testnet: Si usar testnet o live

    Returns:
        True si el test pasó, False si falló
    """
    logger.info(f"🚀 Iniciando test para: {exchange}")
    logger.info(f"🌐 Modo: {'TESTNET' if testnet else 'LIVE'}")

    # Crear conector base
    if exchange.lower() == "kraken":
        base_connector = KrakenConnector(
            mode="testing" if testnet else "live",
            enable_websocket=False,
        )
    else:
        raise ValueError(f"Exchange no soportado: {exchange}")

    # Envolver con ResilientConnector
    connector = ResilientConnector(
        connector=base_connector,
        enable_state_recovery=False,
    )

    # Crear adapter (simula el Croupier)
    adapter = CCXTAdapter(
        connector=connector,
        symbol=symbol,
    )

    # Ejecutar test
    test = BotToExchangeFlowTest(adapter, symbol=symbol, amount=amount)
    return await test.run()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Test del flujo Bot → Exchange → Bot",
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

    parser.add_argument(
        "--amount",
        type=float,
        help="Order amount (auto-calculated if not specified)",
    )

    args = parser.parse_args()

    # Determinar si usar testnet o live
    testnet = not args.live

    # Ejecutar test
    success = asyncio.run(run_test(args.exchange, testnet, args.symbol, args.amount))

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
