"""
====================================================
🎮 PLAYERS — Gestores de Tamaño de Posición
====================================================

Los Players reciben un Verdict de Gemini (validación probabilística)
y deciden cuánto apostar según su estrategia de sizing.

Esto desacopla la validación de oportunidades (Gemini)
del dimensionamiento de posiciones (Players).

Módulos disponibles:
--------------------
- kelly_player: Criterio de Kelly fraccional (conservador)
- fixed_player: Porcentaje fijo del equity
- adaptive_player: Ajusta según volatilidad/régimen

Uso típico:
-----------
    from players import kelly_player

    verdict = gemini.evaluate_signals(signals, equity)
    size_fraction = kelly_player.calculate_position_size(verdict, equity)

    if size_fraction and size_fraction > 0:
        order = gemini.make_order_from_verdict(verdict, size_fraction)
"""

from .fixed_player import calculate_position_size as fixed_position_size
from .kelly_player import calculate_position_size as kelly_position_size

__all__ = [
    "kelly_position_size",
    "fixed_position_size",
]
