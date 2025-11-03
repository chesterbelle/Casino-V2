"""Placeholder live session module for Casino V2 v1.9.

El modo live (dinero real) será implementado en la versión v2.4. Esta
implementación temporal solamente expone `run_live_session`, la cual arroja
un NotImplementedError con instrucciones claras.
"""

from __future__ import annotations

import logging
from typing import Optional

LOGGER = logging.getLogger("LiveSessionPlaceholder")


def _live_not_available_message() -> str:
    return (
        "\n" + "=" * 70 + "\n"
        "🚧 LIVE TRADING NO DISPONIBLE EN v1.9 🚧\n" + "=" * 70 + "\n\n"
        "Casino V2 aún no soporta trading en vivo con dinero real.\n"
        "El modo 'live' será implementado en la versión v2.4 (tentativa).\n\n"
        "Para validar el sistema usa el modo 'testing' con Kraken Demo:\n"
        "  - core/config.py → MODE = 'testing'\n"
        "  - EXCHANGE = 'KRAKEN'\n\n"
        "Si realmente necesitas live trading antes de v2.4, revisa el ROADMAP\n"
        "y coordina con el equipo para priorizar la implementación.\n"
    )


def run_live_session(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    max_candles: Optional[int] = None,
    player_module=None,
    player_name: str = "paroli",
):
    LOGGER.error("Se intentó iniciar modo live, pero no está disponible en v1.9.")
    raise NotImplementedError(_live_not_available_message())
