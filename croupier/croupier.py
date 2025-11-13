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

import logging
from typing import Dict, List, Optional

from core.portfolio.balance_manager import BalanceManager
from core.portfolio.position_tracker import PositionTracker
from exchanges.adapters.exchange_state_sync import ExchangeStateSync


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
        self.exchange = exchange_adapter

        # --- El Croupier ahora es dueño del estado ---
        self.balance_manager = BalanceManager(starting_balance=initial_balance)
        self.position_tracker = PositionTracker(mode="hybrid")  # Modo recomendado
        self.state_sync = ExchangeStateSync(exchange_adapter.connector)
        # --------------------------------------------

        self.logger.info(f"🎯 Croupier initialized as State Owner | Balance: ${initial_balance:,.2f}")

        # Alias para backward compatibility
        self.table = exchange_adapter

    # ========================================
    # API Pública: Información del Portfolio
    # ========================================

    def get_balance(self) -> float:
        """
        Retorna el balance disponible (cash).

        Returns:
            Balance en USDT
        """
        return self.balance_manager.get_balance()

    def get_equity(self) -> float:
        """
        Retorna el equity total (balance + valor de posiciones).

        Returns:
            Equity total en USDT
        """
        # Equity = balance + PnL no realizado de posiciones abiertas
        # (Esta lógica se puede refinar después)
        return self.balance_manager.get_equity()

    def get_open_positions(self) -> List[Dict]:
        """
        Retorna lista de posiciones abiertas.

        Returns:
            Lista de diccionarios con info de posiciones
        """
        return self.position_tracker.open_positions

    def get_position(self, trade_id: str) -> Optional[Dict]:
        """
        Obtiene una posición específica.

        Args:
            trade_id: ID del trade

        Returns:
            Diccionario con info de la posición o None
        """
        for pos in self.position_tracker.open_positions:
            if pos.trade_id == trade_id:
                return pos.__dict__
        return None

    def get_portfolio_state(self) -> Dict:
        """
        Retorna el estado completo del portfolio.

        Returns:
            Diccionario con balance, equity, y posiciones
        """
        return self.balance_manager.get_state()
        # Backward compatibility
        return {
            "balance": self.get_balance(),
            "equity": self.get_equity(),
            "open_positions_count": len(self.get_open_positions()),
            "open_positions": self.get_open_positions(),
        }

    # ========================================
    # API Pública: Ejecución de Órdenes
    # ========================================

    async def execute_order(self, order: dict) -> dict:
        """
        Ejecuta una orden de trading (async).

        Flujo:
        1. Validar orden
        2. Verificar fondos disponibles (si no es ghost)
        3. Delegar ejecución al exchange
        4. Actualizar portfolio con resultado (si no es ghost)
        5. Retornar resultado normalizado

        Args:
            order: Diccionario con la orden a ejecutar

        Returns:
            Diccionario con el resultado de la ejecución

        Raises:
            ValueError: Si la orden es inválida
        """
        # 1. Validar orden
        self._validate_order(order)

        # 2. NUEVO: Verificar que no hay posición abierta (prevenir múltiples posiciones)
        if await self._has_open_position(order.get("symbol")):
            self.logger.warning(f"⚠️ Ya hay posición abierta para {order.get('symbol')}, rechazando orden")
            return {
                "status": "rejected",
                "reason": "Position already open for this symbol",
                "order": order,
                "balance": self.get_balance(),
                "equity": self.get_equity(),
            }

        # 3. Verificar fondos usando nuestro propio BalanceManager
        is_ghost = order.get("ghost", False)
        # (La lógica de cálculo de margen requerido se refinará)
        required_margin = self.get_equity() * order.get("size", 0.0)
        if not is_ghost and not self.balance_manager.can_open_position(required_margin):
            return self._insufficient_funds_result(order)

        # 3. Delegar ejecución al exchange
        try:
            result = await self._execute_on_exchange(order)
        except Exception as e:
            self.logger.error(f"❌ Exchange execution failed: {e}")
            return self._execution_error_result(order, str(e))

        # 4. Actualizar portfolio (si no es ghost)
        if not is_ghost and result.get("status") in ["open", "opened"]:
            self.position_tracker.open_position(
                order=order,
                entry_price=result.get("price", 0.0),
                entry_timestamp=result.get("timestamp", ""),
                available_equity=self.get_equity(),
                tp_order_id=result.get("tp_order_id"),
                sl_order_id=result.get("sl_order_id"),
            )

        # 5. Enriquecer resultado con info de portfolio
        result["balance"] = self.get_balance()
        result["equity"] = self.get_equity()
        result["ghost"] = is_ghost

        # Log consolidado
        self._log_execution(order, result)

        return result

    async def route_order(self, order: dict) -> dict:
        """
        Alias de execute_order para backward compatibility (async).

        Args:
            order: Diccionario con la orden a ejecutar

        Returns:
            Diccionario con el resultado de la ejecución
        """
        return await self.execute_order(order)

    # ========================================
    # Métodos Privados: Validación
    # ========================================

    def _validate_order(self, order: dict):
        """
        Valida que la orden tenga todos los campos requeridos.

        Args:
            order: Diccionario con la orden

        Raises:
            ValueError: Si la orden es inválida
        """
        if not isinstance(order, dict):
            raise ValueError("Orden inválida: debe ser un dict estándar.")

        required = ("symbol", "side", "size", "take_profit", "stop_loss")
        for field in required:
            if field not in order:
                raise ValueError(f"Orden incompleta: falta '{field}'")

        # Validar side
        if order["side"] not in ("LONG", "SHORT"):
            raise ValueError(f"Side inválido: {order['side']} (debe ser LONG o SHORT)")

        # Validar size
        if order["size"] <= 0:
            raise ValueError(f"Size inválido: {order['size']} (debe ser > 0)")

    # ========================================
    # Métodos Privados: Ejecución
    # ========================================

    async def _execute_on_exchange(self, order: dict) -> dict:
        """
        Orquesta la creación de la posición y sus órdenes TP/SL.
        Implementa la lógica OCO manual.
        """
        # 1. Calcular 'amount' si no está presente
        if "size" in order and "amount" not in order:
            self.logger.info(f"🎯 Croupier calculará el 'amount' desde size={order['size']}")
            order = await self._calculate_amount_from_size(order)

        # 2. Crear la orden principal para abrir la posición
        main_order_result = await self.exchange.execute_order(order)
        if main_order_result.get("status") not in ["open", "opened"]:
            self.logger.error(f"❌ La orden principal falló: {main_order_result}")
            return main_order_result

        self.logger.info(f"✅ Orden principal ejecutada: {main_order_result.get('id')}")

        # 3. Crear órdenes TP y SL separadas
        tp_order_id, sl_order_id = await self._create_tpsl_orders(order, main_order_result)

        # 4. Devolver un resultado combinado
        main_order_result["tp_order_id"] = tp_order_id
        main_order_result["sl_order_id"] = sl_order_id
        return main_order_result

    async def _calculate_amount_from_size(self, order: dict) -> dict:
        """
        Calcula el 'amount' en base currency desde 'size' (USD nominal) (async).

        Args:
            order: Orden con 'size' (fracción de equity)

        Returns:
            Orden con 'amount' calculado
        """
        size_fraction = float(order["size"])
        leverage = order.get("leverage", 1)
        symbol = order["symbol"]

        # Obtener equity actual
        equity = self.get_equity()

        # Obtener precio actual - primero verificar si viene en la orden
        current_price = order.get("price")

        if current_price:
            self.logger.info(f"💰 Using price from order: {current_price}")
        else:
            # Obtener precio del exchange (async)
            if hasattr(self.exchange, "get_current_price"):
                current_price = await self.exchange.get_current_price(symbol)
            else:
                raise ValueError("Exchange adapter does not have get_current_price method")

            if not current_price:
                raise ValueError(f"Cannot get current price for {symbol} from exchange")

        # Calcular amount
        margin = equity * size_fraction  # USD a arriesgar
        position_value = margin * leverage  # USD de posición total
        amount = position_value / current_price  # Cantidad en base currency

        self.logger.info(
            f"📊 Croupier calculation | "
            f"Equity: ${equity:.2f} | "
            f"Size: {size_fraction*100:.2f}% | "
            f"Margin: ${margin:.2f} | "
            f"Leverage: {leverage}x | "
            f"Position: ${position_value:.2f} | "
            f"Price: ${current_price:.2f} | "
            f"Amount: {amount:.6f}"
        )

        # Crear nueva orden con amount
        order_with_amount = dict(order)
        order_with_amount["amount"] = amount

        return order_with_amount

    async def _create_tpsl_orders(
        self, base_order: dict, main_order_result: dict
    ) -> tuple[Optional[str], Optional[str]]:
        """Crea las órdenes de Take Profit y Stop Loss por separado."""
        tp_order_id, sl_order_id = None, None
        try:
            # Calcular precios absolutos de TP/SL
            _, sl_price = await self.exchange._calculate_tpsl_prices(base_order)
            tp_price, _ = await self.exchange._calculate_tpsl_prices(base_order)

            order_side = base_order["side"]
            close_side = "sell" if order_side == "LONG" else "buy"
            amount = float(main_order_result.get("amount", 0.0))

            # Crear orden Take Profit (Limit)
            if tp_price:
                tp_order = {
                    "symbol": base_order["symbol"],
                    "type": "limit",
                    "side": close_side,
                    "amount": amount,
                    "price": tp_price,
                    "params": {"reduceOnly": True},
                }
                tp_result = await self.exchange.execute_order(tp_order)
                tp_order_id = tp_result.get("id")
                self.logger.info(f"✅ Orden TP creada: {tp_order_id} @ {tp_price:.2f}")

            # Crear orden Stop Loss (Stop Market)
            if sl_price:
                sl_order = {
                    "symbol": base_order["symbol"],
                    "type": "stop_market",
                    "side": close_side,
                    "amount": amount,
                    "price": sl_price,  # Stop price
                    "params": {"reduceOnly": True},
                }
                sl_result = await self.exchange.execute_order(sl_order)
                sl_order_id = sl_result.get("id")
                self.logger.info(f"✅ Orden SL creada: {sl_order_id} @ {sl_price:.2f}")

        except Exception as e:
            self.logger.error(f"❌ Falló la creación de órdenes TP/SL: {e}", exc_info=True)
            # Opcional: intentar cancelar la posición principal si TP/SL fallan

        return tp_order_id, sl_order_id

    # ========================================
    # Métodos Privados: Resultados de Error
    # ========================================

    def _insufficient_funds_result(self, order: dict) -> dict:
        """
        Genera resultado de fondos insuficientes.

        Args:
            order: Orden original

        Returns:
            Diccionario con resultado de error
        """
        self.logger.warning(
            f"⚠️ Insufficient funds | Need: ${order['size']:,.2f} | " f"Have: ${self.get_balance():,.2f}"
        )

        return {
            "trade_id": order.get("trade_id", "unknown"),
            "status": "rejected",
            "reason": "insufficient_funds",
            "symbol": order.get("symbol", "unknown"),
            "balance": self.get_balance(),
            "equity": self.get_equity(),
            "ghost": order.get("ghost", False),
        }

    def _execution_error_result(self, order: dict, error: str) -> dict:
        """
        Genera resultado de error de ejecución.

        Args:
            order: Orden original
            error: Mensaje de error

        Returns:
            Diccionario con resultado de error
        """
        return {
            "trade_id": order.get("trade_id", "unknown"),
            "status": "error",
            "reason": "execution_error",
            "error": error,
            "symbol": order.get("symbol", "unknown"),
            "balance": self.get_balance(),
            "equity": self.get_equity(),
            "ghost": order.get("ghost", False),
        }

    # ========================================
    # Métodos Privados: Logging
    # ========================================

    def _log_execution(self, order: dict, result: dict):
        """
        Log consolidado de la ejecución.

        Args:
            order: Orden original
            result: Resultado de la ejecución
        """
        status = result.get("status", "unknown")
        symbol = order.get("symbol", "?")
        side = order.get("side", "?")
        is_ghost = order.get("ghost", False)

        if status == "rejected":
            self.logger.warning(f"🚫 Rejected | {symbol} {side} | {result.get('reason', 'unknown')}")
        elif status == "error":
            self.logger.error(f"❌ Error | {symbol} {side} | {result.get('error', 'unknown')}")
        elif status == "closed":
            result_type = result.get("result", "?")
            pnl = result.get("pnl", 0.0)
            exit_reason = result.get("exit_reason", "?")
            self.logger.info(
                f"🃏 Closed | {symbol} {side} | {exit_reason} | " f"{result_type} | PnL=${pnl:,.2f} | ghost={is_ghost}"
            )
        else:
            self.logger.debug(f"🃏 Exec | {symbol} {side} | status={status} | ghost={is_ghost}")

    async def sync_and_process_fills(self):
        """
        Sincroniza con el exchange para obtener nuevos fills (ejecuciones)
        y procesa la lógica OCO si una orden de TP/SL se ejecutó.
        """
        self.logger.debug("🔄 Sincronizando fills para lógica OCO...")
        try:
            recent_fills = await self.state_sync.sync_fills()
            for fill in recent_fills:
                if not fill.order_id:
                    continue

                # Buscar si el fill corresponde a una de nuestras posiciones abiertas
                for position in self.position_tracker.open_positions:
                    if fill.order_id == position.tp_order_id:
                        self.logger.info(f"🎯 HIT DE TAKE PROFIT DETECTADO para {position.symbol}")
                        await self._cancel_sibling_order(position.sl_order_id, "SL")
                        self.position_tracker.confirm_close(
                            position.trade_id, fill.price, "TP", fill.realized_pnl, fill.fee
                        )
                        break

                    elif fill.order_id == position.sl_order_id:
                        self.logger.info(f"🛡️ HIT DE STOP LOSS DETECTADO para {position.symbol}")
                        await self._cancel_sibling_order(position.tp_order_id, "TP")
                        self.position_tracker.confirm_close(
                            position.trade_id, fill.price, "SL", fill.realized_pnl, fill.fee
                        )
                        break
        except Exception as e:
            self.logger.error(f"❌ Error procesando fills para OCO: {e}", exc_info=True)

    async def _cancel_sibling_order(self, order_id: Optional[str], order_type: str):
        """Cancela la orden OCO hermana."""
        if not order_id:
            return
        try:
            self.logger.info(f"🗑️ Cancelando orden {order_type} hermana: {order_id}")
            await self.exchange.connector.cancel_order(order_id)
        except Exception as e:
            self.logger.error(f"❌ CRÍTICO: Falló al cancelar la orden {order_type} {order_id}: {e}", exc_info=True)
            # Aquí se podría añadir una alerta para el operador

    async def _has_open_position(self, symbol: str) -> bool:
        """
        Verifica si ya hay una posición abierta para el símbolo.

        Args:
            symbol: Símbolo a verificar

        Returns:
            True si hay posición abierta, False en caso contrario
        """
        try:
            # Si estamos en modo simulado (backtest), verificar posiciones internas
            if hasattr(self.exchange, "connector") and hasattr(self.exchange.connector, "open_positions"):
                # BacktestDataSource tiene open_positions
                open_positions = self.exchange.connector.open_positions
                for pos in open_positions:
                    if pos.get("symbol") == symbol:
                        return True
                return False

            # Si estamos en modo real/demo, verificar con el exchange
            if hasattr(self.exchange, "connector") and hasattr(self.exchange.connector, "fetch_positions"):
                positions = await self.exchange.connector.fetch_positions()
                for position in positions:
                    # Verificar si el símbolo coincide y hay contratos
                    pos_symbol = position.get("symbol", "")
                    contracts = abs(float(position.get("contracts", 0)))

                    # Normalizar símbolos (LTC/USDT:USDT -> LTC/USD:USD)
                    if pos_symbol.replace("USDT", "USD") == symbol.replace("USDT", "USD"):
                        if contracts > 0:
                            self.logger.info(f"📊 Posición encontrada: {pos_symbol} con {contracts} contratos")
                            return True
                return False

        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Error verifying open positions: {e}", exc_info=True)
            self.logger.warning("🛡️ SAFETY FIRST: Rejecting order to prevent duplicate positions.")
            # En caso de error, RECHAZAR la orden para evitar riesgo de posiciones duplicadas.
            return True

        return False
