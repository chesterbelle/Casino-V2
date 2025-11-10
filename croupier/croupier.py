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

from core.portfolio import PortfolioManager


class Croupier:
    """
    Tablero de control centralizado del Casino.

    El Croupier es el dueño del portfolio y coordina todas las
    operaciones de trading. Cualquier componente que necesite
    información del portfolio debe consultarle al Croupier.
    """

    def __init__(self, exchange_adapter, initial_balance: float = None):
        """
        Inicializa el Croupier.

        Args:
            exchange_adapter: Adaptador para comunicación con exchange
            initial_balance: Balance inicial en USDT (opcional para backward compatibility)

        Note:
            Si initial_balance no se provee, el Croupier funcionará en modo
            "pass-through" sin gestionar portfolio (backward compatibility).
        """
        self.logger = logging.getLogger("Croupier")
        self.exchange = exchange_adapter

        # Modo con portfolio management (nuevo)
        if initial_balance is not None:
            self.portfolio = PortfolioManager(initial_balance)
            self.logger.info(f"🎯 Croupier V2 initialized | Balance: ${initial_balance:,.2f}")
        # Modo pass-through (backward compatibility)
        else:
            self.portfolio = None
            self.logger.info("🎯 Croupier initialized (pass-through mode)")

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
        if self.portfolio:
            return self.portfolio.get_balance()
        # Backward compatibility: try to get from exchange/table
        if hasattr(self.exchange, "balance_manager"):
            return self.exchange.balance_manager.balance
        return 0.0

    def get_equity(self) -> float:
        """
        Retorna el equity total (balance + valor de posiciones).

        Returns:
            Equity total en USDT
        """
        if self.portfolio:
            return self.portfolio.get_equity()
        return self.get_balance()

    def get_open_positions(self) -> List[Dict]:
        """
        Retorna lista de posiciones abiertas.

        Returns:
            Lista de diccionarios con info de posiciones
        """
        if self.portfolio:
            return self.portfolio.get_open_positions()
        # Backward compatibility
        if hasattr(self.exchange, "position_tracker"):
            return self.exchange.position_tracker.get_open_positions()
        return []

    def get_position(self, trade_id: str) -> Optional[Dict]:
        """
        Obtiene una posición específica.

        Args:
            trade_id: ID del trade

        Returns:
            Diccionario con info de la posición o None
        """
        if self.portfolio:
            return self.portfolio.get_position(trade_id)
        # Backward compatibility
        if hasattr(self.exchange, "position_tracker"):
            return self.exchange.position_tracker.get_position(trade_id)
        return None

    def get_portfolio_state(self) -> Dict:
        """
        Retorna el estado completo del portfolio.

        Returns:
            Diccionario con balance, equity, y posiciones
        """
        if self.portfolio:
            return self.portfolio.get_portfolio_state()
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

    def execute_order(self, order: dict) -> dict:
        """
        Ejecuta una orden de trading.

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

        # 2. Verificar fondos (si no es ghost y tenemos portfolio)
        is_ghost = order.get("ghost", False)
        if not is_ghost and self.portfolio:
            if not self.portfolio.can_open_position(order["size"]):
                return self._insufficient_funds_result(order)

        # 3. Delegar ejecución al exchange
        try:
            result = self._execute_on_exchange(order)
        except Exception as e:
            self.logger.error(f"❌ Exchange execution failed: {e}")
            return self._execution_error_result(order, str(e))

        # 4. Actualizar portfolio (si no es ghost y tenemos portfolio)
        if not is_ghost and self.portfolio:
            try:
                self._update_portfolio(order, result)
            except Exception as e:
                self.logger.error(f"❌ Portfolio update failed: {e}")
                # Nota: La orden ya se ejecutó en el exchange,
                # pero no pudimos actualizar el portfolio local

        # 5. Enriquecer resultado con info de portfolio
        result["balance"] = self.get_balance()
        result["equity"] = self.get_equity()
        result["ghost"] = is_ghost

        # Log consolidado
        self._log_execution(order, result)

        return result

    def route_order(self, order: dict) -> dict:
        """
        Alias de execute_order para backward compatibility.

        Args:
            order: Diccionario con la orden a ejecutar

        Returns:
            Diccionario con el resultado de la ejecución
        """
        return self.execute_order(order)

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

    def _execute_on_exchange(self, order: dict) -> dict:
        """
        Delega la ejecución al exchange adapter.

        Si la orden tiene 'size' (USD nominal) pero no 'amount',
        el Croupier calcula el 'amount' usando el precio real del exchange.

        Args:
            order: Diccionario con la orden

        Returns:
            Resultado de la ejecución del exchange
        """
        # Si la orden tiene 'size' pero no 'amount', calcular amount
        if "size" in order and "amount" not in order:
            self.logger.info(f"🎯 Croupier will calculate amount from size={order['size']}")
            order = self._calculate_amount_from_size(order)
        elif "amount" in order:
            self.logger.info(f"✅ Order already has amount={order['amount']:.6f}, skipping calculation")

        # Usar execute_order_sync si existe (para adapters async)
        if hasattr(self.exchange, "execute_order_sync"):
            return self.exchange.execute_order_sync(order)
        else:
            return self.exchange.execute_order(order)

    def _calculate_amount_from_size(self, order: dict) -> dict:
        """
        Calcula el 'amount' en base currency desde 'size' (USD nominal).

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

        # Obtener precio actual del exchange
        if hasattr(self.exchange, "get_current_price"):
            current_price = self.exchange.get_current_price(symbol)
        else:
            # Fallback: intentar obtener del balance_manager si existe
            if hasattr(self.exchange, "balance_manager"):
                current_price = getattr(self.exchange.balance_manager, "last_price", None)
            else:
                current_price = None

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

    def _update_portfolio(self, order: dict, result: dict):
        """
        Actualiza el portfolio basado en el resultado de ejecución.

        Args:
            order: Orden original
            result: Resultado de la ejecución
        """
        status = result.get("status", "unknown")

        # Aceptar tanto "open" (CCXT) como "opened" (normalizado)
        if status in ["open", "opened"]:
            # Posición abierta
            self.portfolio.open_position(
                trade_id=order.get("trade_id", "unknown"),
                symbol=order["symbol"],
                side=order["side"],
                size=order["size"],
                entry_price=result.get("entry_price", 0.0),
                take_profit=order["take_profit"],
                stop_loss=order["stop_loss"],
                timestamp=order.get("timestamp"),
            )

        elif status == "closed":
            # Posición cerrada
            self.portfolio.close_position(
                trade_id=order.get("trade_id", "unknown"),
                exit_price=result.get("exit_price", 0.0),
                exit_reason=result.get("exit_reason", "unknown"),
                fee=result.get("fee", 0.0),
                timestamp=result.get("timestamp"),
            )

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
