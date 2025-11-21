#!/usr/bin/env python3
"""
Consolidated helper to inspect configured sensors.

Usage (CLI):
    python3 -m utils.cli check-sensors
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)


def _ensure_project_root() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_project_root()

import config
from sensors.sensor_manager import SENSOR_REGISTRY

DEFAULT_MEAN_REVERSION = [
    "RSIReversion",
    "BollingerTouch",
    "KeltnerReversion",
    "StochasticReversion",
    "BollingerSqueeze",
    "WilliamsRReversion",
    "CCIReversion",
    "ZScoreReversion",
]

DEFAULT_MOMENTUM_TREND = [
    "EMACrossover",
    "MACDCrossover",
    "Supertrend",
    "ADXFilter",
    "ParabolicSAR",
]

DEFAULT_VOLUME = [
    "OBVBreakout",
    "VWAPDeviation",
    "MFIReversion",
    "AccumulationDistribution",
]


def _resolve_active_sensors(cfg: Dict[str, bool] | None) -> Tuple[List[str], int]:
    if not cfg:
        active_list = list(SENSOR_REGISTRY.keys())
        return active_list, len(active_list)
    active_list = [name for name, enabled in cfg.items() if enabled]
    return active_list, len(active_list)


def _print_category(title: str, sensors: Iterable[str], active_lookup: set[str]) -> Tuple[int, int]:
    logger.info(f"\n{title}:")
    total = 0
    active_count = 0
    for sensor in sensors:
        total += 1
        if sensor not in SENSOR_REGISTRY:
            logger.warning(f"  ⚠️  {sensor} (NO REGISTRADO)")
            continue
        status = "✅" if sensor in active_lookup else "❌"
        if status == "✅":
            active_count += 1
        logger.info(f"  {status} {sensor}")
    return active_count, total


def run_sensor_check() -> bool:
    """Render the full sensor report and return True when all are active."""
    logger.info("\n" + "=" * 70)
    logger.info("🔍 VERIFICACIÓN DE SENSORES")
    logger.info("=" * 70)

    total_available = len(SENSOR_REGISTRY)
    logger.info(f"\n📊 Sensores disponibles en el sistema: {total_available}")

    active_cfg = getattr(config, "ACTIVE_SENSORS", {}) or None
    active_list, active_count = _resolve_active_sensors(active_cfg)

    if active_cfg is None:
        logger.warning("\n⚠️  ACTIVE_SENSORS no está configurado en config.py")
        logger.info("   Por defecto, TODOS los sensores están activos.")

    logger.info(f"✅ Sensores activos: {active_count}")

    active_lookup = set(active_list)

    mr_active, mr_total = _print_category("📉 Mean Reversion", DEFAULT_MEAN_REVERSION, active_lookup)
    mt_active, mt_total = _print_category("📈 Momentum/Trend", DEFAULT_MOMENTUM_TREND, active_lookup)
    vol_active, vol_total = _print_category("📊 Volume", DEFAULT_VOLUME, active_lookup)

    logger.info("\n" + "=" * 70)
    logger.info("📊 RESUMEN:")
    logger.info("-" * 70)
    logger.info(f"  Mean Reversion:   {mr_active}/{mr_total}")
    logger.info(f"  Momentum/Trend:   {mt_active}/{mt_total}")
    logger.info(f"  Volume:           {vol_active}/{vol_total}")
    logger.info(f"  {'─' * 40}")
    logger.info(f"  TOTAL ACTIVOS:    {active_count}/{total_available}")
    print("=" * 70)

    if active_count == total_available:
        logger.info("\n✅ ¡PERFECTO! Todos los sensores están activos.")
    elif active_count >= 15:
        logger.info(f"\n🟢 BUENO: {active_count} sensores activos (suficiente cobertura)")
    elif active_count >= 10:
        logger.info(f"\n🟡 REGULAR: {active_count} sensores activos (considera activar más)")
    else:
        logger.warning(f"\n🔴 BAJO: Solo {active_count} sensores activos (activa más para mejor cobertura)")

    if active_count < total_available:
        inactive = [sensor for sensor in SENSOR_REGISTRY.keys() if sensor not in active_lookup]
        if inactive:
            logger.warning("\n⚠️  Sensores DESACTIVADOS:")
            for sensor in inactive:
                logger.warning(f"  ❌ {sensor}")

    logger.info("\n💡 Para activar todos los sensores:")
    logger.info("   Edita config.py y asegúrate que ACTIVE_SENSORS tiene todos en True")
    logger.info("   O simplemente NO definas ACTIVE_SENSORS (todos activos por defecto)")
    logger.info("\n" + "=" * 70 + "\n")

    return active_count == total_available


def main() -> int:
    """CLI entry point."""
    success = run_sensor_check()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
