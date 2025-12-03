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
from typing import Any, Dict, List, Optional

from core.concurrency import get_lock_manager
from core.portfolio.balance_manager import BalanceManager
from core.portfolio.position_tracker import PositionTracker
from core.portfolio.utils import calculate_position_pnl
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

    def __init__(self, exchange_adapter, initial_balance: float, gemini=None):
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
            adapter=exchange_adapter,  # Pasar adapter para OCO manual
            on_close_callback=gemini.on_trade_result if gemini else None,
        )
        self.state_sync = ExchangeStateSync(exchange_adapter)

        # Lock manager for concurrency control
        self.lock_mgr = get_lock_manager()
        self.logger.info("🔒 Lock manager initialized")
        # LAYER 2 ATOMICITY PROTECTION: Flag for conditional validation
        self.integrity_check_failed = False

        # Error classifier for smart validation triggering
        from exchanges.resilience.error_classifier import ErrorClassifier

        self.error_classifier = ErrorClassifier()
        # --------------------------------------------

        # Register for order updates if supported
        if hasattr(exchange_adapter.connector, "set_order_update_callback"):
            exchange_adapter.connector.set_order_update_callback(self._on_order_update)
            self.logger.info("✅ Registered for WebSocket order updates")

        self.logger.info(f"🎯 Croupier initialized as State Owner | Balance: ${initial_balance:,.2f}")
        self.logger.info("✅ OCO Manual enabled in PositionTracker")

    async def _on_order_update(self, order: dict):
        """
        Callback para recibir actualizaciones de órdenes vía WebSocket.
        Delega a PositionTracker para confirmar cierres.
        """
        try:
            order_id = str(order.get("id"))
            status = order.get("status")
            symbol = order.get("symbol")

            # Log ALL order updates for debugging
            self.logger.info(f"⚡ WebSocket Order Update: ID={order_id}, Symbol={symbol}, Status={status}")

            # Solo nos interesan órdenes llenadas o cerradas
            if status not in ["closed", "filled"]:
                self.logger.debug(f"   ⏭️ Skipping order {order_id} - status '{status}' not in ['closed', 'filled']")
                return

            # Buscar si esta orden pertenece a alguna posición abierta (TP o SL)
            # 2. Buscar si la orden pertenece a una posición abierta
            target_position = None
            exit_reason = None  # "TP" or "SL"

            # Debug: Log what we are looking for
            self.logger.info(
                f"🔍 OCO Check: Searching for {order_id} in {len(self.position_tracker.open_positions)} positions"
            )

            for pos in self.position_tracker.open_positions:
                self.logger.info(f"   - Checking Pos {pos.trade_id}: TP={pos.tp_order_id} SL={pos.sl_order_id}")
                if str(pos.tp_order_id) == order_id:
                    target_position = pos
                    exit_reason = "TP"
                    break
                elif str(pos.sl_order_id) == order_id:
                    target_position = pos
                    exit_reason = "SL"
                    break
                elif str(pos.main_order_id) == order_id:
                    # Si es la orden principal, quizás actualizar precio de entrada?
                    # Por ahora ignoramos, ya que se maneja en la creación
                    pass

            if target_position and exit_reason:
                self.logger.info(f"⚡ WebSocket Order Update: {exit_reason} filled for {target_position.symbol}")

                # Extraer datos del fill
                # last_trade = order.get("lastTrade", {})  # Binance specific structure sometimes
                # CCXT normalized structure
                fill_price = float(order.get("average") or order.get("price") or order.get("lastPrice") or 0.0)
                filled_amount = float(order.get("filled") or order.get("amount") or 0.0)

                # Calcular PnL aproximado si no viene en la orden
                pnl = 0.0
                if target_position.side == "LONG":
                    pnl = (fill_price - target_position.entry_price) * filled_amount
                else:
                    pnl = (target_position.entry_price - fill_price) * filled_amount

                # Confirmar cierre en el tracker
                # Esto disparará el callback on_trade_result y liberará capital
                self.position_tracker.confirm_close(
                    trade_id=target_position.trade_id,
                    exit_price=fill_price,
                    exit_reason=exit_reason,
                    pnl=pnl,
                    fee=float(order.get("fee", {}).get("cost", 0.0)),
                )

                # IMPORTANTE: Cancelar la orden hermana (OCO Manual)
                sibling_order_id = target_position.sl_order_id if exit_reason == "TP" else target_position.tp_order_id
                if sibling_order_id:
                    self.logger.info(f"🧹 Cancelling sibling {exit_reason} order: {sibling_order_id}")
                    try:
                        await self.exchange_adapter.cancel_order(sibling_order_id, target_position.symbol)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to cancel sibling order {sibling_order_id}: {e}")
            else:
                self.logger.debug(f"   ⏭️ Order {order_id} not associated with any open position")

        except Exception as e:
            self.logger.error(f"❌ Error processing order update: {e}", exc_info=True)

    async def reconcile_positions(self, symbol: str):
        """
        Sistema de reconciliación periódica para mantener atomicidad de órdenes.

        Verifica y corrige:
        1. Posiciones sin TP/SL completo
        2. Órdenes huérfanas sin posición asociada
        3. Posiciones en exchange no registradas en tracker

        Args:
            symbol: Símbolo a reconciliar (ej: "LTC/USDT:USDT")
        """
        try:
            self.logger.info(f"🔍 Iniciando reconciliación para {symbol}")

            # 1. Obtener estado del exchange
            exchange_positions = await self.state_sync.sync_positions()
            exchange_orders = await self.exchange_adapter.connector.fetch_open_orders(symbol)

            # 2. Obtener estado interno
            tracker_positions = self.position_tracker.open_positions

            # 3. Crear mapas para búsqueda rápida
            # tracker_map = {p.trade_id: p for p in tracker_positions if p.symbol == symbol}
            # exchange_pos_map = {p.symbol: p for p in exchange_positions if p.symbol == symbol}

            self.logger.info(
                f"🔍 Reconciliación debug: Exchange positions: {len(exchange_positions)} | Exchange orders: {len(exchange_orders)} | Tracker positions: {len(tracker_positions)}"
            )
            for p in exchange_positions:
                self.logger.info(f"   Position: {p.symbol} Size: {p.size} Side: {getattr(p, 'side', 'N/A')}")
            for o in exchange_orders:
                self.logger.info(f"   Order: {o['id']} ({o['type']}) Side: {o['side']} Stop: {o.get('stopPrice')}")

            # === VERIFICACIÓN 1: Posiciones del tracker tienen TP/SL completo ===
            for pos in tracker_positions:
                if pos.symbol != symbol:
                    continue

                # Verificar que tenga IDs de órdenes
                if not pos.tp_order_id or not pos.sl_order_id:
                    self.logger.warning(
                        f"⚠️ Posición {pos.trade_id} sin TP/SL completo. "
                        f"TP: {pos.tp_order_id}, SL: {pos.sl_order_id}"
                    )
                    # Cerrar posición incompleta
                    self.logger.info(f"🧹 Cerrando posición incompleta {pos.trade_id}")
                    try:
                        await self.close_position(pos.trade_id)
                    except Exception as e:
                        self.logger.error(f"❌ Error cerrando posición incompleta: {e}")
                    continue

                # Verificar que las órdenes TP/SL existan en el exchange
                order_ids = {str(o["id"]) for o in exchange_orders}

                if str(pos.tp_order_id) not in order_ids:
                    self.logger.warning(f"⚠️ Orden TP {pos.tp_order_id} no existe en exchange")
                    # Cerrar posición sin TP
                    self.logger.info(f"🧹 Cerrando posición sin TP: {pos.trade_id}")
                    try:
                        await self.close_position(pos.trade_id)
                    except Exception as e:
                        self.logger.error(f"❌ Error cerrando posición sin TP: {e}")
                    continue

                if str(pos.sl_order_id) not in order_ids:
                    self.logger.warning(f"⚠️ Orden SL {pos.sl_order_id} no existe en exchange")
                    # Cerrar posición sin SL
                    self.logger.info(f"🧹 Cerrando posición sin SL: {pos.trade_id}")
                    try:
                        await self.close_position(pos.trade_id)
                    except Exception as e:
                        self.logger.error(f"❌ Error cerrando posición sin SL: {e}")
                    continue

            # Obtener todos los IDs de órdenes asociadas a posiciones
            tracked_order_ids = set()
            for pos in tracker_positions:
                if pos.symbol == symbol:
                    if pos.main_order_id:
                        tracked_order_ids.add(str(pos.main_order_id))
                    if pos.tp_order_id:
                        tracked_order_ids.add(str(pos.tp_order_id))
                    if pos.sl_order_id:
                        tracked_order_ids.add(str(pos.sl_order_id))

            self.logger.info(f"🔍 Tracked Order IDs: {tracked_order_ids}")

            # Cancelar órdenes que no están asociadas a ninguna posición
            for order in exchange_orders:
                order_id = str(order["id"])
                order_type = order.get("type", "").upper()

                # Solo verificar órdenes TP/SL (las órdenes market ya están ejecutadas)
                if order_type in ["TAKE_PROFIT_MARKET", "STOP_MARKET", "TAKE_PROFIT", "STOP"]:
                    if order_id not in tracked_order_ids:
                        self.logger.warning(f"⚠️ Orden huérfana detectada: {order_id} ({order_type})")
                        # Cancelar orden huérfana
                        try:
                            await self.exchange_adapter.cancel_order(order_id, symbol)
                            self.logger.info(f"✅ Orden huérfana {order_id} cancelada")
                        except Exception as e:
                            self.logger.error(f"❌ Error cancelando orden huérfana {order_id}: {e}")

            # === VERIFICACIÓN 3: Posiciones en exchange no registradas ===
            for ex_pos in exchange_positions:
                # Normalize symbols for comparison (handle LTC/USDT:USDT vs LTCUSDT)
                # LTCUSDT is the native format, LTC/USDT:USDT is the CCXT format
                # We need to extract just the base symbol for comparison
                ex_symbol_clean = ex_pos.symbol.replace("/", "").replace(":", "").upper()
                target_symbol_clean = (
                    symbol.split("/")[0] + symbol.split("/")[1].split(":")[0]
                    if "/" in symbol
                    else symbol.replace(":", "").upper()
                )

                if ex_symbol_clean != target_symbol_clean or ex_pos.size == 0:
                    continue

                # Buscar si existe en el tracker
                found_in_tracker = any(p.symbol == symbol for p in tracker_positions)

                if not found_in_tracker:
                    self.logger.warning(f"⚠️ Posición en exchange no registrada: {symbol} " f"(size: {ex_pos.size})")
                    # Cerrar posición no registrada
                    self.logger.info(f"🧹 Cerrando posición no registrada en {symbol}")
                    try:
                        # One-Way Mode: Close by opening opposite order with reduceOnly
                        close_side = (
                            "SHORT" if ex_pos.size > 0 else "LONG"
                        )  # If ex_pos.size > 0, it's a LONG position, so close with SHORT
                        await self.exchange_adapter.execute_order(
                            {
                                "symbol": symbol,
                                "type": "market",
                                "side": close_side,
                                "amount": abs(ex_pos.size),
                                "params": {"reduceOnly": True},
                            }
                        )
                        self.logger.info("✅ Posición no registrada cerrada")
                    except Exception as e:
                        self.logger.error(f"❌ Error cerrando posición no registrada: {e}")

            self.logger.info(f"✅ Reconciliación completada para {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error durante reconciliación de {symbol}: {e}", exc_info=True)

    async def validate_all_positions_integrity(self):
        """LAYER 2 ATOMICITY PROTECTION: Valida que todas las posiciones tengan sus órdenes TP/SL activas.

        Este método debe llamarse periódicamente (ej: cada 5 minutos) para detectar y cerrar
        posiciones que perdieron sus órdenes protectoras por cualquier razón.
        """
        try:
            open_positions = self.position_tracker.open_positions
            if not open_positions:
                return

            self.logger.debug(f"🔍 Validating integrity of {len(open_positions)} open positions")

            for position in list(open_positions):  # Use list() to avoid modification during iteration
                try:
                    # Fetch all open orders for this symbol
                    exchange_orders = await self.exchange_adapter.connector.fetch_open_orders(position.symbol)
                    order_ids = {str(o["id"]) for o in exchange_orders}

                    # Check if TP and SL orders exist
                    tp_exists = str(position.tp_order_id) in order_ids if position.tp_order_id else False
                    sl_exists = str(position.sl_order_id) in order_ids if position.sl_order_id else False

                    # If any protective order is missing, close the position
                    if not tp_exists or not sl_exists:
                        missing_orders = []
                        if not tp_exists:
                            missing_orders.append(f"TP({position.tp_order_id})")
                        if not sl_exists:
                            missing_orders.append(f"SL({position.sl_order_id})")

                        self.logger.warning(
                            f"🚨 PERIODIC VALIDATION | Position {position.trade_id} missing orders: {', '.join(missing_orders)}"
                        )
                        self.logger.info(f"🛡️ Closing unprotected position {position.trade_id}")

                        try:
                            await self.close_position(position.trade_id, skip_confirm_close=False)
                            self.logger.info(
                                f"✅ Unprotected position {position.trade_id} closed (PERIODIC_VALIDATION)"
                            )
                        except Exception as e:
                            self.logger.error(f"❌ Failed to close unprotected position {position.trade_id}: {e}")

                except Exception as e:
                    self.logger.error(f"❌ Error validating position {position.trade_id}: {e}")

            self.logger.debug("✅ Position integrity validation complete")

        except Exception as e:
            self.logger.error(f"❌ Error during periodic position validation: {e}", exc_info=True)

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
        la confirmación de fill/avgPrice vía WebSocket antes de proceder
        con la creación de TP/SL. Por defecto True (nuevo flujo market-first).
        """
        return await self.oco_bracketed_order(order, wait_for_fill_confirmation=wait_for_fill_confirmation)

    async def oco_bracketed_order(self, order: dict, wait_for_fill_confirmation: bool = True) -> dict:
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

            # 2. Obtener precio actual y convertir fracción a cantidad real de contratos
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

            # Round amount to exchange precision
            try:
                if hasattr(self.exchange_adapter, "amount_to_precision"):
                    astr = self.exchange_adapter.amount_to_precision(symbol, amount)
                    amount = float(astr)
            except Exception:
                pass

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
                "side": order["side"],  # Use LONG/SHORT directly
                "type": "market",
                "amount": amount,
                "params": {
                    # For entry orders, reduceOnly should not be true.
                    # Leverage is handled by the exchange adapter.
                    "leverage": order.get("leverage", 1),
                    **order.get("params", {}),
                },
            }

            # Respect caller preference whether to wait for WS fill confirmation
            # If True, adapters/connectors may prefer WebSocket confirmation before
            # proceeding to create TP/SL. Default is True to preserve new websocket-first behavior.
            main_order_payload["confirm_with_ws"] = bool(wait_for_fill_confirmation)
            # Permitir especificar timeout por orden (ms)
            if "ws_timeout_ms" in order:
                main_order_payload["ws_timeout_ms"] = order.get("ws_timeout_ms")

            main_order = await self._execute_on_exchange(main_order_payload)

            if not main_order or not main_order.get("id"):
                raise Exception("No se pudo ejecutar la orden principal")

            # 6. Configurar TP/SL (siempre se configuran)
            tp_order_id = None
            sl_order_id = None
            entry_price_from_oco = None
            # Instrumentation placeholders for attempt metadata (defined here so
            # outer scope can safely attach them to the result dict). The
            # detailed attempt logs are recorded inside _setup_oco_orders, but
            # exposing these placeholders avoids NameError/flake8 issues when
            # instrumentation is attempted below.
            tp_attempts = []
            sl_attempts = []
            try:
                tp_order_id, sl_order_id, entry_price_from_oco = await self._setup_oco_orders(order, main_order)
            except (TPOrderCreationError, SLOrderCreationError, OCOConfigurationError) as e:
                self.logger.error(f"❌ Error crítico en OCO: {e}")
                self.logger.error("❌ Cancelando todas las órdenes y cerrando posición por fallo en TP/SL")

                # Intentar cancelar TP/SL si se crearon
                if tp_order_id:
                    try:
                        await self.exchange_adapter.cancel_order(tp_order_id, symbol)
                        self.logger.info(f"🔄 TP {tp_order_id} cancelado tras fallo en OCO")
                    except Exception as cancel_err:
                        self.logger.error(f"❌ Error cancelando TP {tp_order_id}: {cancel_err}")

                if sl_order_id:
                    try:
                        await self.exchange_adapter.cancel_order(sl_order_id, symbol)
                        self.logger.info(f"🔄 SL {sl_order_id} cancelado tras fallo en OCO")
                    except Exception as cancel_err:
                        self.logger.error(f"❌ Error cancelando SL {sl_order_id}: {cancel_err}")

                # Cerrar posición principal
                try:
                    close_side = "SHORT" if order["side"] == "LONG" else "LONG"
                    await self.exchange_adapter.execute_order(
                        {
                            "symbol": symbol,
                            "type": "market",
                            "side": close_side,
                            "amount": amount,
                            "params": {"reduceOnly": True},
                        }
                    )
                    self.logger.info("🔄 Posición principal cerrada tras fallo en OCO")
                except Exception as close_err:
                    self.logger.error(f"❌ Error cerrando posición principal: {close_err}")

                return {
                    "status": "error",
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
                    close_side = "SHORT" if order["side"] == "LONG" else "LONG"
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
                    self.logger.error(f"❌ Failed to close position after reconciliation error: {close_error}")

                return {
                    "status": "error",
                    "reason": f"Unexpected error in OCO setup: {str(e)}",
                    "main_order_id": None,
                    "tp_order_id": None,
                    "sl_order_id": None,
                }

            # 7. Registrar posición
            # Use entry_price from OCO setup (which fetches the order to get avgPrice)
            # Fallback to extracting from main_order if OCO didn't return it
            entry_price = (
                entry_price_from_oco
                or main_order.get("avgPrice")
                or main_order.get("average")
                or main_order.get("price", 0.0)
            )

            self.position_tracker.open_position(
                order=order,
                entry_price=entry_price,
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
            if main_status not in ["open", "opened", "closed", "new"]:
                error_msg = (
                    f"❌ Status inválido en orden principal: '{main_status}'. "
                    f"Se esperaba 'open', 'opened', 'closed' o 'new'. "
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

            # Attach TP/SL attempt metadata for diagnostics (non-critical)
            try:
                result["tp_attempts"] = tp_attempts
                result["sl_attempts"] = sl_attempts
            except Exception:
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
                # Prefer normalized positions from ExchangeStateSync; use central helper to fallback
                positions = await self._fetch_positions([symbol])

                def _pos_contracts(p):
                    try:
                        if not p:
                            return 0
                        if isinstance(p, dict):
                            return abs(p.get("contracts", 0) or p.get("amount", 0))
                        # dataclass/obj
                        return abs(getattr(p, "contracts", None) or getattr(p, "size", 0))
                    except Exception:
                        return 0

                pos_found = any(
                    _pos_contracts(p) > 0
                    for p in positions
                    if p
                    and (getattr(p, "symbol", None) == symbol or (isinstance(p, dict) and p.get("symbol") == symbol))
                )
                if pos_found:
                    for pos in [
                        p
                        for p in positions
                        if p
                        and (
                            getattr(p, "symbol", None) == symbol or (isinstance(p, dict) and p.get("symbol") == symbol)
                        )
                    ]:
                        if _pos_contracts(pos) > 0:
                            # compute side and amount from dict or object
                            try:
                                if isinstance(pos, dict):
                                    side = "SHORT" if (pos.get("side") or "").lower() == "long" else "LONG"
                                    amount = abs(pos.get("contracts", 0) or pos.get("amount", 0))
                                else:
                                    side = "SHORT" if (getattr(pos, "side", "")).upper() == "LONG" else "LONG"
                                    amount = abs(getattr(pos, "contracts", None) or getattr(pos, "size", 0))
                            except Exception:
                                side = "SHORT"  # Default to short to close long positions
                                amount = 0

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

                # Obtener estado del exchange
                exchange_orders = await self.exchange_adapter.connector.fetch_open_orders(symbol)
                tracker_positions = [p for p in self.position_tracker.open_positions if p.symbol == symbol]

                self.logger.info(
                    f"🔍 Reconciliación debug: Exchange orders: {len(exchange_orders)} | Tracker positions: {len(tracker_positions)}"
                )
                for o in exchange_orders:
                    self.logger.info(f"   Order: {o['id']} ({o['type']}) Side: {o['side']} Stop: {o.get('stopPrice')}")

                # 4. Verificación final
                final_orders = await self.exchange_adapter.connector.fetch_open_orders(symbol)
                final_positions = await self._fetch_positions([symbol])
                has_pos = any(_pos_contracts(p) > 0 for p in final_positions)

                if not final_orders and not has_pos:
                    self.logger.info(f"✅ Limpieza para {symbol} completada.")
                    return

            except Exception as e:
                self.logger.error(f"Error en limpieza (intento {attempt + 1}): {e}")

            self.logger.warning(f"Limpieza fallida en intento {attempt + 1}. Reintentando...")
            await asyncio.sleep(2)

        raise RuntimeError(f"No se pudo limpiar el símbolo {symbol} después de {max_retries} intentos.")

    async def close_position(self, trade_id: str, skip_confirm_close: bool = False) -> dict:
        self.logger.info(f"Intentando cerrar manualmente la posición: {trade_id}")
        position_to_close = self.position_tracker.get_position(trade_id)

        if not position_to_close:
            raise ValueError(f"No se encontró una posición abierta con el trade_id: {trade_id}")

        # Cancel TP/SL first to ensure ReduceOnly order isn't rejected due to locked quantity
        await self._cancel_sibling_order(position_to_close.tp_order_id, "TP", position_to_close.symbol, trade_id)
        await self._cancel_sibling_order(position_to_close.sl_order_id, "SL", position_to_close.symbol, trade_id)

        close_side = "sell" if position_to_close.side == "LONG" else "buy"

        # Use size/amount directly to avoid precision errors from notional calculation
        try:
            if isinstance(position_to_close, dict):
                amount = position_to_close.get("amount") or position_to_close.get("size") or 0.0
            else:
                amount = getattr(position_to_close, "amount", None) or getattr(position_to_close, "size", 0.0)

            # Fallback to notional calculation if amount is missing/zero
            if not amount:
                if isinstance(position_to_close, dict):
                    notional_val = position_to_close.get("notional") or 0.0
                    entry_price = position_to_close.get("entry_price") or 1.0
                else:
                    notional_val = getattr(position_to_close, "notional", 0.0)
                    entry_price = getattr(position_to_close, "entry_price", 1.0)
                amount = notional_val / entry_price

        except Exception:
            amount = 0.0

        # Determine amount to close
        if amount is None:
            amount = abs(position_to_close.size)
        else:
            amount = abs(amount)

        # Skip if position is already closed
        if amount <= 0:
            self.logger.info(f"⏭️ Position {trade_id} already closed (size: {amount})")
            return {"status": "skipped", "reason": "Position already closed"}

        # Ensure minimum notional
        if amount < 0.001:
            amount = 0.0

        # Format amount to exchange precision
        if hasattr(self.exchange_adapter, "amount_to_precision"):
            amount = float(self.exchange_adapter.amount_to_precision(position_to_close.symbol, amount))

        close_order = {
            "symbol": position_to_close.symbol,
            "type": "market",
            "side": close_side,
            "amount": amount,
            "params": {},  # Don't send reduceOnly in Hedge Mode - Binance infers from positionSide
        }

        try:
            result = await self.exchange_adapter.execute_order(close_order)
        except Exception as e:
            # Check for ReduceOnly rejection (Binance error code -2022)
            error_msg = str(e)
            if "ReduceOnly Order is rejected" in error_msg or "-2022" in error_msg:
                self.logger.warning(f"⚠️ ReduceOnly rejected for {trade_id}. Verifying actual position state...")

                # Fetch actual position from exchange
                try:
                    positions = await self.exchange_adapter.fetch_positions([position_to_close.symbol])
                    actual_position = None
                    for p in positions:
                        # Match by symbol (handle potential formatting differences)
                        p_symbol = p.get("symbol", "").replace("/", "").replace(":", "")
                        target_symbol = position_to_close.symbol.replace("/", "").replace(":", "")
                        if p_symbol == target_symbol or p.get("symbol") == position_to_close.symbol:
                            actual_position = p
                            break

                    actual_size = (
                        float(actual_position.get("contracts", 0) or actual_position.get("amount", 0))
                        if actual_position
                        else 0.0
                    )

                    if actual_size == 0:
                        self.logger.info(f"✅ Position {trade_id} is actually CLOSED on exchange. Confirming close.")
                        # Position is already closed, confirm it
                        if not skip_confirm_close:
                            self.position_tracker.confirm_close(
                                trade_id=trade_id,
                                exit_price=position_to_close.entry_price,  # Use entry price as fallback
                                exit_reason="MANUAL_SYNC",
                                pnl=0.0,  # Unknown PnL, assume 0 or fetch from trade history if possible
                                fee=0.0,
                            )
                        return {"status": "closed", "reason": "already_closed_on_exchange"}

                    else:
                        self.logger.info(f"🔄 Position size mismatch. Retry close with actual size: {actual_size}")
                        # Retry with actual size
                        close_order["amount"] = actual_size
                        result = await self.exchange_adapter.execute_order(close_order)

                except Exception as retry_error:
                    self.logger.error(f"❌ Failed to recover from ReduceOnly rejection: {retry_error}")
                    raise e  # Raise original error if recovery fails
            else:
                raise e  # Raise other errors

        if not result:
            raise ValueError(f"Failed to execute close order for position {trade_id}")

        # Safe access to result fields
        exit_price = result.get("price", 0.0) if result else 0.0
        pnl = result.get("realizedPnl", 0.0) if result else 0.0
        fee_info = result.get("fee", {}) if result else {}
        fee = fee_info.get("cost", 0.0) if isinstance(fee_info, dict) else 0.0

        # Only confirm close if not skipped (allows TestingDataSource to handle PnL calculation)
        if not skip_confirm_close:
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

        # Accept both limit orders (open/opened) and market orders (closed/new)
        status = result.get("status")
        if status not in ["open", "opened", "closed", "new"]:
            error_msg = (
                f"❌ Status de orden inválido: '{status}'. "
                f"Se esperaba 'open', 'opened', 'closed' o 'new'. "
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

    async def _fetch_positions(self, symbols: list = None):
        """Return normalized positions via ExchangeStateSync when possible, fallback to connector."""
        try:
            synced = await self.state_sync.sync_positions()
            if symbols:
                syms = set(symbols)
                return [p for p in synced if getattr(p, "symbol", None) in syms]
            return synced
        except Exception:
            return await self.exchange_adapter.connector.fetch_positions(symbols)

    async def _setup_oco_orders(self, order: dict, main_result: dict) -> tuple:
        """
        OCO Monitor: Crea órdenes TP/SL después de la orden principal.

        Responsable de:
        1. Detectar si hay TP/SL en la orden
        2. Calcular precios absolutos desde multiplicadores
          3. Crear órdenes TP y SL como órdenes limit separadas (creadas en paralelo para
              reducir ventana de riesgo de "immediate-trigger")
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

        # Preferir precio confirmado por WebSocket cuando esté disponible
        entry_price = None
        try:
            # Si el main_result indica que se usó la confirmación WS, preferir ese precio
            if main_result.get("used_ws_confirm"):
                entry_price = main_result.get("price") or main_result.get("avgPrice")

            # Si no hay confirmación WS, usar price/avgPrice si están presentes
            if not entry_price:
                entry_price = main_result.get("price") or main_result.get("avgPrice")

            # Como último recurso, intentar fetch_order para obtener average/avgPrice
            if (not entry_price or entry_price <= 0) and main_result.get("id"):
                try:
                    self.logger.info(f"🔍 Fetching order {main_result.get('id')} to get execution price...")
                    fetched_order = await self.exchange_adapter.connector.fetch_order(
                        main_result.get("id"), order.get("symbol")
                    )
                    self.logger.info(f"📋 Fetched order data: {fetched_order}")
                    entry_price = (
                        fetched_order.get("average")
                        or fetched_order.get("avgPrice")
                        or fetched_order.get("price")
                        or entry_price
                    )
                    self.logger.info(f"💰 Extracted entry_price: {entry_price}")
                    # mark that we used rest fallback for instrumentation
                    main_result["used_rest_fallback"] = True
                except Exception as e:
                    self.logger.warning(f"⚠️ fetch_order fallback failed: {e}", exc_info=True)
        except Exception as e:
            self.logger.warning(f"⚠️ Error obtaining execution price from main_result: {e}")

        # Si aún no hay precio, fallar claramente
        if not entry_price or entry_price <= 0:
            raise OCOConfigurationError(f"No valid execution price for TP/SL calculation. Got: {entry_price}")

        symbol = order.get("symbol")
        # IMPORTANTE: Obtener amount del RESULTADO de la orden principal, no de la orden original
        amount = main_result.get("amount") or order.get("amount")
        side = order.get("side")

        # Aumentar margen de seguridad para evitar "Order would immediately trigger"
        if entry_price < 0.01:
            safety_margin_factor = 0.01  # 1% para precios muy pequeños
        elif entry_price < 0.1:
            safety_margin_factor = 0.005  # 0.5% para precios pequeños
        else:
            safety_margin_factor = 0.002  # 0.2% para precios normales

        # Delegar cálculo de precios al adaptador (centralización de lógica)
        # El adaptador maneja la lógica de porcentajes vs multiplicadores y dirección (LONG/SHORT)
        try:
            tp_price, sl_price = await self.exchange_adapter.calculate_tpsl_prices(order, entry_price)
        except Exception as e:
            raise OCOConfigurationError(f"Error calculating TP/SL prices: {e}")

        if not tp_price or not sl_price:
            raise OCOConfigurationError("Adapter returned None for TP/SL prices")

        self.logger.info(f"📊 OCO Monitor | Entry: ${entry_price:.8f} | TP: ${tp_price:.8f} | SL: ${sl_price:.8f}")

        # Rounding: intentar ajustar TP/SL al tick size/precision del exchange antes de validar
        def _round_price_to_exchange(sym: str, price: float) -> float:
            try:
                if hasattr(self.exchange_adapter, "price_to_precision"):
                    pstr = self.exchange_adapter.price_to_precision(sym, price)
                    return float(pstr)

                # Legacy fallback
                exch = getattr(self.exchange_adapter, "exchange", None)
                if exch and hasattr(exch, "price_to_precision"):
                    # price_to_precision devuelve string formateada
                    pstr = exch.price_to_precision(sym, price)
                    return float(pstr)
            except Exception:
                pass
            # Fallback: no rounding disponible, devolver original
            return price

        tp_price_rounded = _round_price_to_exchange(symbol, tp_price)
        sl_price_rounded = _round_price_to_exchange(symbol, sl_price)

        if tp_price_rounded != tp_price or sl_price_rounded != sl_price:
            self.logger.info(
                f"🔧 Rounded TP/SL to exchange precision | TP: {tp_price} -> {tp_price_rounded} | SL: {sl_price} -> {sl_price_rounded}"
            )

        tp_price = tp_price_rounded
        sl_price = sl_price_rounded

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

        # Mejorar resiliencia: aumentar retries y usar backoff exponencial
        MAX_RETRIES = 5
        tp_order_id = None
        sl_order_id = None
        tp_attempts = []
        sl_attempts = []

        # Helper to create order with retries. Return a structured result so we can
        # act atomically when creating both TP and SL concurrently.
        async def _attempt_create_structured(payload, attempts_list, tag: str):
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # Debug instrumentation: log entering attempt and payload
                    self.logger.debug("🔁 %s attempt %s/%s - payload: %s", tag, attempt, MAX_RETRIES, payload)
                    t0 = time.time()
                    self.logger.debug(
                        "🔁 %s attempt %s/%s - creating order payload: %s", tag, attempt, MAX_RETRIES, payload
                    )
                    res = await self.exchange_adapter.execute_order(payload)
                    t1 = time.time()
                    attempts_list.append({"attempt": attempt, "ok": True, "duration_ms": int((t1 - t0) * 1000)})
                    return {"ok": True, "result": res}
                except Exception as e:
                    t1 = time.time()
                    err_str = str(e)
                    attempts_list.append(
                        {"attempt": attempt, "ok": False, "error": err_str, "duration_ms": int((t1 - t0) * 1000)}
                    )
                    # Detect immediate-trigger-like responses (fail fast semantics)
                    low_err = err_str.lower()
                    immediate = False
                    if (
                        "order would immediately trigger" in low_err
                        or "-2021" in low_err
                        or "immediately trigger" in low_err
                    ):
                        immediate = True
                        self.logger.error(f"❌ Immediate-trigger error detected for {tag}, failing fast: {err_str}")

                    # Log error details to help diagnosis (exchange msg / code if present)
                    self.logger.warning(f"⚠️ {tag} order create attempt {attempt} failed: {err_str}")
                    # If immediate-trigger, return quickly to let the caller cancel sibling
                    if immediate:
                        return {"ok": False, "immediate": True, "error": err_str}

                    # Exponential backoff with cap
                    backoff = min(0.25 * (2 ** (attempt - 1)), 5.0)
                    await asyncio.sleep(backoff)
            return {"ok": False, "immediate": False, "error": "max_retries_exhausted"}

        # Validate both TP and SL prices are present and positive
        if not tp_price:
            raise OCOConfigurationError("TP price is zero or invalid")
        if not sl_price:
            raise OCOConfigurationError("SL price is zero or invalid")

        # Create TP order (take profit market)
        # One-Way Mode: reduceOnly=True, side=opposite
        tp_payload = {
            "symbol": symbol,
            "side": close_side,
            "amount": amount,
            "type": "take_profit_market",
            "params": {
                "stopPrice": tp_price,
                "reduceOnly": True,
            },
        }

        # Validate that TP is sufficiently far from current market to avoid
        # immediate-trigger errors from exchanges (e.g. Binance).
        # Use the previously calculated safety margin as a minimum required %.
        required_margin_pct = max(safety_margin_factor, 0.002)  # at least 0.2%
        try:
            if current_market_price and current_market_price > 0:
                if side == "LONG":
                    min_allowed_tp = current_market_price * (1.0 + required_margin_pct)
                    if tp_price <= min_allowed_tp:
                        msg = (
                            f"TP order would immediately trigger. Entry: ${entry_price:.8f}, "
                            f"TP: ${tp_price:.8f}, Market: ${current_market_price:.8f}. "
                            f"Increase TP margin or reduce position size."
                        )
                        self.logger.error(f"❌ {msg}")
                        raise TPOrderCreationError(msg)
                else:  # SHORT
                    max_allowed_tp = current_market_price * (1.0 - required_margin_pct)
                    if tp_price >= max_allowed_tp:
                        msg = (
                            f"TP order would immediately trigger. Entry: ${entry_price:.8f}, "
                            f"TP: ${tp_price:.8f}, Market: ${current_market_price:.8f}. "
                            f"Increase TP margin or reduce position size."
                        )
                        self.logger.error(f"❌ {msg}")
                        raise TPOrderCreationError(msg)
        except TPOrderCreationError:
            raise
        except Exception as e:
            # Non-fatal: proceed to attempts but log the anomaly
            self.logger.warning(f"⚠️ Could not validate TP distance: {e}")

        # Create SL order (stop market)
        # One-Way Mode: reduceOnly=True, side=opposite
        sl_payload = {
            "symbol": symbol,
            "side": close_side,
            "amount": amount,
            "type": "stop_market",
            "params": {
                "stopPrice": sl_price,
                "reduceOnly": True,
            },
        }

        # Validate SL proximity as well (mirror of TP validation) before creation
        try:
            if current_market_price and current_market_price > 0:
                if side == "LONG":
                    max_allowed_sl = current_market_price * (1.0 - required_margin_pct)
                    if sl_price >= max_allowed_sl:
                        msg = (
                            f"SL order would immediately trigger. Entry: ${entry_price:.8f}, "
                            f"SL: ${sl_price:.8f}, Market: ${current_market_price:.8f}. "
                            f"Increase SL margin or reduce position size."
                        )
                        self.logger.error(f"❌ {msg}")
                        raise SLOrderCreationError(msg)
                else:  # SHORT
                    min_allowed_sl = current_market_price * (1.0 + required_margin_pct)
                    if sl_price <= min_allowed_sl:
                        msg = (
                            f"SL order would immediately trigger. Entry: ${entry_price:.8f}, "
                            f"SL: ${sl_price:.8f}, Market: ${current_market_price:.8f}. "
                            f"Increase SL margin or reduce position size."
                        )
                        self.logger.error(f"❌ {msg}")
                        raise SLOrderCreationError(msg)
        except SLOrderCreationError:
            raise

        # Now that both TP and SL passed validation (or we didn't raise), create them concurrently
        # Debug instrumentation: record payloads for diagnostics
        try:
            # Use lazy formatting to avoid exceptions during debug string creation
            self.logger.debug("🔁 Preparing OCO payloads: TP=%s | SL=%s", tp_payload, sl_payload)
        except Exception:
            pass
        tp_task = asyncio.create_task(_attempt_create_structured(tp_payload, tp_attempts, "TP"))
        sl_task = asyncio.create_task(_attempt_create_structured(sl_payload, sl_attempts, "SL"))
        tp_res_struct, sl_res_struct = await asyncio.gather(tp_task, sl_task)

        # Helper shorthand
        tp_ok = bool(tp_res_struct and tp_res_struct.get("ok"))
        sl_ok = bool(sl_res_struct and sl_res_struct.get("ok"))

        # If both ok, great
        if tp_ok and sl_ok:
            tp_order_id = tp_res_struct["result"].get("id")
            sl_order_id = sl_res_struct["result"].get("id")
            self.logger.info(f"✅ TP order created: {tp_order_id} @ ${tp_price:.8f}")
            self.logger.info(f"✅ SL order created: {sl_order_id} @ ${sl_price:.8f}")
        else:
            # If one failed but the other succeeded, cancel the successful one and raise
            if tp_ok and not sl_ok:
                # Check immediate trigger
                if sl_res_struct.get("immediate"):
                    # Cancel created TP and raise TPOrderCreationError so caller can handle
                    try:
                        await self.exchange_adapter.cancel_order(tp_res_struct["result"].get("id"), symbol)
                        self.logger.info(
                            f"🔄 Cancelled TP order {tp_res_struct['result'].get('id')} due to SL immediate-trigger error"
                        )
                    except Exception as e:
                        self.logger.error(f"❌ Failed to cancel TP after SL immediate-trigger: {e}")
                    raise SLOrderCreationError(sl_res_struct.get("error"))
                else:
                    # SL failed for other reason; cancel TP and raise
                    try:
                        await self.exchange_adapter.cancel_order(tp_res_struct["result"].get("id"), symbol)
                        self.logger.info(
                            f"🔄 Cancelled TP order {tp_res_struct['result'].get('id')} due to SL creation failure"
                        )
                    except Exception as e:
                        self.logger.error(f"❌ Failed to cancel TP after SL failure: {e}")
                    raise SLOrderCreationError(sl_res_struct.get("error"))

            if sl_ok and not tp_ok:
                if tp_res_struct.get("immediate"):
                    try:
                        await self.exchange_adapter.cancel_order(sl_res_struct["result"].get("id"), symbol)
                        self.logger.info(
                            f"🔄 Cancelled SL order {sl_res_struct['result'].get('id')} due to TP immediate-trigger error"
                        )
                    except Exception as e:
                        self.logger.error(f"❌ Failed to cancel SL after TP immediate-trigger: {e}")
                    raise TPOrderCreationError(tp_res_struct.get("error"))
                else:
                    try:
                        await self.exchange_adapter.cancel_order(sl_res_struct["result"].get("id"), symbol)
                        self.logger.info(
                            f"🔄 Cancelled SL order {sl_res_struct['result'].get('id')} due to TP creation failure"
                        )
                    except Exception as e:
                        self.logger.error(f"❌ Failed to cancel SL after TP failure: {e}")
                    raise TPOrderCreationError(tp_res_struct.get("error"))

            # Neither succeeded
            self.logger.error(
                f"❌ Both TP and SL creation failed. TP attempts: {tp_attempts} | SL attempts: {sl_attempts}"
            )
            if tp_res_struct and tp_res_struct.get("immediate"):
                raise TPOrderCreationError(tp_res_struct.get("error"))
            if sl_res_struct and sl_res_struct.get("immediate"):
                raise SLOrderCreationError(sl_res_struct.get("error"))
                raise OCOConfigurationError("Both TP and SL creations failed after retries")
            else:
                # If TP couldn't be created after retries, raise to trigger failure handling
                self.logger.error(f"❌ Failed to create TP after {MAX_RETRIES} attempts: {tp_attempts}")
                raise TPOrderCreationError(f"Failed to create TP after {MAX_RETRIES} attempts")

        # Attach attempt metadata to logs (non-critical)
        try:
            self.logger.debug({"tp_attempts": tp_attempts, "sl_attempts": sl_attempts})
        except Exception:
            pass

        return tp_order_id, sl_order_id, entry_price  # Also return entry_price for position tracking

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
            side_raw = getattr(position, "side", None)
            if not side_raw and isinstance(position, dict):
                side_raw = position.get("side")
            close_side = "sell" if (str(side_raw).upper() == "LONG" or str(side_raw).lower() == "buy") else "buy"

            # Compute amount (contracts) safely
            if isinstance(position, dict):
                size_val = abs(position.get("contracts", 0) or position.get("amount", 0))
            else:
                size_val = abs(getattr(position, "size", 0))

            # Cerrar con orden MARKET
            close_order = await self.exchange_adapter.execute_order(
                {
                    "symbol": getattr(
                        position, "symbol", position.get("symbol") if isinstance(position, dict) else None
                    ),
                    "side": close_side,
                    "amount": size_val,
                    "type": "market",
                    "params": {"reduceOnly": True},
                }
            )

            # Calcular PnL
            # Safe access to returned payloads (some connectors use dicts for fee, others float)
            exit_price = (
                close_order.get("price", position.entry_price)
                if isinstance(close_order, dict)
                else position.entry_price
            )
            fee_info = close_order.get("fee", {}) if isinstance(close_order, dict) else {}
            if isinstance(fee_info, dict):
                fee = fee_info.get("cost", 0.0)
            else:
                try:
                    fee = float(fee_info) if fee_info is not None else 0.0
                except Exception:
                    fee = 0.0
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
        return calculate_position_pnl(position, exit_price, fee)

    async def _cancel_sibling_order(
        self, order_id: Optional[str], order_type: str, symbol: str, trade_id: Optional[str] = None
    ):
        """Cancela una orden hermana (TP o SL) si existe y está activa.

        Args:
            order_id: ID de la orden a cancelar
            order_type: Tipo de orden ("TP", "SL", "sibling", etc.)
            symbol: Símbolo de la orden
            trade_id: ID del trade asociado (opcional). Si se provee y la orden se cancela,
                     verificará si la posición quedó sin protección y la cerrará.
        """
        if not order_id:
            return

        order_was_cancelled = False

        try:
            # PASO 1: Verificar si la orden aún existe y está activa
            should_cancel = False  # Default to NOT cancel if we can't verify
            try:
                order_status = await self.exchange_adapter.fetch_order(order_id, symbol)
                if order_status.get("status") in ["closed", "canceled", "expired"]:
                    self.logger.info(
                        f"ℹ️ Orden {order_type} {order_id} ya está {order_status.get('status')}, no necesita cancelación"
                    )
                    should_cancel = False
                elif order_status.get("status") in ["open", "new"]:
                    # Order is active, safe to cancel
                    should_cancel = True
                else:
                    self.logger.warning(
                        f"⚠️ Orden {order_type} {order_id} tiene estado desconocido: {order_status.get('status')}"
                    )
                    should_cancel = False
            except Exception as e:
                # Si no podemos obtener el estado, NO cancelar (podría ser un timeout temporal)
                # Solo registramos el error y dejamos la orden intacta
                self.logger.warning(
                    f"⚠️ No se pudo verificar estado de orden {order_type} {order_id} ({e}). NO cancelando por seguridad."
                )
                should_cancel = False

            # PASO 2: Proceder a cancelar si es necesario
            if should_cancel:
                try:
                    await self.exchange_adapter.cancel_order(order_id, symbol)
                    self.logger.info(f"✅ Orden {order_type} cancelada exitosamente: {order_id}")
                    order_was_cancelled = True
                except Exception as e:
                    # Si falla la cancelación, logueamos pero no lanzamos error (puede que ya no exista)
                    self.logger.warning(
                        f"⚠️ Falló cancelación de orden {order_type} {order_id} (posiblemente ya cerrada): {e}"
                    )

        except Exception as e:
            # Este bloque solo debería ejecutarse si hay un error real inesperado
            self.logger.error(f"❌ Error inesperado cancelando orden {order_type} {order_id}: {e}")

        # PASO 3: ATOMICITY PROTECTION - Si se canceló una orden protectora, verificar integridad de la posición
        if order_was_cancelled and trade_id:
            had_errors = await self._check_position_integrity_after_cancellation(trade_id, order_type, symbol)
            if had_errors:
                # Set flag to trigger conditional validation
                self.integrity_check_failed = True
                self.logger.warning(f"⚠️ Integrity check had errors for {trade_id}, enabling conditional validation")

    async def _check_position_integrity_after_cancellation(
        self, trade_id: str, cancelled_order_type: str, symbol: str
    ) -> bool:
        """Verifica la integridad de una posición después de cancelar una orden protectora.

        Si ambas órdenes TP/SL están canceladas o faltantes, cierra la posición inmediatamente
        para mantener la atomicidad del sistema de 3 órdenes.

        Args:
            trade_id: ID del trade
            cancelled_order_type: Tipo de orden que se acaba de cancelar ("TP", "SL", etc.)
            symbol: Símbolo de la posición

        Returns:
            True si hubo errores al verificar/cerrar la posición, False si todo OK
        """
        try:
            # Buscar la posición en el tracker
            position = self.position_tracker.get_position(trade_id)
            if not position:
                self.logger.debug(f"Position {trade_id} not found in tracker, skipping integrity check")
                return False

            # Verificar si las órdenes TP/SL existen en el exchange
            tp_exists = False
            sl_exists = False
            verification_error = False

            if position.tp_order_id:
                try:
                    tp_order = await self._fetch_order_safely(position.tp_order_id, symbol)
                    tp_exists = tp_order is not None and tp_order.get("status") in ["open", "new"]
                except Exception as e:
                    self.logger.warning(f"⚠️ Error verifying TP order {position.tp_order_id}: {e}")
                    # Classify error to determine if validation is needed
                    classification = self.error_classifier.classify(e)
                    if classification.is_retriable:
                        self.logger.info(
                            f"🔄 Retriable error ({classification.category.value}), will trigger validation"
                        )
                        verification_error = True
                    else:
                        self.logger.debug(
                            f"❌ Non-retriable error ({classification.category.value}), skipping validation trigger"
                        )

            if position.sl_order_id:
                try:
                    sl_order = await self._fetch_order_safely(position.sl_order_id, symbol)
                    sl_exists = sl_order is not None and sl_order.get("status") in ["open", "new"]
                except Exception as e:
                    self.logger.warning(f"⚠️ Error verifying SL order {position.sl_order_id}: {e}")
                    # Classify error to determine if validation is needed
                    classification = self.error_classifier.classify(e)
                    if classification.is_retriable:
                        self.logger.info(
                            f"🔄 Retriable error ({classification.category.value}), will trigger validation"
                        )
                        verification_error = True
                    else:
                        self.logger.debug(
                            f"❌ Non-retriable error ({classification.category.value}), skipping validation trigger"
                        )

            # Si falta alguna orden protectora, cerrar la posición
            if not tp_exists or not sl_exists:
                missing_orders = []
                if not tp_exists:
                    missing_orders.append("TP")
                if not sl_exists:
                    missing_orders.append("SL")

                self.logger.warning(
                    f"🚨 ATOMICITY VIOLATION | Position {trade_id} missing protective orders: {', '.join(missing_orders)}"
                )
                self.logger.info(f"🛡️ Closing position {trade_id} to maintain atomicity")

                # Cerrar la posición inmediatamente
                try:
                    await self.close_position(trade_id, skip_confirm_close=False)
                    self.logger.info(f"✅ Position {trade_id} closed successfully (PROTECTIVE_CLOSE)")
                    return verification_error  # Return True only if there were verification errors
                except Exception as e:
                    self.logger.error(f"❌ Failed to close unprotected position {trade_id}: {e}")
                    return True  # Error closing position
            else:
                self.logger.debug(f"✅ Position {trade_id} integrity OK (both TP and SL exist)")
                return verification_error

        except Exception as e:
            self.logger.error(f"❌ Error checking position integrity for {trade_id}: {e}", exc_info=True)
            return True  # Error during check

    async def monitor_positions(self) -> List[Dict[str, Any]]:
        """
        Método centralizado para monitorear posiciones abiertas y emular OCO.

        Responsabilidades:
        1. Iterar sobre posiciones abiertas.
        2. Verificar estado de órdenes TP/SL.
        3. Si una se ejecuta, cancelar la otra y confirmar el cierre.
        4. Si ambas órdenes desaparecen, cerrar la posición para evitar posiciones huérfanas.

        Returns:
            List[Dict]: Lista de resultados de posiciones cerradas en esta iteración.
        """
        self.logger.debug("🔍 Monitoring open positions...")
        closed_results = []
        # Usar una copia de la lista para poder modificarla durante la iteración
        for position in list(self.position_tracker.open_positions):
            try:
                tp_order = await self._fetch_order_safely(position.tp_order_id, position.symbol)
                sl_order = await self._fetch_order_safely(position.sl_order_id, position.symbol)

                # Escenario 1: TP ejecutado
                if tp_order and tp_order.get("status") in ["closed", "filled"]:
                    self.logger.info(f"🎯 TAKE PROFIT DETECTED for {position.symbol}")
                    result = await self._handle_position_closure(position, tp_order, "TP", sl_order)
                    if result:
                        closed_results.append(result)
                    continue  # Mover a la siguiente posición

                # Escenario 2: SL ejecutado
                if sl_order and sl_order.get("status") in ["closed", "filled"]:
                    self.logger.info(f"🛡️ STOP LOSS DETECTED for {position.symbol}")
                    result = await self._handle_position_closure(position, sl_order, "SL", tp_order)
                    if result:
                        closed_results.append(result)
                    continue

                # Escenario 3: Ambas órdenes TP/SL han desaparecido (canceladas o no encontradas)
                if not tp_order and not sl_order:
                    self.logger.warning(f"⚠️ Both TP/SL orders missing for {position.symbol}. Closing position.")
                    # Estimar precio de salida (usar precio de entrada como fallback neutro)
                    exit_price = position.entry_price
                    result = await self._handle_position_closure(
                        position, {"price": exit_price}, "ORPHANED_ORDERS_MISSING", None
                    )
                    if result:
                        closed_results.append(result)
                    continue

            except Exception as e:
                self.logger.error(f"❌ Error monitoring position {position.trade_id}: {e}", exc_info=True)

        return closed_results

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
    ) -> Optional[Dict]:
        """Maneja el cierre de una posición, cancelando la orden hermana y confirmando."""
        self.logger.info(f"📋 Closing position | Symbol: {position.symbol} | Reason: {reason}")

        # Cancelar la orden hermana (TP/SL restante)
        sibling_id = None
        if sibling_order:
            sibling_id = sibling_order.get("id")

        # Fallback: determinar ID desde la posición si no se pasó la orden
        if not sibling_id:
            if reason == "TP":
                sibling_id = position.sl_order_id
            elif reason == "SL":
                sibling_id = position.tp_order_id

        if sibling_id:
            self.logger.info(f"🔄 Cancelling sibling order ({reason} counterpart): {sibling_id}")
            await self._cancel_sibling_order(sibling_id, "sibling", position.symbol, position.trade_id)

        # Cancelar el main_order_id si todavía existe y está abierta
        if position.main_order_id:
            self.logger.info(f"🔄 Cancelling main_order_id: {position.main_order_id}")
            await self._cancel_sibling_order(position.main_order_id, "main_order", position.symbol, position.trade_id)

        # Calcular PnL y confirmar el cierre
        exit_price = executed_order.get("price", position.entry_price)
        fee_info = executed_order.get("fee") or {}
        if isinstance(fee_info, dict):
            fee = fee_info.get("cost", 0.0)
        else:
            try:
                fee = float(fee_info) if fee_info is not None else 0.0
            except Exception:
                fee = 0.0
        pnl = self._calculate_position_pnl(position, exit_price, fee)

        self.logger.info(
            f"✅ CONFIRMED CLOSE | {position.symbol} {position.side} | "
            f"Entry: {position.entry_price:.2f} | Exit: {exit_price:.2f} ({reason}) | "
            f"PnL: {pnl:+.2f} | Fee: {fee:.2f}"
        )

        return self.position_tracker.confirm_close(position.trade_id, exit_price, reason, pnl, fee)

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
            # Compute notional safely
            try:
                if isinstance(position, dict):
                    notional_val = position.get("notional") or (position.get("amount") * position.get("entry_price", 0))
                else:
                    notional_val = getattr(position, "notional", None)
                    if notional_val is None:
                        notional_val = getattr(position, "size", 0) * getattr(position, "entry_price", 0)
            except Exception:
                notional_val = 0.0

            amount = notional_val / position.entry_price if position.entry_price else 0
            market_close_order = await self.exchange_adapter.execute_order(
                {
                    "symbol": position.symbol,
                    "side": close_side,
                    "amount": amount,
                    "type": "market",
                    "params": {"reduceOnly": True},
                }
            )

            exit_price = (
                market_close_order.get("price", position.entry_price)
                if isinstance(market_close_order, dict)
                else position.entry_price
            )
            fee_info = market_close_order.get("fee", {}) if isinstance(market_close_order, dict) else {}
            if isinstance(fee_info, dict):
                fee = fee_info.get("cost", 0.0)
            else:
                try:
                    fee = float(fee_info) if fee_info is not None else 0.0
                except Exception:
                    fee = 0.0
            pnl = self._calculate_position_pnl(position, exit_price, fee)

            self.position_tracker.confirm_close(position.trade_id, exit_price, "ORPHANED", pnl, fee)
            self.logger.info(f"✅ Position {position.symbol} closed successfully.")

        except Exception as e:
            self.logger.error(f"❌ Failed to close orphaned position {position.symbol}: {e}")
            # Como último recurso, se cierra internamente para evitar que el capital quede bloqueado
            pnl = self._calculate_position_pnl(position, position.entry_price, 0.0)  # PnL cero
            self.position_tracker.confirm_close(position.trade_id, position.entry_price, "ORPHANED_FAIL", pnl, 0.0)
