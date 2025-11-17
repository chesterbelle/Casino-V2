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

    async def execute_order(self, order: dict) -> dict:
        """
        Wrapper para mantener compatibilidad con código existente.
        Delega a oco_bracketed_order que es el método principal.
        """
        return await self.oco_bracketed_order(order)

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

            # 3. Verificar fondos
            required_margin = self.get_equity() * order.get("size", 0.0)
            if not self.balance_manager.can_open_position(required_margin):
                return self._insufficient_funds_result(order)

            # 4. Ejecutar orden principal
            main_order = await self._execute_on_exchange(
                {
                    "symbol": symbol,
                    "side": "buy" if order["side"] == "LONG" else "sell",
                    "type": "market",
                    "amount": order["size"],
                    "leverage": order.get("leverage", 1),
                    "params": {"reduceOnly": False},
                }
            )

            if not main_order or not main_order.get("id"):
                raise Exception("No se pudo ejecutar la orden principal")

            # 5. Configurar TP/SL (siempre se configuran)
            try:
                tp_order_id, sl_order_id = await self._setup_oco_orders(order, main_order)
            except (TPOrderCreationError, SLOrderCreationError, OCOConfigurationError) as e:
                self.logger.error(f"❌ Error crítico en OCO: {e}")
                self.logger.error(f"❌ Cancelando orden principal {main_order['id']} por fallo en TP/SL")

                # Cancelar orden principal ya que no podemos tener TP/SL
                try:
                    await self.exchange_adapter.cancel_order(main_order["id"], symbol)
                    self.logger.info(f"✅ Orden principal {main_order['id']} cancelada")
                except Exception as cancel_error:
                    self.logger.error(f"❌ Error cancelando orden principal: {cancel_error}")

                return {
                    "status": "rejected",
                    "reason": f"OCO setup failed: {str(e)}",
                    "main_order_id": main_order["id"],
                    "tp_order_id": None,
                    "sl_order_id": None,
                }

            # 6. Registrar posición
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

        entry_price = main_result.get("price", 0.0)

        # Si entry_price es 0, obtener el precio actual del mercado
        if not entry_price:
            ticker = await self.exchange_adapter.fetch_ticker(order.get("symbol"))
            entry_price = ticker.get("last", 0.0)
            if entry_price:
                self.logger.info(f"📊 Using current market price as entry: ${entry_price:.2f}")

        if not entry_price:
            raise OCOConfigurationError("No entry price available for TP/SL calculation")

        tp_multiplier = order.get("take_profit", 1.0)
        sl_multiplier = order.get("stop_loss", 1.0)
        symbol = order.get("symbol")
        # IMPORTANTE: Obtener amount del RESULTADO de la orden principal, no de la orden original
        # La orden original puede tener "size" pero no "amount"
        # El "amount" se calcula en _execute_on_exchange() y se retorna en main_result
        amount = main_result.get("amount") or order.get("amount")
        side = order.get("side")
        safety_margin_factor = 0.0005  # 0.05%

        if side == "LONG":
            tp_price = entry_price * tp_multiplier
            sl_price = entry_price * sl_multiplier * (1 - safety_margin_factor)
        else:  # SHORT
            tp_price = entry_price * (2.0 - tp_multiplier)
            sl_price = entry_price * (2.0 - sl_multiplier) * (1 + safety_margin_factor)

        self.logger.info(f"📊 OCO Monitor | Entry: ${entry_price:.2f} | TP: ${tp_price:.2f} | SL: ${sl_price:.2f}")

        # Determinar lado opuesto (para cerrar posición)
        close_side = "sell" if side == "LONG" else "buy"

        # Crear TP order - TAKE_PROFIT_MARKET (según documentación oficial CCXT)
        # https://github.com/ccxt/ccxt/blob/master/examples/py/binance-stop-loss-take-profit.py
        tp_order_id = None
        if tp_price:
            tp_order = {
                "symbol": symbol,
                "side": close_side,
                "amount": amount,
                "type": "take_profit_market",  # ← TAKE_PROFIT_MARKET (no LIMIT)
                "params": {
                    "stopPrice": tp_price,  # ← stopPrice para TP
                },
            }

            tp_result = await self.exchange_adapter.execute_order(tp_order)
            tp_order_id = tp_result.get("id")
            self.logger.info(f"✅ TP order created: {tp_order_id} @ ${tp_price:.2f}")
        else:
            raise OCOConfigurationError("TP price is zero or invalid")

        # Crear SL order - STOP_MARKET (según documentación oficial CCXT)
        # https://github.com/ccxt/ccxt/blob/master/examples/py/binance-stop-loss-take-profit.py
        sl_order_id = None
        if sl_price:
            sl_order = {
                "symbol": symbol,
                "side": close_side,
                "amount": amount,
                "type": "stop_market",  # ← STOP_MARKET
                "params": {
                    "stopPrice": sl_price,  # ← stopPrice para SL
                },
            }

            sl_result = await self.exchange_adapter.execute_order(sl_order)
            sl_order_id = sl_result.get("id")
            self.logger.info(f"✅ SL order created: {sl_order_id} @ ${sl_price:.2f}")
        else:
            raise OCOConfigurationError("SL price is zero or invalid")

        return tp_order_id, sl_order_id

    async def _has_open_position(self, symbol: str) -> bool:
        try:
            positions = await self.state_sync.sync_positions()
            for position in positions:
                if position.symbol == symbol and position.size > 0:
                    self.logger.info(f"📊 Posición encontrada: {position.symbol} con {position.size} contratos")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Error verifying open positions: {e}", exc_info=True)
            self.logger.warning("🛡️ SAFETY FIRST: Rejecting order to prevent duplicate positions.")
            return True

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
        # Cancelar la orden hermana si todavía existe y está abierta
        if sibling_order and sibling_order.get("status") == "open":
            await self._cancel_sibling_order(sibling_order["id"], "sibling", position.symbol)

        # Calcular PnL y confirmar el cierre
        exit_price = executed_order.get("price", position.entry_price)
        fee_info = executed_order.get("fee") or {}
        fee = fee_info.get("cost", 0.0)
        pnl = self._calculate_position_pnl(position, exit_price, fee)

        self.position_tracker.confirm_close(position.trade_id, exit_price, reason, pnl, fee)

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
