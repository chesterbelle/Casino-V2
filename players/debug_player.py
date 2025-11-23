"""
====================================================
🧪 DEBUG PLAYER — Apuesta cada vela (ignora Verdict)
====================================================

Este player fuerza una apuesta en cada iteración de vela sin revisar
el `Verdict` de Gemini ni otras señales. Está destinado para pruebas
rápidas y generación de órdenes en demo/testnet.

Interfaz soportada:
- `init_state()` -> dict
- `prepare_state(state, equity)` -> (new_state, meta)
- `calculate_position_size(verdict, equity, meta)` -> fraction (0..1) or None
- `handle_trade_outcome(state, action, result)` -> new_state

Notas de seguridad:
- Usa `config.trading.MAX_POSITION_SIZE` como límite por defecto.
- Este player puede generar muchas órdenes; úsalo en entornos de demo/testnet.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from config import trading

# Límites por defecto
MAX_POSITION_SIZE = float(getattr(trading, "MAX_POSITION_SIZE", 0.02))
DEFAULT_FRACTION = min(0.01, MAX_POSITION_SIZE)  # apuesta 1% del equity por defecto, o menos si el config lo limita


def init_state() -> Dict:
    """Estado inicial (no necesita nada complejo)."""
    return {"forced_count": 0}


# Flag para que el sistema trate este player como agresivo (puede forzar apuestas)
FORCE_BET = True


def prepare_state(state: Dict, equity: Optional[float]) -> Tuple[Dict, Dict]:
    """
    Garantiza que el estado exista y devuelve metadata sencilla.
    Siempre devuelve meta con `force_bet=True` para indicar intención.
    """
    new_state = dict(state or {})
    if "forced_count" not in new_state:
        new_state["forced_count"] = 0
    # Only request a forced bet on the FIRST candle (when forced_count == 0)
    force_first = int(new_state.get("forced_count", 0)) == 0
    meta = {
        "force_bet": force_first,
        "force_bet_first": force_first,
        "max_fraction": MAX_POSITION_SIZE,
    }
    if equity is not None:
        meta["equity"] = float(equity)
    return new_state, meta


def calculate_position_size(verdict, equity: Optional[float], meta: Optional[Dict] = None) -> Optional[float]:
    """
    Retorna la fracción de equity a apostar en esta vela.
    Ignora `verdict` completamente y apuesta siempre `DEFAULT_FRACTION`.
    Si `equity` es None o 0 devuelve None.
    """
    if equity is None or equity <= 0:
        return None
    meta = meta or {}
    max_fraction = float(meta.get("max_fraction", MAX_POSITION_SIZE))
    fraction = min(DEFAULT_FRACTION, max_fraction)
    # sanity: no apostar cantidades ridículas
    if fraction <= 0:
        return None
    return float(fraction)


def handle_trade_outcome(state: Dict, action: str, result: Dict) -> Dict:
    """
    Actualiza un contador simple de apuestas forzadas; para DEBUG no se
    altera la lógica de progresión.
    """
    new_state = dict(state or {})
    if "forced_count" not in new_state:
        new_state["forced_count"] = 0
    if action == "BET":
        new_state["forced_count"] = int(new_state.get("forced_count", 0)) + 1
    return new_state
