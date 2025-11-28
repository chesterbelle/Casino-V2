#!/usr/bin/env python3
"""
Entrenamiento de Memoria Gemini (Directo)
-----------------------------------------
Este script ejecuta el entrenamiento de la memoria de Gemini iterando directamente
sobre los archivos de datos, sin usar subprocesos ni archivos de configuración temporales.

Uso:
    python3 utils/training/train.py [--pattern "*_training.csv"]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Configurar logging básico para este script
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TrainMemory")

# Importaciones del proyecto
import config.system as system_config
from main import run_backtest
from players import paroli_player


async def train_on_dataset(dataset_path: Path):
    """Ejecuta una sesión de entrenamiento sobre un dataset."""
    logger.info(f"🧠 Entrenando con: {dataset_path.name}")

    # Configuración para entrenamiento
    # Nota: En el futuro, si necesitamos overrides específicos (como FORCE_GHOST),
    # deberíamos pasarlos como argumentos a run_backtest o usar un contexto.
    # Por ahora, confiamos en que el modo 'backtest' y la lógica de Gemini manejan
    # el aprendizaje correctamente.

    try:
        # Ejecutar backtest
        # Usamos un balance alto para evitar quiebras durante el entrenamiento
        await run_backtest(
            player_module=paroli_player, data_file=str(dataset_path), max_candles=None, initial_balance=10000.0
        )
        logger.info(f"✅ Entrenamiento completado para {dataset_path.name}")
        return True
    except Exception as e:
        logger.error(f"❌ Error entrenando con {dataset_path.name}: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Entrenamiento de Memoria Gemini")
    parser.add_argument(
        "--pattern",
        default="*_training.csv",
        help="Patrón de búsqueda para datasets en data/raw (default: *_training.csv)",
    )
    args = parser.parse_args()

    # Buscar datasets
    data_dir = ROOT / "data" / "raw"
    # Fallback a tables/data/raw si data/raw no existe o está vacío (compatibilidad)
    if not data_dir.exists():
        data_dir = ROOT / "tables" / "data" / "raw"

    datasets = sorted(data_dir.glob(args.pattern))

    if not datasets:
        logger.error(f"❌ No se encontraron datasets con el patrón '{args.pattern}' en {data_dir}")
        return 1

    logger.info(f"📊 Datasets encontrados: {len(datasets)}")

    success_count = 0
    for i, dataset in enumerate(datasets, 1):
        logger.info(f"\n[{i}/{len(datasets)}] Procesando {dataset.name}...")
        if await train_on_dataset(dataset):
            success_count += 1

    logger.info("\n" + "=" * 50)
    logger.info(f"🎉 Entrenamiento finalizado: {success_count}/{len(datasets)} exitosos")
    logger.info("=" * 50)

    return 0 if success_count == len(datasets) else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("\n⚠️ Entrenamiento interrumpido por el usuario")
        sys.exit(130)
