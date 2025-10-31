"""
====================================================
📊 FIXED PLAYER — Sizing de Porcentaje Fijo
====================================================

Player simple que apuesta un porcentaje fijo del equity
cuando Gemini aprueba una oportunidad.

Estrategia:
-----------
- Si hay participantes aprobados con edge → apuesta FIXED_PERCENTAGE
- Si no hay edge → no apuesta (retorna None)
- Ignora la magnitud del edge (a diferencia de Kelly)

Uso recomendado:
----------------
- Testing/baseline para comparar contra Kelly
- Estrategias que prefieren consistencia sobre optimalidad
- Cuando se quiere simplificar el sistema de decisión

Configuración (config.py):
--------------------------
FIXED_POSITION_SIZE: porcentaje fijo a apostar (default: 0.01 = 1%)
  Si no existe, usa MAX_POSITION_SIZE como fallback

Ventajas vs Kelly:
------------------
✅ Más simple de entender
✅ Menos volátil en sizing
✅ No depende de calibración precisa de probabilidades

Desventajas vs Kelly:
---------------------
❌ Subóptimo matemáticamente
❌ No ajusta a la magnitud del edge
❌ Puede sobre-apostar con edge pequeño o sub-apostar con edge grande
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gemini.gemini_core import Verdict

try:
    import config
except ImportError:
    # Fallback for when config is in core/
    import os
    import sys

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        # Last resort: import from core
        from core import config

# Logger
logger = logging.getLogger("FixedPlayer")

# Configuración
FIXED_SIZE = getattr(config, "FIXED_POSITION_SIZE", getattr(config, "MAX_POSITION_SIZE", 0.01))

# Para validación de edge (mismo que Kelly)
R_GROSS = getattr(config, "TAKE_PROFIT", 0.01)
L_GROSS = getattr(config, "STOP_LOSS", 0.01)
FEES = 2 * getattr(config, "COMMISSION_RATE", 0.0)
SLIPPAGE = getattr(config, "SLIPPAGE_DEFAULT", 0.0)
COST = FEES + SLIPPAGE
R_NET = max(0.0, R_GROSS - COST)
L_NET = L_GROSS + COST
P_STAR = L_NET / (L_NET + R_NET) if (L_NET + R_NET) > 0 else 1.0


def calculate_position_size(verdict: Verdict, equity: float, meta: dict = None) -> Optional[float]:
    """
    Retorna un tamaño fijo si hay edge positivo, None si no.

    Args:
        verdict: Veredicto de Gemini con métricas de participantes
        equity: Capital disponible (usado solo para logging)
        meta: Metadatos adicionales (no usado)

    Returns:
        float: FIXED_SIZE si hay edge positivo
        None: Si no hay participantes aprobados con edge

    Lógica:
        1. Verifica que haya participantes aprobados
        2. Verifica que al menos uno tenga p_conservative > P_STAR
        3. Retorna tamaño fijo configurado
    """

    # Validaciones básicas
    if not verdict or not verdict.metrics:
        logger.debug("No verdict or metrics available")
        return None

    if not verdict.side:
        logger.debug("No side determined (likely conflict)")
        return None

    # Filtrar participantes con edge positivo
    approved_with_edge = [m for m in verdict.metrics if m.approved and m.p_conservative > P_STAR]

    if not approved_with_edge:
        logger.debug(
            f"No approved participants with positive edge. "
            f"Total: {len(verdict.metrics)}, "
            f"Approved: {len([m for m in verdict.metrics if m.approved])}"
        )
        return None

    # Retornar tamaño fijo
    logger.info(
        f"Fixed Size | "
        f"size={FIXED_SIZE:.4f} | "
        f"approved_with_edge={len(approved_with_edge)}/{len(verdict.metrics)} | "
        f"best_p={max(m.p_conservative for m in approved_with_edge):.4f}"
    )

    return FIXED_SIZE


def get_info(verdict: Verdict) -> dict:
    """
    Retorna información sobre la decisión para análisis.

    Returns:
        dict con keys: fixed_size, approved_count, has_edge
    """
    if not verdict or not verdict.metrics:
        return {
            "fixed_size": FIXED_SIZE,
            "approved_count": 0,
            "has_edge": False,
        }

    approved_with_edge = [m for m in verdict.metrics if m.approved and m.p_conservative > P_STAR]

    return {
        "fixed_size": FIXED_SIZE,
        "approved_count": len(approved_with_edge),
        "has_edge": len(approved_with_edge) > 0,
        "total_participants": len(verdict.metrics),
    }
