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
        }

    # ========================================
    # API Pública: Ejecución de Órdenes
    # ========================================

    async def execute_order(self, order: dict) -> dict:
        self._validate_order(order)

        if await self._has_open_position(order.get("symbol")):
            self.logger.warning(f"⚠️ Ya hay posición abierta para {order.get('symbol')}, rechazando orden")
            return {
                "status": "rejected",
                "reason": "Position already open for this symbol",
                "order": order,
            }

        required_margin = self.get_equity() * order.get("size", 0.0)
        if not self.balance_manager.can_open_position(required_margin):
            return self._insufficient_funds_result(order)

        try:
            result = await self._execute_on_exchange(order)
        except Exception as e:
            self.logger.error(f"❌ Exchange execution failed: {e}")
            return self._execution_error_result(order, str(e))

        # Register position for both limit orders (open/opened) and market orders (closed)
        if result.get("status") in ["open", "opened", "closed"]:
            trade_id = self.position_tracker.open_position(
                order=order,
                entry_price=result.get("price", 0.0),
                entry_timestamp=result.get("timestamp", ""),
                available_equity=self.get_equity(),
                main_order_id=result.get("id"),  # ID de la orden principal
                tp_order_id=result.get("tp_order_id"),
                sl_order_id=result.get("sl_order_id"),
            )

            # Register TP/SL pair for OCO manual monitoring
            tp_order_id = result.get("tp_order_id")
            sl_order_id = result.get("sl_order_id")
            if tp_order_id and sl_order_id:
                symbol = order.get("symbol", "")
                self.position_tracker.register_tpsl_pair(symbol, tp_order_id, sl_order_id)

            # If order was immediately closed (e.g., market order or instant execution),
            # register the close immediately
            if result.get("status") == "closed" and trade_id:
                exit_price = result.get("price") or result.get("entry_price") or 0.0
                pnl = result.get("pnl") or 0.0
                fee = result.get("fee") or 0.0
                # Extract trade_id from OpenPosition object if needed
                trade_id_str = trade_id.trade_id if hasattr(trade_id, "trade_id") else str(trade_id)
                self.logger.info(f"✅ Order immediately closed | trade_id={trade_id_str} | PnL={pnl}")
                try:
                    self.position_tracker.confirm_close(
                        trade_id=trade_id_str,
                        exit_price=float(exit_price) if exit_price else 0.0,
                        exit_reason="IMMEDIATE_CLOSE",
                        pnl=float(pnl) if pnl else 0.0,
                        fee=float(fee) if fee else 0.0,
                    )
                except Exception as e:
                    self.logger.error(f"❌ Error confirming close: {e}")

        result["balance"] = self.get_balance()
        result["equity"] = self.get_equity()
        self._log_execution(order, result)
        return result

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
        if result.get("status") not in ["open", "opened", "closed"]:
            self.logger.error(f"❌ La orden falló: {result}")
            return result

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

    async def sync_and_process_fills(self):
        self.logger.debug("🔄 Sincronizando fills para lógica OCO...")
        try:
            # Obtener fills básicos (agnósticos) del ExchangeStateSync
            recent_fills = await self.state_sync.sync_fills()

            for fill in recent_fills:
                if not fill.order_id:
                    continue

                # Normalizar el fill usando CCXTAdapter para obtener datos específicos del exchange
                raw_trade = {
                    "id": fill.trade_id,
                    "order": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "price": fill.price,
                    "amount": fill.amount,
                    "cost": fill.cost,
                    "fee": {"cost": fill.fee, "currency": fill.fee_currency},
                    "timestamp": fill.timestamp,
                    "datetime": fill.datetime,
                }

                # Usar CCXTAdapter para normalización específica del exchange
                normalized_fill = self.exchange_adapter.normalize_trade(raw_trade)
                realized_pnl = normalized_fill.get("realized_pnl", 0.0)
                _ = normalized_fill.get("close_reason", "UNKNOWN")

                for position in self.position_tracker.open_positions:
                    if fill.order_id == position.tp_order_id:
                        self.logger.info(f"🎯 HIT DE TAKE PROFIT DETECTADO para {position.symbol}")
                        await self._cancel_sibling_order(position.sl_order_id, "SL", position.symbol)
                        self.position_tracker.confirm_close(position.trade_id, fill.price, "TP", realized_pnl, fill.fee)
                        break

                    elif fill.order_id == position.sl_order_id:
                        self.logger.info(f"🛡️ HIT DE STOP LOSS DETECTADO para {position.symbol}")
                        await self._cancel_sibling_order(position.tp_order_id, "TP", position.symbol)
                        self.position_tracker.confirm_close(position.trade_id, fill.price, "SL", realized_pnl, fill.fee)
                        break
        except Exception as e:
            self.logger.error(f"❌ Error procesando fills para OCO: {e}", exc_info=True)

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

    async def monitor_oco_manual(self) -> None:
        """
        Monitor OCO manual execution.
        Should be called periodically from TradingSession or a central clock.
        """
        try:
            self.logger.debug("🔍 Monitoring OCO manual execution...")
            await self.position_tracker.monitor_oco_execution()
        except Exception as e:
            self.logger.error(f"❌ Error in OCO manual monitoring: {e}")
            # No re-raise para evitar fallar el cierre de posición)
