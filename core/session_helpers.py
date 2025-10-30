"""
Session helpers and utilities for Casino V2 trading system.

This module provides utility functions for session management, balance handling,
and trade logging in the Casino V2 trading system.
"""

import logging
from typing import Dict, Optional, Any, Union

import config

logger = logging.getLogger("SessionHelpers")


def ask_initial_balance() -> float:
    """Pide balance inicial por consola con validación; fallback a config.STARTING_BALANCE.

    Solicita al usuario que ingrese un balance inicial válido. Si el input es inválido
    o vacío, usa el valor por defecto de config.STARTING_BALANCE.

    Returns:
        Balance inicial válido como float positivo.

    Example:
        >>> balance = ask_initial_balance()
        💰 Ingrese balance inicial (ej. 10000): 50000
        >>> print(balance)
        50000.0
    """
    try:
        raw = input("💰 Ingrese balance inicial (ej. 10000): ").strip()
        if not raw:
            raise ValueError
        value = float(raw.replace(",", ""))
        if value <= 0:
            raise ValueError
        return value
    except Exception:
        default = float(getattr(config, "STARTING_BALANCE", 10_000.0))
        print(f"⚠️ Valor inválido. Usando STARTING_BALANCE de config: {default:.2f}")
        return default


def set_table_balance(table: Any, amount: float) -> None:
    """Fuerza el balance inicial de la mesa con validación.

    Establece el balance inicial en el balance manager de la mesa.
    Compatible con diferentes implementaciones de balance managers.

    Args:
        table: Instancia de mesa (TableBacktest, TableCCXTPro, etc.).
        amount: Monto del balance inicial (debe ser positivo).

    Raises:
        ValueError: Si amount es negativo o cero.
    """
    if amount <= 0:
        raise ValueError(f"Balance amount must be positive, got {amount}")

    bm = getattr(table, "balance_manager", None)
    if not bm:
        logger.warning("Table has no balance_manager, cannot set balance")
        return

    try:
        bm.balance = amount
        bm.equity = amount
    except Exception as e:
        logger.debug(f"Direct balance setting failed: {e}")
        if hasattr(bm, "set_balance"):
            bm.set_balance(amount)
        else:
            logger.error(f"Cannot set balance on table {type(table).__name__}")
    bm = getattr(table, "balance_manager", None)
    if not bm:
        return
    try:
        bm.balance = amount
        bm.equity = amount
    except Exception:
        if hasattr(bm, "set_balance"):
            bm.set_balance(amount)


def get_table_state(table: Any) -> Dict[str, Union[float, int, str]]:
    """Obtiene el estado actual de la mesa de forma segura.

    Args:
        table: Instancia de mesa con balance_manager.

    Returns:
        Dict con estado del balance manager, o dict vacío si falla.

    Example:
        >>> state = get_table_state(table)
        >>> print(state)
        {'balance': 10000.0, 'equity': 9500.0}
    """
    bm = getattr(table, "balance_manager", None)
    if bm and hasattr(bm, "get_state"):
        try:
            return bm.get_state()
        except Exception as e:
            logger.debug(f"Failed to get table state: {e}")
            return {}
    return {}


def log_trade(action: str, verdict: Optional[Any], order: Dict[str, Any], result: Dict[str, Any], balance: Optional[float]) -> None:
    """Log estandarizado de trades con formato estructurado.

    Registra información detallada de cada trade incluyendo símbolo, lado,
    tamaño de posición, resultado y métricas financieras.

    Args:
        action: Tipo de acción ('OPEN', 'CLOSE', 'GHOST', etc.).
        verdict: Objeto Verdict de Gemini (opcional).
        order: Dict con detalles de la orden.
        result: Dict con resultado de la ejecución.
        balance: Balance actual después del trade (opcional).

    Example:
        >>> log_trade('OPEN', verdict, order, result, 9500.0)
        🎲 OPEN | BTC/USDT BUY | Unidad=1u(100.00USD) | outcome=WIN | exit=TP | bars=5 | pnl_pct=0.0250 | balance=9500.00
    """
    notional_amount = result.get("notional")
    if notional_amount is None:
        size_fraction = float(order.get("size", 0.0))
        try:
            if balance is not None:
                equity_reference = float(balance)
            else:
                equity_reference = float(result.get("balance", 0.0))
        except (TypeError, ValueError):
            equity_reference = 0.0
        notional_amount = equity_reference * size_fraction
    try:
        notional_amount = float(notional_amount)
    except (TypeError, ValueError):
        notional_amount = 0.0
    unit_multiplier = order.get("unit_multiplier")
    try:
        unit_multiplier = float(unit_multiplier)
    except (TypeError, ValueError):
        unit_multiplier = None
    if unit_multiplier is None or unit_multiplier <= 0:
        unit_multiplier = 1.0

    unit_amount = order.get("unit_amount")
    try:
        unit_amount = float(unit_amount)
    except (TypeError, ValueError):
        unit_amount = None
    if unit_amount is None or unit_amount <= 0:
        unit_amount = notional_amount / unit_multiplier if unit_multiplier > 0 else notional_amount

    try:
        unit_display = float(unit_amount)
    except (TypeError, ValueError):
        unit_display = 0.0
    unit_count_display = int(unit_multiplier) if abs(unit_multiplier - round(unit_multiplier)) < 1e-6 else unit_multiplier

    logger.info(
        "🎲 %s | %s %s | Unidad=%su(%.2fUSD) | outcome=%s | exit=%s | bars=%s | pnl_pct=%.4f | balance=%s",
        action,
        order.get("symbol", "?"),
        order.get("side", "?"),
        unit_count_display,
        unit_display,
        result.get("result", "?"),
        result.get("exit_reason", "?"),
        result.get("bars_held", "?"),
        float(result.get("pnl_pct", 0.0)),
        f"{balance:.2f}" if balance is not None else "n/a",
    )