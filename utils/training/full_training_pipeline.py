#!/usr/bin/env python3
"""
Pipeline Completo de Entrenamiento Gemini
-----------------------------------------
Ejecuta el flujo completo de entrenamiento de memoria:
1. Descarga de datos históricos (si es necesario)
2. Entrenamiento de memoria (GHOST Mode)
3. Análisis de memoria
4. Validación de estrategias

Uso Básico:
    python3 utils/training/pipeline.py --symbols BTCUSDT --days 30

Uso Avanzado:
    python3 utils/training/pipeline.py --symbols BTCUSDT ETHUSDT --interval 5m --days 60 --tag mi_experimento

Argumentos Principales:
    --symbols: Lista de símbolos a descargar/usar (ej: BTCUSDT ETHUSDT)
    --days:    Días de historia hacia atrás a descargar (default: 1000).
               Esto determina el tamaño del dataset. Ej: --days 30 descarga el último mes.
    --interval: Intervalo de velas (default: 1m).
               Opciones comunes: 1m, 5m, 15m, 1h, 4h, 1d.

Argumentos Opcionales:
    --tag: Etiqueta para los archivos generados (default: training).
           Útil para organizar diferentes experimentos.
    --non-interactive: Ejecutar sin pausas para confirmación (ideal para scripts automáticos).
"""

import sys
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.cli import main as cli_main
from utils.training.train import main as train_main


def main():
    """Ejecuta el pipeline de entrenamiento."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", help="Símbolos a descargar")
    parser.add_argument("--days", type=int, default=30, help="Días a descargar")
    parser.add_argument("--interval", default="1m", help="Intervalo")
    parser.add_argument("--tag", default="training", help="Tag para archivos")
    args = parser.parse_args()

    # 1. Descargar datos (usando CLI existente por ahora)
    print("⬇️  Fase 1: Descarga de datos...")
    cli_args = ["download-training-data", "--interval", args.interval, "--days", str(args.days), "--tag", args.tag]
    if args.symbols:
        cli_args.extend(["--symbols"] + args.symbols)

    if cli_main(cli_args) != 0:
        print("❌ Error en descarga")
        return 1

    # 2. Entrenar (usando nuevo script directo)
    print("\n🧠 Fase 2: Entrenamiento...")
    # Hack: manipular sys.argv para que train.py lea los argumentos correctos si es necesario,
    # o llamar a una función que acepte argumentos. Por simplicidad en este refactor rápido,
    # llamamos a train_main pero necesitamos asegurar que sys.argv sea compatible o refactorizar train.py
    # para aceptar args.
    # Mejor opción: invocar train.py como subprocess para aislar args, O refactorizar train.py para exponer una funcion run(pattern).
    # Dado que acabamos de escribir train.py con argparse en main, lo más limpio es llamarlo via subprocess
    # para no pelear con sys.argv global, O refactorizar train.py.
    # Vamos a usar subprocess para train.py para mantener aislamiento de argumentos por ahora,
    # ya que pipeline.py es un orquestador.

    import subprocess

    cmd = [sys.executable, "utils/training/train.py", "--pattern", f"*_{args.tag}.csv"]
    if subprocess.call(cmd) != 0:
        print("❌ Error en entrenamiento")
        return 1

    # 3. Analizar (usando wrapper nuevo)
    print("\n📊 Fase 3: Análisis...")
    from utils.analysis import analyze_memory

    analyze_memory()

    print("\n✅ Pipeline finalizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
