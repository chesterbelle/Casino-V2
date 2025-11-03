#!/usr/bin/env python3
"""
Consolidated helper to inspect configured sensors.

Usage (CLI):
    python3 -m utils.cli check-sensors
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


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
    print(f"\n{title}:")
    total = 0
    active_count = 0
    for sensor in sensors:
        total += 1
        if sensor not in SENSOR_REGISTRY:
            print(f"  ⚠️  {sensor} (NO REGISTRADO)")
            continue
        status = "✅" if sensor in active_lookup else "❌"
        if status == "✅":
            active_count += 1
        print(f"  {status} {sensor}")
    return active_count, total


def run_sensor_check() -> bool:
    """Render the full sensor report and return True when all are active."""
    print("\n" + "=" * 70)
    print("🔍 VERIFICACIÓN DE SENSORES")
    print("=" * 70)

    total_available = len(SENSOR_REGISTRY)
    print(f"\n📊 Sensores disponibles en el sistema: {total_available}")

    active_cfg = getattr(config, "ACTIVE_SENSORS", {}) or None
    active_list, active_count = _resolve_active_sensors(active_cfg)

    if active_cfg is None:
        print("\n⚠️  ACTIVE_SENSORS no está configurado en config.py")
        print("   Por defecto, TODOS los sensores están activos.")

    print(f"✅ Sensores activos: {active_count}")

    active_lookup = set(active_list)

    mr_active, mr_total = _print_category("📉 Mean Reversion", DEFAULT_MEAN_REVERSION, active_lookup)
    mt_active, mt_total = _print_category("📈 Momentum/Trend", DEFAULT_MOMENTUM_TREND, active_lookup)
    vol_active, vol_total = _print_category("📊 Volume", DEFAULT_VOLUME, active_lookup)

    print("\n" + "=" * 70)
    print("📊 RESUMEN:")
    print("-" * 70)
    print(f"  Mean Reversion:   {mr_active}/{mr_total}")
    print(f"  Momentum/Trend:   {mt_active}/{mt_total}")
    print(f"  Volume:           {vol_active}/{vol_total}")
    print(f"  {'─' * 40}")
    print(f"  TOTAL ACTIVOS:    {active_count}/{total_available}")
    print("=" * 70)

    if active_count == total_available:
        print("\n✅ ¡PERFECTO! Todos los sensores están activos.")
    elif active_count >= 15:
        print(f"\n🟢 BUENO: {active_count} sensores activos (suficiente cobertura)")
    elif active_count >= 10:
        print(f"\n🟡 REGULAR: {active_count} sensores activos (considera activar más)")
    else:
        print(f"\n🔴 BAJO: Solo {active_count} sensores activos (activa más para mejor cobertura)")

    if active_count < total_available:
        inactive = [sensor for sensor in SENSOR_REGISTRY.keys() if sensor not in active_lookup]
        if inactive:
            print("\n⚠️  Sensores DESACTIVADOS:")
            for sensor in inactive:
                print(f"  ❌ {sensor}")

    print("\n💡 Para activar todos los sensores:")
    print("   Edita config.py y asegúrate que ACTIVE_SENSORS tiene todos en True")
    print("   O simplemente NO definas ACTIVE_SENSORS (todos activos por defecto)")
    print("\n" + "=" * 70 + "\n")

    return active_count == total_available


def main() -> int:
    """CLI entry point."""
    success = run_sensor_check()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
