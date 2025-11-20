"""
====================================================
🎯 Croupier V2 — Tablero de Control del Casino
====================================================

Rol:
----
El Croupier es el tablero de control centralizado del Casino.
Gestiona el portfolio completo (balance + posiciones) y coordina
la ejecución de órdenes con el exchange adapter.

Responsabilidades:
------------------
• Gestionar portfolio (PortfolioManager)
• Validar órdenes antes de ejecutar
• Coordinar ejecución con exchange adapter
• Proveer información consolidada del portfolio
• Mantener el estado del trading

API Pública:
------------
Información:
- get_balance() -> float
- get_equity() -> float
- get_open_positions() -> List[Dict]
- get_portfolio_state() -> Dict

Ejecución:
- execute_order(order: dict) -> dict

Contrato de la orden:
---------------------
{
    "trade_id": str,
    "symbol": str,
    "side": "LONG" | "SHORT",
    "size": float,            # fracción del equity a arriesgar
    "take_profit": float,     # factor multiplicativo (ej. 1.01 => +1%)
    "stop_loss": float,       # factor multiplicativo (ej. 0.992 => -0.8%)
    "timestamp": str | None,
    "ghost": bool             # True = shadow (entrena sin tocar balance)
}
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

from core.portfolio.balance_manager import BalanceManager
from core.portfolio.position_tracker import PositionTracker
from exchanges.adapters.exchange_state_sync import ExchangeStateSync


class TPOrderCreationError(Exception):
    """Error al crear orden Take Profit"""

    pass


class SLOrderCreationError(Exception):
    """Error al crear orden Stop Loss"""

    pass


class OCOConfigurationError(Exception):
    """Error en configuración OCO"""

    pass


class Croupier:
    """
    Cerebro central del sistema de trading. Es el dueño del estado del portfolio
    y el único responsable de la lógica de negocio y la recuperación de errores.
    """

    async def cleanup_orphaned_positions(self, symbol: str):
        """
        Detecta y cierra posiciones huérfanas para un símbolo específico.
        Se debe llamar en cada vela antes de ejecutar la estrategia.
        """
        try:
            # 1. Obtener posiciones del exchange
            exchange_positions = await self.state_sync.sync_positions()

            # 2. Obtener posiciones del tracker interno
            tracker_positions = self.position_tracker.open_positions
            tracker_map = {p.symbol: p for p in tracker_positions}

            for ex_pos in exchange_positions:
                if ex_pos.symbol == symbol and ex_pos.size != 0:
                    tracker_pos = tracker_map.get(ex_pos.symbol)

                    # Si no hay posición en el tracker, o si la del tracker es incompleta, es huérfana
                    is_orphaned = not tracker_pos or not (
                        tracker_pos.main_order_id and tracker_pos.tp_order_id and tracker_pos.sl_order_id
                    )

                    if is_orphaned:
                        self.logger.warning(f"🧹 Found orphaned position for {symbol} during cleanup. Closing it.")
                        # Usar una estructura de posición temporal para el cierre
                        temp_position_for_closure = ex_pos
                        if tracker_pos:  # Usar datos del tracker si existen
                            temp_position_for_closure.trade_id = tracker_pos.trade_id
                            temp_position_for_closure.side = tracker_pos.side
                        else:  # Estimar datos si no hay tracker
                            temp_position_for_closure.trade_id = f"ORPHAN_{int(time.time())}"
                            temp_position_for_closure.side = "LONG" if ex_pos.size > 0 else "SHORT"

                        await self._close_orphaned_position(temp_position_for_closure)

        except Exception as e:
            self.logger.error(f"❌ Error during orphaned position cleanup for {symbol}: {e}", exc_info=True)

    def __init__(self, exchange_adapter, initial_balance: float):
        """
        Inicializa el Croupier como el dueño del estado.

        Args:
            exchange_adapter: Adaptador para comunicación con el exchange (debe ser sin estado).
            initial_balance: Balance inicial en USDT. Requerido para inicializar el estado.
        """
        self.logger = logging.getLogger("Croupier")
        self.exchange_adapter = exchange_adapter

        # --- El Croupier ahora es dueño del estado ---
        self.balance_manager = BalanceManager(starting_balance=initial_balance)
        self.position_tracker = PositionTracker(
            mode="hybrid",  # Modo recomendado
            adapter=exchange_adapter,  # Pasar adapter para OCO manual
        )
        self.state_sync = ExchangeStateSync(exchange_adapter.connector)
        # --------------------------------------------

        self.logger.info(f"🎯 Croupier initialized as State Owner | Balance: ${initial_balance:,.2f}")
        self.logger.info("✅ OCO Manual enabled in PositionTracker")

    # ========================================
    # API Pública: Información del Portfolio
    # ========================================

    def get_balance(self) -> float:
        return self.balance_manager.get_balance()

    def get_equity(self) -> float:
        return self.balance_manager.get_equity()

    def get_open_positions(self) -> List[Dict]:
        return self.position_tracker.open_positions

    def get_position(self, trade_id: str) -> Optional[Dict]:
        position = self.position_tracker.get_position(trade_id)
        return position.__dict__ if position else None

    def get_portfolio_state(self) -> Dict:
        tracker_stats = self.position_tracker.get_stats()
        return {
            "balance": self.get_balance(),
            "equity": self.get_equity(),
            "open_positions_count": len(self.get_open_positions()),
            "open_positions": self.get_open_positions(),
            "total_trades": tracker_stats.get("total_closed", 0),
            "wins": tracker_stats.get("total_wins", 0),
            "losses": tracker_stats.get("total_losses", 0),
        }

    # ========================================
    # API Pública: Ejecución de Órdenes
    # ========================================

    async def execute_order(self, order: dict, wait_for_fill_confirmation: bool = True) -> dict:
        """
        Wrapper para mantener compatibilidad con código existente.
        Delega a oco_bracketed_order que es el método principal.

        Args:
            order: diccionario de orden (ver contrato)
            wait_for_fill_confirmation: si True, solicitar al adaptador que espere
            la confirmación de fill/avgPrice vía WebSocket antes de proceder
            con la creación de TP/SL. Por defecto True (nuevo flujo market-first).
        """
        return await self.oco_bracketed_order(order, wait_for_fill_confirmation=wait_for_fill_confirmation)

    async def oco_bracketed_order(self, order: dict) -> dict:
        """
        Método principal para ejecutar órdenes con TP/SL.

        Args:
            order: {
                "symbol": "BTC/USDT",
                "side": "LONG" | "SHORT",
                "size": 0.1,           # fracción del equity a arriesgar
                "take_profit": 1.05,   # multiplicador (ej: 1.05 = +5%)
                "stop_loss": 0.98,     # multiplicador (ej: 0.98 = -2%)
                "leverage": 10,        # apalancamiento (opcional)
                "ghost": False         # si es True, no ejecuta órdenes reales
            }

        Returns:
            {
                "status": "filled" | "rejected" | "error",
                "main_order_id": str,
                "tp_order_id": str,
                "sl_order_id": str,
                "reason": str  # en caso de error o rechazo
            }
        """
        try:
            # 1. Validar orden (incluye TP/SL requeridos)
            self._validate_order(order)
            symbol = order["symbol"]

            # 2. Verificar si ya hay posición abierta
            if await self._has_open_position(symbol):
                msg = f"Ya hay una posición abierta para {symbol}"
                self.logger.warning(f"⚠️ {msg}")
                return {
                    "status": "rejected",
                    "reason": msg,
                    "main_order_id": None,
                    "tp_order_id": None,
                    "sl_order_id": None,
                }

            # 3. Obtener precio actual y convertir fracción a cantidad real de contratos
            try:
                current_price = await self.exchange_adapter.get_current_price(symbol)
            except Exception as e:
                self.logger.error(f"❌ Error obteniendo precio actual: {e}")
                return {
                    "status": "error",
                    "reason": f"Could not get current price: {str(e)}",
                    "main_order_id": None,
                    "tp_order_id": None,
                    "sl_order_id": None,
                }

            # Convertir fracción del equity a notional en USDT
            size_fraction = order.get("size", 0.0)
            notional_desired = self.get_equity() * size_fraction

            # Calcular cantidad real de contratos
            amount = notional_desired / current_price if current_price > 0 else 0

            # Validar mínimo de notional (Binance requiere 5 USDT)
            MIN_NOTIONAL = 5.0
            if notional_desired < MIN_NOTIONAL:
                self.logger.warning(
                    f"⚠️ Notional ({notional_desired:.2f} USDT) menor que mínimo ({MIN_NOTIONAL} USDT). "
                    f"Ajustando al mínimo."
                )
                amount = MIN_NOTIONAL / current_price
                notional_desired = MIN_NOTIONAL

            self.logger.info(
                f"📊 Orden convertida | Fracción: {size_fraction:.4f} | "
                f"Notional: {notional_desired:.2f} USDT | Precio: {current_price:.8f} | "
                f"Cantidad: {amount:.6f} contratos"
            )

            # 4. Verificar fondos
            required_margin = notional_desired
            if not self.balance_manager.can_open_position(required_margin):
                return self._insufficient_funds_result(order)

            # 5. Ejecutar orden principal
            main_order_payload = {
                "symbol": symbol,
                "side": "buy" if order["side"] == "LONG" else "sell",
                "type": "market",
                "amount": amount,
                "leverage": order.get("leverage", 1),
                "params": {"reduceOnly": False},
            }

            # Always use WS-first confirmation semantics for the main order
            main_order_payload["confirm_with_ws"] = True
            # Permitir especificar timeout por orden (ms)
            if "ws_timeout_ms" in order:
                main_order_payload["ws_timeout_ms"] = order.get("ws_timeout_ms")

            main_order = await self._execute_on_exchange(main_order_payload)

            if not main_order or not main_order.get("id"):
                raise Exception("No se pudo ejecutar la orden principal")

            # 6. Configurar TP/SL (siempre se configuran)
            tp_order_id = None
            sl_order_id = None
            try:
                tp_order_id, sl_order_id = await self._setup_oco_orders(order, main_order)
            except (TPOrderCreationError, SLOrderCreationError, OCOConfigurationError) as e:
                self.logger.error(f"❌ Error crítico en OCO: {e}")
                self.logger.error("❌ Cancelando todas las órdenes y cerrando posición por fallo en TP/SL")

                # Cancelar TODAS las órdenes que se hayan creado
                await self._cancel_all_orders(
                    symbol=symbol,
                    main_order_id=main_order.get("id"),
                    tp_order_id=tp_order_id,
                    sl_order_id=sl_order_id,
                )

                # Cerrar la posición abierta para evitar órdenes huérfanas
                try:
                    close_side = "sell" if order["side"] == "LONG" else "buy"
                    await self.exchange_adapter.execute_order(
                        {
                            "symbol": symbol,
                            "side": close_side,
                            "amount": main_order.get("amount", 0),
                            "type": "market",
                            "params": {"reduceOnly": True},
                        }
                    )
                    self.logger.info("✅ Posición cerrada por fallo en OCO")
                except Exception as close_error:
                    self.logger.error(f"❌ Failed to close position after OCO error: {close_error}")

                return {
                    "status": "rejected",
                    "reason": f"OCO setup failed: {str(e)}",
                    "main_order_id": None,
                    "tp_order_id": None,
                    "sl_order_id": None,
                }
            except Exception as e:
                self.logger.error(f"❌ Error inesperado en OCO: {e}", exc_info=True)
                self.logger.error("❌ Cancelando todas las órdenes y cerrando posición por error inesperado")

                # Cancelar TODAS las órdenes que se hayan creado
                await self._cancel_all_orders(
                    symbol=symbol,
                    main_order_id=main_order.get("id"),
                    tp_order_id=tp_order_id,
                    sl_order_id=sl_order_id,
                )

                # Cerrar la posición abierta para evitar órdenes huérfanas
                try:
                    close_side = "sell" if order["side"] == "LONG" else "buy"
                    await self.exchange_adapter.execute_order(
                        {
                            "symbol": symbol,
                            "side": close_side,
                            "amount": main_order.get("amount", 0),
                            "type": "market",
                            "params": {"reduceOnly": True},
                        }
                    )
                    self.logger.info("✅ Posición cerrada por error inesperado en OCO")
                except Exception as close_error:
                    self.logger.error(f"❌ Failed to close position after unexpected error: {close_error}")

                return {
                    "status": "error",
                    "reason": f"Unexpected error in OCO setup: {str(e)}",
                    "main_order_id": None,
                    "tp_order_id": None,
                    "sl_order_id": None,
                }

            # 7. Registrar posición
            self.position_tracker.open_position(
                order=order,
                entry_price=main_order.get("price", 0.0),
                entry_timestamp=main_order.get("timestamp", ""),
                available_equity=self.get_equity(),
                main_order_id=main_order["id"],
                tp_order_id=tp_order_id,
                sl_order_id=sl_order_id,
            )

            # 8. NO cerrar inmediatamente - dejar que TP/SL se ejecuten
            # La posición debe permanecer abierta para que TP/SL puedan cerrarse
            # El cierre se hará cuando TP o SL se ejecute (monitoreado por PositionTracker)

            # 9. Validar status de la orden principal
            main_status = main_order.get("status")
            if main_status not in ["open", "opened", "closed"]:
                error_msg = (
                    f"❌ Status inválido en orden principal: '{main_status}'. "
                    f"Se esperaba 'open', 'opened' o 'closed'. "
                    f"Orden: {main_order}"
                )
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # 10. Retornar resultado con status real del exchange
            result = {
                "status": main_status,  # Status validado del exchange
                "id": main_order["id"],
                "price": main_order.get("price", 0.0),
                "amount": main_order.get("amount", 0.0),
                "balance": self.get_balance(),
                "equity": self.get_equity(),
                "main_order_id": main_order["id"],
                "tp_order_id": tp_order_id,
                "sl_order_id": sl_order_id,
                "reason": None,
            }

            # Instrumentation: propagate order timing/confirm flags if present
            try:
                if isinstance(main_order, dict):
                    if "order_create_ts" in main_order:
                        result["order_create_ts"] = main_order.get("order_create_ts")
                    if "ws_confirm_ts" in main_order:
                        result["ws_confirm_ts"] = main_order.get("ws_confirm_ts")
                    if "used_ws_confirm" in main_order:
                        result["used_ws_confirm"] = bool(main_order.get("used_ws_confirm"))
                    if "used_rest_fallback" in main_order:
                        result["used_rest_fallback"] = bool(main_order.get("used_rest_fallback"))
                    # compute latency if possible
                    if result.get("order_create_ts") and result.get("ws_confirm_ts"):
                        try:
                            result["ws_latency_ms"] = int(result["ws_confirm_ts"] - result["order_create_ts"])
                        except Exception:
                            pass
            except Exception:
                # Non-critical: do not fail order flow due to instrumentation
                pass

            self._log_execution(order, result)
            return result

        except Exception as e:
            self.logger.error(f"❌ Error en oco_bracketed_order: {e}", exc_info=True)
            return {
                "status": "error",
                "main_order_id": None,
                "tp_order_id": None,
                "sl_order_id": None,
                "reason": str(e),
            }

    async def cleanup_symbol(self, symbol: str):
        """Método público para forzar la limpieza de un símbolo."""
        self.logger.info(f"🧹 Ejecutando limpieza robusta para {symbol}...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 1. Cancelar todas las órdenes abiertas
                open_orders = await self.exchange_adapter.connector.fetch_open_orders(symbol)
                if open_orders:
                    for order in open_orders:
                        await self.exchange_adapter.cancel_order(order["id"], symbol)

                # 2. Cerrar posición si existe
                positions = await self.exchange_adapter.connector.fetch_positions([symbol])
                pos_found = any(p and abs(p.get("contracts", 0)) > 0 for p in positions)
                if pos_found:
                    for pos in positions:
                        if pos and abs(pos.get("contracts", 0)) > 0:
                            side = "sell" if pos.get("side") == "long" else "buy"
                            amount = abs(pos.get("contracts", 0))
                            await self.exchange_adapter.execute_order(
                                {
                                    "symbol": symbol,
                                    "type": "market",
                                    "side": side,
                                    "amount": amount,
                                    "params": {"reduceOnly": True},
                                }
                            )
                            await asyncio.sleep(2)  # Esperar a que se procese

                # 3. Sincronizar y limpiar estado interno
                await self.state_sync.sync_positions()
                for p in list(self.position_tracker.open_positions):
                    if p.symbol == symbol:
                        self.position_tracker.open_positions.remove(p)

                # 4. Verificación final
                final_orders = await self.exchange_adapter.connector.fetch_open_orders(symbol)
                final_positions = await self.exchange_adapter.connector.fetch_positions([symbol])
                has_pos = any(p and abs(p.get("contracts", 0)) > 0 for p in final_positions)

                if not final_orders and not has_pos:
                    self.logger.info(f"✅ Limpieza para {symbol} completada.")
                    return

            except Exception as e:
                self.logger.error(f"Error en limpieza (intento {attempt + 1}): {e}")

            self.logger.warning(f"Limpieza fallida en intento {attempt + 1}. Reintentando...")
            await asyncio.sleep(2)

        raise RuntimeError(f"No se pudo limpiar el símbolo {symbol} después de {max_retries} intentos.")

    async def close_position(self, trade_id: str) -> dict:
        self.logger.info(f"Intentando cerrar manualmente la posición: {trade_id}")
        position_to_close = self.position_tracker.get_position(trade_id)

        if not position_to_close:
            raise ValueError(f"No se encontró una posición abierta con el trade_id: {trade_id}")

        close_side = "sell" if position_to_close.side == "LONG" else "buy"
        close_order = {
            "symbol": position_to_close.symbol,
            "type": "market",
            "side": close_side,
            "amount": position_to_close.notional / position_to_close.entry_price,
            "params": {"reduceOnly": True},
        }

        result = await self.exchange_adapter.execute_order(close_order)

        if not result:
            raise ValueError(f"Failed to execute close order for position {trade_id}")

        await self._cancel_sibling_order(position_to_close.tp_order_id, "TP", position_to_close.symbol)
        await self._cancel_sibling_order(position_to_close.sl_order_id, "SL", position_to_close.symbol)

        # Safe access to result fields
        exit_price = result.get("price", 0.0) if result else 0.0
        pnl = result.get("realizedPnl", 0.0) if result else 0.0
        fee_info = result.get("fee", {}) if result else {}
        fee = fee_info.get("cost", 0.0) if isinstance(fee_info, dict) else 0.0

        self.position_tracker.confirm_close(
            trade_id=trade_id, exit_price=exit_price, exit_reason="MANUAL", pnl=pnl, fee=fee
        )

        return result

    # ========================================
    # Métodos Privados
    # ========================================

    def _validate_order(self, order: dict):
        required = ("symbol", "side", "size", "take_profit", "stop_loss")
        for field in required:
            if field not in order:
                raise ValueError(f"Orden incompleta: falta '{field}'")

    async def _execute_on_exchange(self, order: dict) -> dict:
        if "size" in order and "amount" not in order:
            order = await self._calculate_amount_from_size(order)

        # El Croupier es agnóstico - delega TODA la ejecución al adapter
        # El adapter se encarga de manejar TP/SL según el exchange específico
        result = await self.exchange_adapter.execute_order(order)

        # Accept both limit orders (open/opened) and market orders (closed)
        status = result.get("status")
        if status not in ["open", "opened", "closed"]:
            error_msg = (
                f"❌ Status de orden inválido: '{status}'. "
                f"Se esperaba 'open', 'opened' o 'closed'. "
                f"Orden completa: {result}"
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info(f"✅ Orden ejecutada: {result.get('id')}")
        return result

    async def _calculate_amount_from_size(self, order: dict) -> dict:
        size_fraction = float(order["size"])
        leverage = order.get("leverage", 1)
        symbol = order["symbol"]
        equity = self.get_equity()
        current_price = order.get("price")

        if not current_price:
            if hasattr(self.exchange_adapter, "get_current_price"):
                current_price = await self.exchange_adapter.get_current_price(symbol)
            else:
                raise ValueError("Exchange adapter does not have get_current_price method")
            if not current_price:
                raise ValueError(f"Cannot get current price for {symbol} from exchange")

        margin = equity * size_fraction
        position_value = margin * leverage
        amount = position_value / current_price

        self.logger.info(
            f"📊 Croupier calculation | Equity: ${equity:.2f} | Size: {size_fraction*100:.2f}% | "
            f"Margin: ${margin:.2f} | Leverage: {leverage}x | Position: ${position_value:.2f} | "
            f"Price: ${current_price:.2f} | Amount: {amount:.6f}"
        )

        order_with_amount = dict(order)
        order_with_amount["amount"] = amount
        return order_with_amount

    async def _setup_oco_orders(self, order: dict, main_result: dict) -> tuple:
        """
        OCO Monitor: Crea órdenes TP/SL después de la orden principal.

        Responsable de:
        1. Detectar si hay TP/SL en la orden
        2. Calcular precios absolutos desde multiplicadores
        3. Crear órdenes TP y SL como órdenes limit separadas
        4. Retornar IDs de las órdenes

        Nota: Croupier es agnóstico del exchange. Solo crea órdenes limit simples.
        El exchange adapter/connector maneja los parámetros específicos de cada exchange.

        Args:
            order: Orden original con multiplicadores
            main_result: Resultado de la orden principal

        Returns:
            (tp_order_id, sl_order_id) o (None, None) si no hay TP/SL
        """
        # Detectar TP/SL
        has_tpsl = "take_profit" in order or "stop_loss" in order
        if not has_tpsl:
            return None, None

        # Forzar uso del precio de ejecución real
        entry_price = main_result.get("price")
        if not entry_price or entry_price <= 0:
            entry_price = main_result.get("avgPrice")
        if not entry_price or entry_price <= 0:
            # Intentar obtener de fetch_order si el exchange lo soporta
            try:
                order_id = main_result.get("id")
                if order_id:
                    fetched_order = await self.exchange_adapter.connector.fetch_order(order_id, order.get("symbol"))
                    entry_price = fetched_order.get("average") or fetched_order.get("avgPrice")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not fetch order details: {e}")
        # Si aún no hay precio, fallar claramente
        if not entry_price or entry_price <= 0:
            raise OCOConfigurationError(f"No valid execution price for TP/SL calculation. Got: {entry_price}")

        tp_multiplier = order.get("take_profit", 1.0)
        sl_multiplier = order.get("stop_loss", 1.0)
        symbol = order.get("symbol")
        # IMPORTANTE: Obtener amount del RESULTADO de la orden principal, no de la orden original
        # La orden original puede tener "size" pero no "amount"
        # El "amount" se calcula en _execute_on_exchange() y se retorna en main_result
        amount = main_result.get("amount") or order.get("amount")
        side = order.get("side")

        # Aumentar margen de seguridad para evitar "Order would immediately trigger"
        # Binance requiere que el SL esté suficientemente lejos del precio actual
        # Para precios muy pequeños (como 0.004), necesitamos un margen mayor
        if entry_price < 0.01:
            safety_margin_factor = 0.01  # 1% para precios muy pequeños
        elif entry_price < 0.1:
            safety_margin_factor = 0.005  # 0.5% para precios pequeños
        else:
            safety_margin_factor = 0.002  # 0.2% para precios normales

        if side == "LONG":
            tp_price = entry_price * tp_multiplier
            # Para LONG: SL debe estar DEBAJO del entry_price, así que restamos el margen
            sl_price = entry_price * sl_multiplier * (1 - safety_margin_factor)
        else:  # SHORT
            tp_price = entry_price * (2.0 - tp_multiplier)
            # Para SHORT: SL debe estar ARRIBA del entry_price, así que sumamos el margen
            sl_price = entry_price * (2.0 - sl_multiplier) * (1 + safety_margin_factor)

        self.logger.info(f"📊 OCO Monitor | Entry: ${entry_price:.8f} | TP: ${tp_price:.8f} | SL: ${sl_price:.8f}")

        # Obtener precio actual del mercado para validar TP/SL
        try:
            current_market_price = await self.exchange_adapter.get_current_price(symbol)
            self.logger.debug(f"🔍 Current market price: ${current_market_price:.8f}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not get current market price: {e}")
            current_market_price = entry_price

        # Determinar lado opuesto (para cerrar posición)
        close_side = "sell" if side == "LONG" else "buy"

        # Implement retry logic for creating TP and SL orders. If after retries we
        # cannot create both protective orders, we consider this a critical failure
        # and the caller (Croupier) should cancel created orders and close the main
        # position to avoid leaving an unprotected position open.

        MAX_RETRIES = 3
        tp_order_id = None
        sl_order_id = None
        tp_attempts = []
        sl_attempts = []

        # Helper to create order with retries
        async def _attempt_create(payload, attempts_list):
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    t0 = time.time()
                    res = await self.exchange_adapter.execute_order(payload)
                    t1 = time.time()
                    attempts_list.append({"attempt": attempt, "ok": True, "duration_ms": int((t1 - t0) * 1000)})
                    return res
                except Exception as e:
                    t1 = time.time()
                    attempts_list.append(
                        {"attempt": attempt, "ok": False, "error": str(e), "duration_ms": int((t1 - t0) * 1000)}
                    )
                    await asyncio.sleep(0.2 * attempt)
            return None

        # Create TP order (take profit market)
        if tp_price:
            tp_payload = {
                "symbol": symbol,
                "side": close_side,
                "amount": amount,
                "type": "take_profit_market",
                "params": {"stopPrice": tp_price},
            }

            tp_res = await _attempt_create(tp_payload, tp_attempts)
            if tp_res:
                tp_order_id = tp_res.get("id")
                self.logger.info(f"✅ TP order created: {tp_order_id} @ ${tp_price:.8f}")
            else:
                # If TP couldn't be created after retries, raise to trigger failure handling
                self.logger.error(f"❌ Failed to create TP after {MAX_RETRIES} attempts: {tp_attempts}")
                raise TPOrderCreationError(f"Failed to create TP after {MAX_RETRIES} attempts")
        else:
            raise OCOConfigurationError("TP price is zero or invalid")

        # Create SL order (stop market)
        if sl_price:
            sl_payload = {
                "symbol": symbol,
                "side": close_side,
                "amount": amount,
                "type": "stop_market",
                "params": {"stopPrice": sl_price},
            }

            sl_res = await _attempt_create(sl_payload, sl_attempts)
            if sl_res:
                sl_order_id = sl_res.get("id")
                self.logger.info(f"✅ SL order created: {sl_order_id} @ ${sl_price:.2f}")
            else:
                # Cancel TP if SL creation failed
                self.logger.error(f"❌ Failed to create SL after {MAX_RETRIES} attempts: {sl_attempts}")
                if tp_order_id:
                    try:
                        await self.exchange_adapter.cancel_order(tp_order_id, symbol)
                        self.logger.info(f"🔄 Cancelled TP order {tp_order_id} due to SL creation failure")
                    except Exception as cancel_error:
                        self.logger.error(f"❌ Failed to cancel TP order: {cancel_error}")
                raise SLOrderCreationError(f"Failed to create SL after {MAX_RETRIES} attempts")
        else:
            raise OCOConfigurationError("SL price is zero or invalid")

        # Attach attempt metadata to logs (non-critical)
        try:
            self.logger.debug({"tp_attempts": tp_attempts, "sl_attempts": sl_attempts})
        except Exception:
            pass

        return tp_order_id, sl_order_id

    async def _has_open_position(self, symbol: str) -> bool:
        """
        Verifica si existe una posición VÁLIDA (con main, TP y SL) para el símbolo.
        """
        try:
            # Usamos el tracker interno que es la fuente de verdad del bot
            open_positions = self.position_tracker.open_positions
            for position in open_positions:
                if position.symbol == symbol:
                    # Una posición válida debe tener las 3 órdenes
                    if position.main_order_id and position.tp_order_id and position.sl_order_id:
                        self.logger.info(f"📊 Posición válida encontrada en tracker para {symbol}")
                        return True

            # Si no está en el tracker, no debería haber posición
            return False
        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Error verifying open positions from tracker: {e}", exc_info=True)
            self.logger.warning("🛡️ SAFETY FIRST: Rejecting order to prevent duplicate positions.")
            return True

    async def _close_orphaned_position(self, position) -> None:
        """
        Cierra una posición huérfana detectada durante el trading.
        Se ejecuta automáticamente cuando se detecta una posición sin TP/SL.
        """
        try:
            self.logger.error(
                f"🚨 ORPHANED POSITION DETECTED: {position.symbol} | Size: {position.size} | "
                f"Entry: ${position.entry_price:.8f}"
            )

            # Determinar lado opuesto para cerrar
            close_side = "sell" if position.side == "LONG" else "buy"

            # Cerrar con orden MARKET
            close_order = await self.exchange_adapter.execute_order(
                {
                    "symbol": position.symbol,
                    "side": close_side,
                    "amount": abs(position.size),
                    "type": "market",
                    "params": {"reduceOnly": True},
                }
            )

            # Calcular PnL
            exit_price = close_order.get("price", position.entry_price)
            fee = close_order.get("fee", {}).get("cost", 0.0)
            pnl = self._calculate_position_pnl(position, exit_price, fee)

            # Registrar cierre
            self.position_tracker.confirm_close(position.trade_id, exit_price, "ORPHANED_AUTO_CLOSE", pnl, fee)

            self.logger.info(
                f"✅ ORPHANED POSITION CLOSED: {position.symbol} | " f"Exit: ${exit_price:.8f} | PnL: ${pnl:.8f}"
            )

        except Exception as e:
            self.logger.error(f"❌ FAILED TO CLOSE ORPHANED POSITION: {position.symbol} | Error: {e}")
            # Intentar cerrar internamente como último recurso
            try:
                pnl = self._calculate_position_pnl(position, position.entry_price, 0.0)
                self.position_tracker.confirm_close(
                    position.trade_id, position.entry_price, "ORPHANED_INTERNAL_CLOSE", pnl, 0.0
                )
                self.logger.warning(f"⚠️ ORPHANED POSITION CLOSED INTERNALLY: {position.symbol}")
            except Exception as internal_error:
                self.logger.error(f"❌ CRITICAL: Could not close orphaned position internally: {internal_error}")

    def _insufficient_funds_result(self, order: dict) -> dict:
        return {
            "status": "rejected",
            "reason": "insufficient_funds",
            "order": order,
        }

    def _execution_error_result(self, order: dict, error: str) -> dict:
        return {
            "status": "error",
            "reason": "execution_error",
            "error": error,
            "order": order,
        }

    def _log_execution(self, order: dict, result: dict):
        status = result.get("status", "unknown")
        symbol = order.get("symbol", "?")
        side = order.get("side", "?")

        if status == "rejected":
            self.logger.warning(f"🚫 Rejected | {symbol} {side} | {result.get('reason', 'unknown')}")
        elif status == "error":
            self.logger.error(f"❌ Error | {symbol} {side} | {result.get('error', 'unknown')}")
        else:
            self.logger.debug(f"🃏 Exec | {symbol} {side} | status={status}")

    def _calculate_position_pnl(self, position, exit_price: float, fee: float) -> float:
        """
        Calcula el PnL de una posición cerrada.

        Args:
            position: OpenPosition object
            exit_price: Precio de salida
            fee: Fee de la transacción

        Returns:
            PnL en USD (positivo = ganancia, negativo = pérdida)
        """
        try:
            # Calcular PnL basado en el lado de la posición
            if position.side == "LONG":
                # Para LONG: ganancia si exit_price > entry_price
                pnl_pct = (exit_price - position.entry_price) / position.entry_price
            else:  # SHORT
                # Para SHORT: ganancia si exit_price < entry_price
                pnl_pct = (position.entry_price - exit_price) / position.entry_price

            # Convertir porcentaje a valor absoluto
            pnl = position.notional * pnl_pct

            # Restar fee
            pnl -= fee

            self.logger.debug(
                f"📊 PnL Calc | {position.symbol} {position.side} | "
                f"Entry: {position.entry_price:.2f} | Exit: {exit_price:.2f} | "
                f"PnL: {pnl:+.2f} | Notional: {position.notional:.2f} | Fee: {fee:.2f}"
            )

            return pnl
        except Exception as e:
            self.logger.error(f"❌ Error calculating PnL: {e}")
            return 0.0

    async def _cancel_sibling_order(self, order_id: Optional[str], order_type: str, symbol: str):
        """Cancela una orden hermana (TP o SL) si existe y está activa."""
        if not order_id:
            return

        try:
            # PASO 1: Verificar si la orden aún existe y está activa
            try:
                order_status = await self.exchange_adapter.fetch_order(order_id, symbol)
                if order_status.get("status") in ["closed", "canceled", "expired"]:
                    self.logger.info(
                        f"ℹ️ Orden {order_type} {order_id} ya está {order_status.get('status')}, no necesita cancelación"
                    )
                    return
            except Exception:
                # Si no podemos obtener el estado, la orden probablemente no existe
                self.logger.info(
                    f"ℹ️ Orden {order_type} {order_id} no encontrada al verificar estado, probablemente ya ejecutada"
                )
                return

            # PASO 2: Si llegamos aquí, la orden existe y está activa, proceder a cancelar
            await self.exchange_adapter.cancel_order(order_id, symbol)
            self.logger.info(f"✅ Orden {order_type} cancelada exitosamente: {order_id}")

        except Exception as e:
            # Este bloque solo debería ejecutarse si hay un error real inesperado
            self.logger.error(f"❌ Error inesperado cancelando orden {order_type} {order_id}: {e}")

    async def monitor_positions(self) -> None:
        """
        Método centralizado para monitorear posiciones abiertas y emular OCO.

        Responsabilidades:
        1. Iterar sobre posiciones abiertas.
        2. Verificar estado de órdenes TP/SL.
        3. Si una se ejecuta, cancelar la otra y confirmar el cierre.
        4. Si ambas órdenes desaparecen, cerrar la posición para evitar posiciones huérfanas.
        """
        self.logger.debug("🔍 Monitoring open positions...")
        # Usar una copia de la lista para poder modificarla durante la iteración
        for position in list(self.position_tracker.open_positions):
            try:
                tp_order = await self._fetch_order_safely(position.tp_order_id, position.symbol)
                sl_order = await self._fetch_order_safely(position.sl_order_id, position.symbol)

                # Escenario 1: TP ejecutado
                if tp_order and tp_order.get("status") in ["closed", "filled"]:
                    self.logger.info(f"🎯 TAKE PROFIT DETECTED for {position.symbol}")
                    await self._handle_position_closure(position, tp_order, "TP", sl_order)
                    continue  # Mover a la siguiente posición

                # Escenario 2: SL ejecutado
                if sl_order and sl_order.get("status") in ["closed", "filled"]:
                    self.logger.info(f"🛡️ STOP LOSS DETECTED for {position.symbol}")
                    await self._handle_position_closure(position, sl_order, "SL", tp_order)
                    continue

                # Escenario 3: Ambas órdenes TP/SL han desaparecido (canceladas o no encontradas)
                if not tp_order and not sl_order:
                    self.logger.warning(f"⚠️ Both TP/SL orders for {position.symbol} are gone. Closing position.")
                    await self._close_position_without_orders(position)

            except Exception as e:
                self.logger.error(f"❌ Error monitoring position {position.trade_id}: {e}", exc_info=True)

    async def _fetch_order_safely(self, order_id: Optional[str], symbol: str) -> Optional[Dict]:
        """Obtiene una orden de forma segura, devolviendo None si no se encuentra."""
        if not order_id:
            return None
        try:
            return await self.exchange_adapter.fetch_order(order_id, symbol)
        except Exception:
            # Si fetch_order falla (ej. orden no encontrada), asumimos que no existe.
            return None

    async def _handle_position_closure(
        self, position, executed_order: Dict, reason: str, sibling_order: Optional[Dict]
    ):
        """Maneja el cierre de una posición, cancelando la orden hermana y confirmando."""
        self.logger.info(f"📋 Closing position | Symbol: {position.symbol} | Reason: {reason}")

        # Cancelar la orden hermana si todavía existe y está abierta
        if sibling_order and sibling_order.get("status") == "open":
            self.logger.info(f"🔄 Cancelling sibling order ({reason} counterpart)")
            await self._cancel_sibling_order(sibling_order["id"], "sibling", position.symbol)

        # Cancelar el main_order_id si todavía existe y está abierta
        if position.main_order_id:
            self.logger.info(f"🔄 Cancelling main_order_id: {position.main_order_id}")
            await self._cancel_sibling_order(position.main_order_id, "main_order", position.symbol)

        # Calcular PnL y confirmar el cierre
        exit_price = executed_order.get("price", position.entry_price)
        fee_info = executed_order.get("fee") or {}
        fee = fee_info.get("cost", 0.0)
        pnl = self._calculate_position_pnl(position, exit_price, fee)

        self.logger.info(
            f"✅ CONFIRMED CLOSE | {position.symbol} {position.side} | "
            f"Entry: {position.entry_price:.2f} | Exit: {exit_price:.2f} ({reason}) | "
            f"PnL: {pnl:+.2f} | Fee: {fee:.2f}"
        )

        self.position_tracker.confirm_close(position.trade_id, exit_price, reason, pnl, fee)

    async def _cancel_all_orders(
        self,
        symbol: str,
        main_order_id: Optional[str] = None,
        tp_order_id: Optional[str] = None,
        sl_order_id: Optional[str] = None,
    ):
        """Cancela todas las órdenes de forma segura (main, TP, SL)."""
        orders_to_cancel = [
            (main_order_id, "main"),
            (tp_order_id, "TP"),
            (sl_order_id, "SL"),
        ]

        for order_id, order_type in orders_to_cancel:
            if order_id:
                try:
                    await self.exchange_adapter.cancel_order(order_id, symbol)
                    self.logger.info(f"✅ Cancelled {order_type} order {order_id}")
                except Exception as e:
                    self.logger.error(f"❌ Failed to cancel {order_type} order {order_id}: {e}")

    async def _close_position_without_orders(self, position):
        """Cierra una posición cuando sus órdenes TP/SL han desaparecido."""
        self.logger.info(f"Attempting to close {position.symbol} at market price.")
        try:
            # Crear una orden de mercado para cerrar la posición
            close_side = "sell" if position.side == "LONG" else "buy"
            amount = position.notional / position.entry_price
            market_close_order = await self.exchange_adapter.execute_order(
                {
                    "symbol": position.symbol,
                    "side": close_side,
                    "amount": amount,
                    "type": "market",
                    "params": {"reduceOnly": True},
                }
            )

            exit_price = market_close_order.get("price", position.entry_price)
            fee = market_close_order.get("fee", {}).get("cost", 0.0)
            pnl = self._calculate_position_pnl(position, exit_price, fee)

            self.position_tracker.confirm_close(position.trade_id, exit_price, "ORPHANED", pnl, fee)
            self.logger.info(f"✅ Position {position.symbol} closed successfully.")

        except Exception as e:
            self.logger.error(f"❌ Failed to close orphaned position {position.symbol}: {e}")
            # Como último recurso, se cierra internamente para evitar que el capital quede bloqueado
            pnl = self._calculate_position_pnl(position, position.entry_price, 0.0)  # PnL cero
            self.position_tracker.confirm_close(position.trade_id, position.entry_price, "ORPHANED_FAIL", pnl, 0.0)
