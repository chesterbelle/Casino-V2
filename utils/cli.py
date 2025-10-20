#!/usr/bin/env python3
"""
Unified CLI entry point for operational utilities.

Examples:
    python3 -m utils.cli download-training-data
    python3 -m utils.cli train-memory
    python3 -m utils.cli analyze-memory
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from . import analyze_memory, check_sensors

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def _stream_subprocess(
    command: List[str],
    *,
    cwd: Path = ROOT,
    env: Optional[dict] = None,
    log_path: Optional[Path] = None,
) -> int:
    """
    Execute a subprocess while streaming its output to stdout and an optional log.

    Returns:
        Process return code.
    """
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    log_handle = log_path.open("w", encoding="utf-8") if log_path else None
    try:
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            if log_handle:
                log_handle.write(line)
        process.wait()
    finally:
        if log_handle:
            log_handle.close()
    return process.returncode


def run_download_training_data(
    symbols: Iterable[str],
    interval: str,
    days: int,
    tag: str,
) -> bool:
    symbols = list(symbols) or ["BTCUSDT", "ETHUSDT", "LTCUSDT", "BNBUSDT", "SOLUSDT"]
    output_dir = ROOT / "tables" / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("==================================")
    print("📥 DESCARGA DE DATOS PARA ENTRENAMIENTO")
    print("==================================\n")
    print("📋 Configuración:")
    print(f"  Símbolos: {' '.join(symbols)}")
    print(f"  Intervalo: {interval}")
    print(f"  Días: {days}")
    print(f"  Tag: {tag}")
    print("")

    script_path = ROOT / "utils" / "download_kline_dataset.py"
    if not script_path.exists():
        print("❌ Error: utils/download_kline_dataset.py no encontrado")
        print("   Asegúrate de correr desde la raíz del proyecto.")
        return False

    total = len(symbols)
    failed = 0

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{total}] Descargando {symbol}...")
        command = [
            PYTHON,
            str(script_path),
            "--symbol",
            symbol,
            "--interval",
            interval,
            "--days",
            str(days),
            "--tag",
            tag,
        ]
        return_code = _stream_subprocess(command)
        if return_code == 0:
            print(f"  ✅ {symbol} descargado exitosamente\n")
        else:
            print(f"  ❌ Error descargando {symbol}\n")
            failed += 1

    print("==================================")
    print("📊 RESUMEN DE DESCARGAS")
    print("==================================")
    print(f"  Total símbolos: {total}")
    print(f"  Exitosos: {total - failed}")
    print(f"  Fallidos: {failed}\n")

    if failed == 0:
        print("✅ ¡Todas las descargas completadas!\n")
        generated = sorted(output_dir.glob(f"*_{interval}_{tag}.csv"))
        if generated:
            print("📁 Archivos generados:")
            for path in generated:
                print(f"   - {path.relative_to(ROOT)}")
        else:
            print(f"📁 No se encontraron archivos con tag '{tag}'.")
        print("\n🎯 Próximo paso:")
        print("   python3 -m utils.cli train-memory")
    else:
        print("⚠️  Algunas descargas fallaron, revisa los mensajes anteriores.")

    print("==================================")
    return failed == 0


TRAINING_CONFIG_TEMPLATE = """\
# Configuración temporal para ENTRENAMIENTO DE MEMORIA
# Generado automáticamente por utils.cli

from config import *  # noqa: F401,F403

MODE = "backtest"
FORCE_GHOST_ALL = True

ACTIVE_SENSORS = {
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "StochasticReversion": True,
    "BollingerSqueeze": True,
    "WilliamsRReversion": True,
    "CCIReversion": True,
    "ZScoreReversion": True,
    "EMACrossover": True,
    "MACDCrossover": True,
    "Supertrend": True,
    "ADXFilter": True,
    "ParabolicSAR": True,
    "OBVBreakout": True,
    "VWAPDeviation": True,
    "MFIReversion": True,
    "AccumulationDistribution": True,
}

MIN_SUPPORT = 500
MEMORY_WINDOW = 500
AUTOSAVE_INTERVAL = 50
BAYES_CREDIBILITY_THRESHOLD = 0.7

