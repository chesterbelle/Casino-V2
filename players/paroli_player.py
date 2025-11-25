"""
====================================================
🎯 PAROLI PLAYER — Progresión positiva 1-4-8
====================================================

Estrategia:
-----------
- Calcula una unidad base al arrancar una nueva secuencia: `unit = equity / BASE_DIVISOR`.
- Mantiene esa unidad fija durante toda la progresión Paroli (1x, 4x, 8x).
- Tras cada victoria avanza al siguiente escalón; al perder o completar el ciclo reinicia.
- Respeta `config.MAX_POSITION_SIZE` para no exceder el riesgo máximo.
- Usa leverage 10x para amplificar posiciones en futures.

Integración:
------------
- `init_state()`   → estado inicial (unit=None, step=0).
- `prepare_state()`→ asegura que exista unidad al empezar ciclo y entrega metadata para el player.
- `calculate_position_size()` → decide fracción de equity a apostar según el escalón actual.
- `handle_trade_outcome()` → actualiza el estado tras conocer el resultado del trade.
- `LEVERAGE` → apalancamiento usado en órdenes (10x por defecto, máx 50x según config).

⚠️ Particularidad: este player no comprueba si Gemini encontró edge.
Mientras exista `verdict.side`, apostará aplicando la progresión 1-4-8,
aunque `verdict.reason` sea "sin_aprobadas" o "kelly_no_positivo".
Si necesitas respetar el edge, añade un filtro externo antes de usarlo.

Esta interfaz permite mantener la modularidad del motor: el loop principal controla
la persistencia del estado y solo pasa metadata al player en cada iteración.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple

from config import trading

if TYPE_CHECKING:  # pragma: no cover - solo para hints
    from gemini.gemini_core import Verdict

# Parámetros Paroli
BASE_DIVISOR = 100  # Unidad inicial = equity / 100 (1% de equity)
PROGRESSION = (1, 4, 8)  # Multiplicadores Paroli
MAX_POSITION_SIZE = float(getattr(trading, "MAX_POSITION_SIZE", 0.02))
LEVERAGE = 10  # Apalancamiento para futures (máx permitido: trading.MAX_LEVERAGE)

# Validar leverage contra config
MAX_LEVERAGE = int(getattr(trading, "MAX_LEVERAGE", 50))
if LEVERAGE > MAX_LEVERAGE:
    raise ValueError(f"Paroli player: LEVERAGE={LEVERAGE} excede MAX_LEVERAGE={MAX_LEVERAGE} del config")


def init_state() -> Dict[str, Optional[float]]:
    """Estado inicial para el ciclo Paroli."""
    return {"unit": None, "step": 0}


def prepare_state(state: Dict, equity: Optional[float]) -> Tuple[Dict, Dict]:
    """
    Garantiza que exista unidad cuando comience un nuevo ciclo y devuelve metadata.

    Args:
        state: Estado actual (unit, step).
        equity: Equity disponible en la mesa.

    Returns:
        (new_state, meta) donde meta es pasada al player en calculate_position_size.
    """
    new_state = dict(state)
    if equity is None or equity <= 0:
        # No se puede calcular unidad sin equity válido
        new_state = {"unit": None, "step": 0}
    elif new_state.get("unit") is None:
        new_state = {
            "unit": max(equity / BASE_DIVISOR, 0.0),
            "step": 0,
        }

    step = int(new_state.get("step", 0))
    if step < 0 or step >= len(PROGRESSION):
        new_state["step"] = 0

    meta = {
        "paroli_state": dict(new_state),
        "paroli_progression": PROGRESSION,
    }
    unit_value = new_state.get("unit")
    if unit_value is not None:
        meta["paroli_unit_amount"] = float(unit_value)
    return new_state, meta


def calculate_position_size(
    verdict: "Verdict",
    equity: Optional[float],
    meta: Optional[Dict] = None,
) -> Optional[float]:
    """
    Retorna la fracción de equity a apostar según el escalón Paroli.
    """
    if not verdict or not verdict.side:
        return None
    if equity is None or equity <= 0:
        return None

    meta = meta or {}
    state = meta.get("paroli_state") or {}
    progression = meta.get("paroli_progression", PROGRESSION)
    table_meta = meta.get("table", {}) if isinstance(meta.get("table"), dict) else {}

    unit_amount = state.get("unit")
    step = int(state.get("step", 0))

    # Paroli apuesta "a lo loco": si no hay unit, calcularla ahora
    if unit_amount is None or unit_amount <= 0:
        unit_amount = equity / BASE_DIVISOR
        state["unit"] = unit_amount

    if step < 0 or step >= len(progression):
        step = 0

    multiplier = progression[step]
    position_amount = unit_amount * multiplier

    max_fraction_limit = float(table_meta.get("max_position_fraction", MAX_POSITION_SIZE) or MAX_POSITION_SIZE)
    max_fraction_limit = min(max_fraction_limit, MAX_POSITION_SIZE)

    if equity and equity > 0:
        max_multiplier = max(progression) if progression else 1
        if max_multiplier > 0:
            max_unit_allowed = (equity * max_fraction_limit) / max_multiplier
            if max_unit_allowed > 0 and unit_amount > max_unit_allowed:
                unit_amount = max_unit_allowed
                state["unit"] = unit_amount
                position_amount = unit_amount * multiplier

    size_fraction = position_amount / equity if equity and equity > 0 else 0.0

    price = table_meta.get("price")
    min_qty = table_meta.get("min_qty")
    min_fraction = None
    if equity and equity > 0 and price and min_qty:
        try:
            min_fraction = (float(min_qty) * float(price)) / float(equity)
        except (TypeError, ValueError):
            min_fraction = None

    if min_fraction:
        if min_fraction > max_fraction_limit:
            return None
        if size_fraction < min_fraction:
            size_fraction = min_fraction

    size_fraction = min(size_fraction, max_fraction_limit)

    if equity and equity > 0 and multiplier > 0:
        executed_unit = size_fraction * equity / multiplier
        if executed_unit > 0:
            state["unit"] = executed_unit
            meta["paroli_unit_amount"] = float(executed_unit)

    meta["paroli_multiplier"] = float(multiplier)
    if "paroli_unit_amount" not in meta and unit_amount is not None:
        meta["paroli_unit_amount"] = float(unit_amount)

    return size_fraction if size_fraction > 0 else None


def handle_trade_outcome(state: Dict, action: str, result: Dict) -> Dict:
    """
    Actualiza el estado según el resultado del trade.

    - GHOST → no altera la secuencia.
    - BET + WIN → avanza escalón; si completó la progresión, reinicia.
    - BET + LOSS → reinicia inmediatamente.
    """
    if action != "BET":
        return {"unit": None, "step": 0}

    new_state = dict(state)

    outcome = (result.get("result") or "").upper()
    if outcome == "WIN":
        next_step = int(new_state.get("step", 0)) + 1
        if next_step >= len(PROGRESSION):
            return {"unit": None, "step": 0}
        new_state["step"] = next_step
        return new_state

    # Cualquier resultado no ganador reinicia la secuencia
    return {"unit": None, "step": 0}
