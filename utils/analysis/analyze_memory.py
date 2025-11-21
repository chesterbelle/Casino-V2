#!/usr/bin/env python3
"""
Utilities to inspect Gemini's trained memory and print a concise report.

This consolidates the old `scripts/analyze_memory.py` CLI so it can now be
invoked via `python3 -m utils.cli analyze-memory`.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_MEMORY_PATH = Path("gemini/data/memory_state.json")


def load_memory(path: Path = DEFAULT_MEMORY_PATH) -> Optional[Dict]:
    """
    Load the Gemini memory state JSON if available.

    Returns:
        Parsed memory dictionary or None when the file is missing.
    """
    if not path.exists():
        logger.warning("❌ No se encontró memoria entrenada")
        logger.info(f"   Ruta esperada: {path}")
        logger.info("\n💡 Ejecuta primero:")
        logger.info("   python3 -m utils.cli train-memory")
        return None

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _collect_counts(strategies: Dict[str, Dict], min_support: int) -> Tuple[List[Dict], List[Dict]]:
    approved: List[Dict] = []
    pending: List[Dict] = []

    for name, data in strategies.items():
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        total_trades = wins + losses
        winrate = data.get("winrate")

        if total_trades >= min_support:
            approved.append(
                {
                    "name": name,
                    "wins": wins,
                    "losses": losses,
                    "total": total_trades,
                    "winrate": winrate,
                }
            )
        else:
            pending.append(
                {
                    "name": name,
                    "total": total_trades,
                    "needed": max(0, min_support - total_trades),
                }
            )

    approved.sort(key=lambda item: item.get("winrate") or 0.0, reverse=True)
    pending.sort(key=lambda item: item.get("total") or 0, reverse=True)
    return approved, pending


def analyze_strategies(state: Dict, min_support: int = 500) -> Optional[Dict]:
    """Return aggregate memory statistics ready for reporting."""
    strategies = state.get("strategies", {})

    if not strategies:
        logger.warning("⚠️  Memoria vacía - sin estrategias entrenadas")
        return None

    approved, pending = _collect_counts(strategies, min_support)

    return {
        "total": len(strategies),
        "approved": approved,
        "pending": pending,
        "min_support": min_support,
    }


def _count_by_sensor(approved: Iterable[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for strat in approved:
        name = strat.get("name", "")
        sensor = name.split("|")[-1] if "|" in name else "Unknown"
        counts[sensor] = counts.get(sensor, 0) + 1
    return counts


def print_analysis(analysis: Dict) -> None:
    """Pretty-print the analysis summary."""
    if not analysis:
        return

    logger.info("\n" + "=" * 80)
    logger.info("📊 ANÁLISIS DE MEMORIA ENTRENADA")
    logger.info("=" * 80)

    logger.info(f"\n📈 RESUMEN GENERAL")
    logger.info(f"  Total estrategias: {analysis['total']}")
    logger.info(f"  Aprobadas (>= {analysis['min_support']} trades): {len(analysis['approved'])}")
    logger.info(f"  Pendientes: {len(analysis['pending'])}")

    approved: List[Dict] = analysis["approved"]
    pending: List[Dict] = analysis["pending"]

    if approved:
        logger.info(f"\n✅ TOP ESTRATEGIAS APROBADAS (por winrate):")
        logger.info(f"{'#':<3} {'Estrategia':<60} {'Trades':<8} {'Winrate':<10}")
        logger.info("-" * 85)

        for idx, strat in enumerate(approved[:20], 1):
            name = strat["name"][:60]
            total = strat["total"]
            winrate = strat.get("winrate")
            winrate_str = f"{winrate:.2%}" if winrate is not None else "N/A"

            if winrate and winrate > 0.55:
                emoji = "🟢"
            elif winrate and winrate > 0.52:
                emoji = "🟡"
            else:
                emoji = "🔴"

            logger.info(f"{idx:<3} {emoji} {name:<58} {total:<8} {winrate_str:<10}")

        if len(approved) > 20:
            logger.info(f"\n  ... y {len(approved) - 20} más")

    if pending:
        logger.info(f"\n⏳ ESTRATEGIAS PENDIENTES (más cercanas a aprobar):")
        logger.info(f"{'#':<3} {'Estrategia':<60} {'Trades':<8} {'Faltan':<8}")
        logger.info("-" * 85)
        for idx, strat in enumerate(pending[:10], 1):
            name = strat["name"][:60]
            total = strat["total"]
            needed = strat["needed"]
            logger.info(f"{idx:<3} {name:<60} {total:<8} {needed:<8}")

        if len(pending) > 10:
            logger.info(f"\n  ... y {len(pending) - 10} más")

    logger.info(f"\n📊 DISTRIBUCIÓN POR SENSOR:")
    counts = _count_by_sensor(approved)
    if counts:
        for sensor, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
            bar = "█" * min(count, 50)
            logger.info(f"  {sensor:<25} {count:>3} {bar}")

    logger.info(f"\n💡 RECOMENDACIONES:")
    if len(approved) < 10:
        logger.warning("  ⚠️  Pocas estrategias aprobadas - necesitas más datos de entrenamiento")
        logger.info("     → Ejecuta: python3 -m utils.cli download-training-data")
        logger.info("     → Luego: python3 -m utils.cli train-memory")
    else:
        logger.info("  ✅ Suficientes estrategias aprobadas para operar")
        logger.info("     → Próximo paso: python3 -m utils.cli validate-strategies")

    winrates = [s["winrate"] for s in approved if s.get("winrate") is not None]
    if winrates:
        avg_winrate = sum(winrates) / len(winrates)
        if avg_winrate > 0.55:
            logger.info(f"  🟢 Winrate promedio alto ({avg_winrate:.2%}) - sistema prometedor")
        elif avg_winrate > 0.52:
            logger.info(f"  🟡 Winrate promedio moderado ({avg_winrate:.2%}) - viable con gestión de riesgo")
        else:
            logger.info(f"  🔴 Winrate promedio bajo ({avg_winrate:.2%}) - revisar configuración")

    logger.info("\n" + "=" * 80)


def main(min_support: int = 500, memory_path: Path = DEFAULT_MEMORY_PATH) -> int:
    """CLI entry point."""
    state = load_memory(memory_path)
    if not state:
        return 1

        logger.info(f"✅ Memoria cargada")
        logger.info(f"   Última actualización: {state.get('last_update', 'Unknown')}")
        logger.info(f"   Ventana de memoria: {state.get('memory_window', 'Unknown')}")

    analysis = analyze_strategies(state, min_support=min_support)
    if not analysis:
        return 1
    print_analysis(analysis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
