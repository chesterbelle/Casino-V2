#!/usr/bin/env python3
"""Analiza los resultados detallados de gemini_trade_results.csv."""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict

# Construct an absolute path to the results file relative to this script's location
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(PROJECT_ROOT, "gemini", "data", "gemini_trade_results.csv")
RESULTS_PATH = os.getenv("TRADE_RESULTS_LOG_PATH", DEFAULT_PATH)


def load_results(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo {path}. Corre primero un backtest para generarlo.")
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def analyze_results_in_single_pass(reader):
    """Processes the CSV reader row-by-row to calculate all metrics in one go."""
    metrics = {
        "total": 0,
        "wins": 0,
        "losses": 0,
    }
    exit_breakdown = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})
    bars_sum = 0
    pnl_sum = 0.0

    for row in reader:
        if row.get("action") != "BET":
            continue

        metrics["total"] += 1
        outcome = row.get("result", "").upper()
        if outcome == "WIN":
            metrics["wins"] += 1
        elif outcome == "LOSS":
            metrics["losses"] += 1

        reason = row.get("exit_reason", "UNKNOWN")
        entry = exit_breakdown[reason]
        entry["total"] += 1
        if outcome == "WIN":
            entry["wins"] += 1
        elif outcome == "LOSS":
            entry["losses"] += 1

        try:
            bars_sum += int(row.get("bars_held", 0) or 0)
        except (ValueError, TypeError):
            pass
        try:
            pnl_sum += float(row.get("pnl_pct", 0.0) or 0.0)
        except (ValueError, TypeError):
            pass

    avg_bars = (bars_sum / metrics["total"]) if metrics["total"] else 0.0
    avg_pnl_pct = (pnl_sum / metrics["total"]) if metrics["total"] else 0.0

    metrics["avg_bars"] = avg_bars
    metrics["avg_pnl_pct"] = avg_pnl_pct

    return metrics, exit_breakdown


def main() -> None:
    try:
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            metrics, exit_breakdown = analyze_results_in_single_pass(reader)
    except FileNotFoundError:
        print(f"⚠️ No existe el archivo {RESULTS_PATH}. Corre primero un backtest para generarlo.")
        return
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado al procesar el archivo: {e}")
        return

    print("Resumen general (solo BET):")
    if metrics["total"] == 0:
        print("  No se encontraron trades de tipo 'BET' en el archivo.")
        return

    print(f"  Trades totales : {metrics['total']}")
    print(f"  Wins / Losses  : {metrics['wins']} / {metrics['losses']}")
    winrate = (metrics["wins"] / metrics["total"] * 100) if metrics["total"] else 0.0
    print(f"  Winrate        : {winrate:.2f}%")
    print(f"  Avg. velas     : {metrics['avg_bars']:.2f}")
    print(f"  Avg. pnl_pct   : {metrics['avg_pnl_pct']:.4f}")
    print()

    print("Breakdown por exit_reason:")
    for reason, data in sorted(exit_breakdown.items(), key=lambda x: x[0]):
        total = data["total"]
        win = data["wins"]
        loss = data["losses"]
        wr = (win / total * 100) if total else 0.0
        print(f"  {reason:<15} -> total={total:5d} | wins={win:4d} | losses={loss:4d} | winrate={wr:5.2f}%")


if __name__ == "__main__":
    main()
