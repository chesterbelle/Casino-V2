"""
====================================================
🎲 KELLY PLAYER — Sizing basado en Kelly Fraccional
====================================================

Implementa el Criterio de Kelly para determinar el tamaño óptimo
de la posición basándose en la ventaja estadística detectada por Gemini.

Estrategia:
-----------
1. Recibe Verdict con métricas probabilísticas de participantes aprobados
2. Selecciona el p_conservative más bajo (estrategia conservadora)
3. Calcula Kelly usando: f = p - q/b
4. Aplica fracción de Kelly (ej: 0.2 = 20% de Kelly completo)
5. Limita por MAX_POSITION_SIZE

Configuración (config.py):
--------------------------
KELLY_FRACTION: fracción de Kelly a usar (default: 0.2 = muy conservador)
MAX_POSITION_SIZE: límite máximo de posición (default: 0.02 = 2%)
TAKE_PROFIT, STOP_LOSS, COMMISSION_RATE: para calcular R_NET, L_NET

Referencia:
-----------
Kelly Criterion: f* = (bp - q) / b
donde:
  b = odds (R_NET / L_NET)
  p = probabilidad de ganar (p_conservative)
  q = 1 - p
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from gemini.gemini_core import Verdict

import config

# Logger
logger = logging.getLogger("KellyPlayer")

# Parámetros de cálculo (mismos que Gemini usa para P_STAR)
R_GROSS = getattr(config, "TAKE_PROFIT", 0.01)
L_GROSS = getattr(config, "STOP_LOSS", 0.01)
FEES = 2 * getattr(config, "COMMISSION_RATE", 0.0)
SLIPPAGE = getattr(config, "SLIPPAGE_DEFAULT", 0.0)
COST = FEES + SLIPPAGE

R_NET = max(0.0, R_GROSS - COST)
L_NET = L_GROSS + COST

# Break-even probability y odds
if R_NET <= 0 or (R_NET + L_NET) <= 0:
    P_STAR = 1.0
    B = 0.0
else:
    P_STAR = L_NET / (L_NET + R_NET)
    B = R_NET / L_NET

# Configuración de Kelly
KELLY_FRACTION = getattr(config, "KELLY_FRACTION", 0.2)
MAX_POSITION_SIZE = getattr(config, "MAX_POSITION_SIZE", 0.02)


def calculate_position_size(verdict: Verdict, equity: float, meta: dict = None) -> Optional[float]:
    """
    Calcula el tamaño de posición usando Kelly Criterion.
    
    Args:
        verdict: Veredicto de Gemini con métricas de participantes
        equity: Capital disponible (usado solo para logging)
        meta: Metadatos adicionales (no usado actualmente)
    
    Returns:
        float: Fracción del equity a arriesgar [0, 1]
        None: Si no se debe apostar
    
    Estrategia conservadora:
        - Usa la p_conservative MÁS BAJA entre participantes aprobados
        - Aplica KELLY_FRACTION (típicamente 0.2 = 20% del Kelly óptimo)
        - Limita por MAX_POSITION_SIZE
    """
    
    # Validaciones básicas
    if not verdict or not verdict.metrics:
        logger.debug("No verdict or metrics available")
        return None
    
    if not verdict.side:
        logger.debug("No side determined (likely conflict)")
        return None
    
    # Filtrar solo participantes aprobados con edge positivo
    approved_metrics = [
        m for m in verdict.metrics 
        if m.approved and m.p_conservative > P_STAR
    ]
    
    if not approved_metrics:
        logger.debug(
            f"No approved participants with edge. "
            f"Total metrics: {len(verdict.metrics)}, "
            f"Approved: {len([m for m in verdict.metrics if m.approved])}"
        )
        return None
    
    # Verificar que B > 0 (necesario para Kelly)
    if B <= 0:
        logger.warning(
            f"B={B:.4f} <= 0. Kelly no aplicable. "
            f"Revisa TAKE_PROFIT y STOP_LOSS en config."
        )
        return None
    
    # Estrategia conservadora: usar el p_conservative MÁS BAJO
    # (el más pesimista de los aprobados)
    p_conservative = min(m.p_conservative for m in approved_metrics)
    q = 1.0 - p_conservative
    
    # Calcular Kelly óptimo: f = p - q/b
    f_kelly = p_conservative - (q / B)
    
    # Aplicar fracción de Kelly (conservador)
    f_fractional = max(0.0, f_kelly) * KELLY_FRACTION
    
    # Limitar por tamaño máximo configurado
    size_fraction = min(f_fractional, MAX_POSITION_SIZE)
    
    # Logging detallado
    logger.info(
        f"Kelly Calculation | "
        f"p_cons={p_conservative:.4f} (from {len(approved_metrics)} approved) | "
        f"p*={P_STAR:.4f} | "
        f"B={B:.4f} | "
        f"f_kelly={f_kelly:.4f} | "
        f"f_frac={f_fractional:.4f} | "
        f"final={size_fraction:.4f}"
    )
    
    # Solo retornar si el size es significativo
    if size_fraction <= 0:
        logger.debug("Calculated size <= 0, no bet")
        return None
    
    return size_fraction


def get_kelly_info(verdict: Verdict) -> dict:
    """
    Retorna información detallada del cálculo de Kelly para análisis.
    
    Útil para debugging, logging avanzado o dashboards.
    
    Returns:
        dict con keys: p_conservative, p_star, b, f_kelly, f_fractional, 
                      approved_count, total_participants
    """
    if not verdict or not verdict.metrics:
        return {
            "p_conservative": None,
            "p_star": P_STAR,
            "b": B,
            "f_kelly": 0.0,
            "f_fractional": 0.0,
            "approved_count": 0,
            "total_participants": 0,
        }
    
    approved = [m for m in verdict.metrics if m.approved and m.p_conservative > P_STAR]
    
    if not approved:
        p_cons = None
        f_kelly = 0.0
    else:
        p_cons = min(m.p_conservative for m in approved)
        q = 1.0 - p_cons
        f_kelly = p_cons - (q / B) if B > 0 else 0.0
    
    f_frac = max(0.0, f_kelly) * KELLY_FRACTION if f_kelly else 0.0
    
    return {
        "p_conservative": p_cons,
        "p_star": P_STAR,
        "b": B,
        "f_kelly": f_kelly,
        "f_fractional": f_frac,
        "approved_count": len(approved),
        "total_participants": len(verdict.metrics),
    }
