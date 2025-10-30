"""
Session helpers and utilities for Casino V2 trading system.
"""

import logging
from typing import Dict, Optional

import config

logger = logging.getLogger("SessionHelpers")


def ask_initial_balance() -> float:
    """Pide balance inicial por consola; fallback a config.STARTING_BALANCE."""
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


def set_table_balance(table, amount: float) -> None:
    """Fuerza el balance inicial de la mesa."""
    bm = getattr(table, "balance_manager", None)
    if not bm:
        return
    try:
        bm.balance = amount
        bm.equity = amount
    except Exception:
        if hasattr(bm, "set_balance"):
            bm.set_balance(amount)


def get_table_state(table) -> Dict:
    bm = getattr(table, "balance_manager", None)
    if bm and hasattr(bm, "get_state"):
        try:
            return bm.get_state()
        except Exception:
            return {}
    return {}


def log_trade(action: str, verdict, order: Dict, result: Dict, balance: Optional[float]) -> None:
    """Log estandarizado de trades"""
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