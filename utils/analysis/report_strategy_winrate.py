#!/usr/bin/env python3
"""Resumen de winrate por estrategia a partir de gemini/data/memory_log.csv."""

from __future__ import annotations

import csv
import logging
import os

logger = logging.getLogger(__name__)
from collections import Counter

# Construct an absolute path to the log file relative to this script's location
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(PROJECT_ROOT, "gemini", "data", "memory_log.csv")
LOG_PATH = os.getenv("MEMORY_LOG_PATH", DEFAULT_PATH)


def main() -> None:
    if not os.path.exists(LOG_PATH):
        logger.warning(f"⚠️ No se encontró el archivo {LOG_PATH}. Ejecuta un backtest primero.")
        return

    wins = Counter()
    losses = Counter()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "strategy" not in reader.fieldnames or "result" not in reader.fieldnames:
            logger.warning("⚠️ El archivo no contiene las columnas esperadas (strategy, result).")
            return
        for row in reader:
            strat = row.get("strategy", "UNKNOWN")
            try:
                result = int(row.get("result", 0))
            except ValueError:
                continue
            if result == 1:
                wins[strat] += 1
            else:
                losses[strat] += 1

    print("Estrategia,Winrate (%)")
    logger.info("Estrategia,Winrate (%)")
    for strat in sorted(set(wins) | set(losses)):
        total = wins[strat] + losses[strat]
        if total == 0:
            continue
        wr = wins[strat] / total * 100
        logger.info(f"{strat},{wr:.2f}")


if __name__ == "__main__":
    main()
