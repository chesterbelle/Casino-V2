#!/usr/bin/env python3
"""
Validación de Estrategias Gemini
--------------------------------
Este script valida las estrategias que han sido aprobadas en la memoria de Gemini.
Ejecuta backtests en datasets de validación (distintos a los de entrenamiento) y reporta
el desempeño de las estrategias seleccionadas.

Uso:
    python3 utils/training/validate.py --pattern "*_15m_*.csv" --limit 3

Argumentos:
    --pattern: Patrón de búsqueda para los archivos CSV de validación (default: *_15m_*.csv)
    --limit: Número máximo de datasets a procesar (default: 3)
    --starting-balance: Balance inicial para la simulación (default: 10000.0)
"""

import sys
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.cli import main as cli_main


def main():
    """Ejecuta el comando validate-strategies del CLI unificado."""
    # Pasar los argumentos recibidos al CLI, anteponiendo el comando 'validate-strategies'
    args = ["validate-strategies"] + sys.argv[1:]
    return cli_main(args)


if __name__ == "__main__":
    sys.exit(main())