print("=" * 60)
print("⚙️  CONFIGURACIÓN: MODO ENTRENAMIENTO (GHOST)")
print("=" * 60)
print(f"  FORCE_GHOST_ALL: {FORCE_GHOST_ALL}")
print(f"  MIN_SUPPORT: {MIN_SUPPORT}")
print(f"  SENSORES ACTIVOS: {len(ACTIVE_SENSORS)}")
print("=" * 60)
"""


def run_train_memory(pattern: str) -> bool:
    data_dir = ROOT / "tables" / "data" / "raw"
    datasets = sorted(data_dir.glob(pattern))
    if not datasets:
        print(f"❌ No se encontraron datasets con patrón: {pattern}")
        print(f"   Directorio: {data_dir.relative_to(ROOT)}")
        print("\n💡 Ejecuta primero:\n   python3 -m utils.cli download-training-data")
        return False

    print("==================================")
    print("🧠 ENTRENAMIENTO DE MEMORIA (GHOST MODE)")
    print("==================================\n")

    print(f"📊 Datasets encontrados: {len(datasets)}")
    for ds in datasets:
        try:
            label = ds.relative_to(ROOT)
        except ValueError:
            label = ds
        print(f"  - {label}")
    print("")

    config_training_path = ROOT / "config_training.py"
    config_training_path.write_text(TRAINING_CONFIG_TEMPLATE, encoding="utf-8")
    print("⚙️  Configuración temporal creada en config_training.py\n")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(ROOT) if not python_path else f"{str(ROOT)}{os.pathsep}{python_path}"
    )

    total = len(datasets)
    failed = 0

    try:
        for idx, dataset in enumerate(datasets, 1):
            try:
                dataset_str = dataset.relative_to(ROOT).as_posix()
            except ValueError:
                dataset_str = str(dataset)

            log_path = logs_dir / f"training_{dataset.stem}.log"

            print(f"[{idx}/{total}] Entrenando con: {dataset_str}")
            command = [
                PYTHON,
                "-c",
                textwrap.dedent(
                    f"""
import sys
sys.path.insert(0, '.')
import config_training as config
config.DATASET_PATH = {dataset_str!r}
import main  # noqa: F401
"""
                ),
            ]
            return_code = _stream_subprocess(command, env=env, log_path=log_path)
            if return_code == 0:
                print("  ✅ Entrenamiento completado\n")
            else:
                print("  ❌ Error en entrenamiento\n")
                failed += 1
    finally:
        if config_training_path.exists():
            config_training_path.unlink()

    print("==================================")
    print("📊 RESUMEN DE ENTRENAMIENTO")
    print("==================================")
    print(f"  Datasets procesados: {total}")
    print(f"  Exitosos: {total - failed}")
    print(f"  Fallidos: {failed}\n")

    if failed == 0:
        print("✅ ¡Entrenamiento completado!\n")
        print("📁 Memoria guardada en:")
        print("   gemini/data/memory_log.csv")
        print("   gemini/data/memory_state.json\n")
        print("📊 Revisar estadísticas:")
        print("   python3 -m utils.cli analyze-memory\n")
        print("🎯 Próximo paso:")
        print("   python3 -m utils.cli validate-strategies")
    else:
        print("⚠️  Algunos entrenamientos fallaron")
        print("   Revisa los logs en: logs/")
    print("==================================")
    return failed == 0


def run_validate_strategies(pattern: str, limit: int, starting_balance: float) -> bool:
    data_dir = ROOT / "tables" / "data" / "raw"
    datasets = sorted(data_dir.glob(pattern))[:limit]
    if not datasets:
        print(f"❌ No se encontraron datasets con patrón: {pattern}")
        return False

    memory_path = analyze_memory.DEFAULT_MEMORY_PATH
    if not memory_path.exists():
        print("❌ No se encontró memoria entrenada")
        print("   Ejecuta primero: python3 -m utils.cli train-memory")
        return False

    print("==================================")
    print("✅ VALIDACIÓN DE ESTRATEGIAS")
    print("==================================\n")

    print("📊 Datasets de validación:")
    for ds in datasets:
        try:
            label = ds.relative_to(ROOT)
        except ValueError:
            label = ds
        print(f"  - {label}")
    print("")

    state = analyze_memory.load_memory(memory_path)
    if state:
        strategies = state.get("strategies", {})
        approved = [
            name
            for name, data in strategies.items()
            if data.get("wins", 0) + data.get("losses", 0) >= 500
        ]
        print("🧠 Memoria encontrada:")
        print(f"  Total estrategias: {len(strategies)}")
        print(f"  Estrategias aprobadas (>=500 trades): {len(approved)}\n")

        sorted_strats = sorted(
            [
                (name, strategies[name].get("winrate", 0))
                for name in approved
            ],
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        if sorted_strats:
            print("  Top 5 por winrate:")
            for name, winrate in sorted_strats:
                print(f"    - {name[:50]:50s}: {winrate:.2%}")
            print("")

    results_dir = ROOT / "results" / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    results_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(ROOT) if not python_path else f"{str(ROOT)}{os.pathsep}{python_path}"
    )

    total = len(datasets)
    failed = 0

    for idx, dataset in enumerate(datasets, 1):
        try:
            dataset_str = dataset.relative_to(ROOT).as_posix()
        except ValueError:
            dataset_str = str(dataset)

        out_file = results_dir / f"validation_{dataset.stem}.txt"
        print(f"[{idx}/{total}] Validando con: {dataset_str}")

        command = [
            PYTHON,
            "-c",
            textwrap.dedent(
                f"""
import sys
sys.path.insert(0, '.')
import config
config.MODE = "backtest"
config.DATASET_PATH = {dataset_str!r}
config.STARTING_BALANCE = {starting_balance}
import main  # noqa: F401
"""
            ),
        ]

        return_code = _stream_subprocess(command, env=env, log_path=out_file)
        if return_code == 0:
            print("  ✅ Validación completada\n")
        else:
            print("  ❌ Error en validación\n")
            failed += 1

    print("==================================")
    print("📊 VALIDACIÓN COMPLETADA")
    print("==================================\n")
    print("📁 Resultados guardados en:")
    print(f"   {results_dir.relative_to(ROOT)}\n")
    print("🎯 Analizar resultados:")
    print("   python3 -m utils.cli analyze-memory")
    print("   tail -n 40", results_dir.relative_to(ROOT) / "*.txt")
    print("==================================")
    return failed == 0


def run_full_pipeline(args) -> bool:
    start_time = datetime.now()

    print("")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                                                                ║")
    print("║     🎰 CASINO V2 - PIPELINE COMPLETO DE ENTRENAMIENTO         ║")
    print("║                                                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print("")
    print(f"⏰ Inicio: {start_time:%Y-%m-%d %H:%M:%S}\n")

    ok = run_download_training_data(
        symbols=args.symbols or [],
        interval=args.interval,
        days=args.days,
        tag=args.tag,
    )
    if not ok:
        print("❌ Error en Fase 1 (download-training-data)")
        return False

    if not args.non_interactive:
        input("⏸️  Presiona ENTER para continuar con Fase 2...")
        print("")

    ok = run_train_memory(pattern=args.pattern)
    if not ok:
        print("❌ Error en Fase 2 (train-memory)")
        return False

    if not args.non_interactive:
        input("⏸️  Presiona ENTER para continuar con Fase 3...")
        print("")

    analyze_memory.main()

    if not args.non_interactive:
        input("⏸️  Presiona ENTER para continuar con Fase 4...")
        print("")

    ok = run_validate_strategies(
        pattern=args.validation_pattern,
        limit=args.limit,
        starting_balance=args.starting_balance,
    )
    if not ok:
        print("❌ Error en Fase 4 (validate-strategies)")
        return False

    end_time = datetime.now()
    duration = end_time - start_time
    hours, remainder = divmod(duration.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)

    print("")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                                                                ║")
    print("║     ✅ PIPELINE COMPLETADO EXITOSAMENTE                        ║")
    print("║                                                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print("")
    print(f"⏱️  Tiempo total: {int(hours)}h {int(minutes)}m {int(seconds)}s\n")
    print("📁 Archivos generados:")
    print("   - Memoria: gemini/data/memory_state.json")
    print("   - Logs: logs/")
    print("   - Resultados: results/\n")
    print("🎯 Próximos pasos:")
    print("   1. Revisar análisis de memoria")
    print("   2. Revisar resultados de validación")
    print("   3. Configurar live/paper trading si todo está correcto\n")

    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Casino V2 consolidated utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_cmd = subparsers.add_parser("download-training-data", help="Descarga datasets históricos.")
    download_cmd.add_argument("--symbols", nargs="*", default=None, help="Símbolos a descargar (ej. BTCUSDT ETHUSDT).")
    download_cmd.add_argument("--interval", default="1m", help="Intervalo de velas (default: 1m).")
    download_cmd.add_argument("--days", type=int, default=1000, help="Días hacia atrás a descargar (default: 1000).")
    download_cmd.add_argument("--tag", default="training", help="Etiqueta para los archivos generados (default: training).")

    train_cmd = subparsers.add_parser("train-memory", help="Ejecuta el entrenamiento GHOST de la memoria.")
    train_cmd.add_argument("--pattern", default="*_training.csv", help="Patrón de datasets a usar (default: *_training.csv).")

    validate_cmd = subparsers.add_parser("validate-strategies", help="Valida estrategias entrenadas.")
    validate_cmd.add_argument("--pattern", default="*_15m_*.csv", help="Patrón de búsqueda de datasets.")
    validate_cmd.add_argument("--limit", type=int, default=3, help="Número máximo de datasets a validar (default: 3).")
    validate_cmd.add_argument("--starting-balance", type=float, default=10000.0, help="Balance inicial para la validación.")

    subparsers.add_parser("analyze-memory", help="Analiza el estado de la memoria Gemini.")
    subparsers.add_parser("check-sensors", help="Verifica sensores registrados y activos.")

    pipeline_cmd = subparsers.add_parser("full-pipeline", help="Ejecuta todo el pipeline de datos → entrenamiento → validación.")
    pipeline_cmd.add_argument("--symbols", nargs="*", default=None, help="Sobrescribe la lista de símbolos para la descarga.")
    pipeline_cmd.add_argument("--interval", default="1m", help="Intervalo de velas (default: 1m).")
    pipeline_cmd.add_argument("--days", type=int, default=1000, help="Días hacia atrás a descargar (default: 1000).")
    pipeline_cmd.add_argument("--tag", default="training", help="Etiqueta para los archivos generados (default: training).")
    pipeline_cmd.add_argument("--pattern", default="*_training.csv", help="Patrón de datasets para entrenamiento.")
    pipeline_cmd.add_argument("--validation-pattern", default="*_15m_*.csv", help="Patrón de datasets para validación.")
    pipeline_cmd.add_argument("--limit", type=int, default=3, help="Número máximo de datasets de validación.")
    pipeline_cmd.add_argument("--starting-balance", type=float, default=10000.0, help="Balance inicial usado en validación.")
    pipeline_cmd.add_argument("--non-interactive", action="store_true", help="Desactiva las pausas interactivas entre fases.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "download-training-data":
        ok = run_download_training_data(
            symbols=args.symbols or [],
            interval=args.interval,
            days=args.days,
            tag=args.tag,
        )
        return 0 if ok else 1

    if args.command == "train-memory":
        ok = run_train_memory(pattern=args.pattern)
        return 0 if ok else 1

    if args.command == "validate-strategies":
        ok = run_validate_strategies(
            pattern=args.pattern,
            limit=args.limit,
            starting_balance=args.starting_balance,
        )
        return 0 if ok else 1

    if args.command == "analyze-memory":
        return analyze_memory.main()

    if args.command == "check-sensors":
        return check_sensors.main()

    if args.command == "full-pipeline":
        ok = run_full_pipeline(args)
        return 0 if ok else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
