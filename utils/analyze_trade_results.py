#!/usr/bin/env python3
"""Analiza los resultados detallados de gemini_trade_results.csv."""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict

RESULTS_PATH = os.getenv("TRADE_RESULTS_LOG_PATH", "gemini/data/gemini_trade_results.csv")


def load_results(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo {path}. Corre primero un backtest para generarlo.")
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(results):
    metrics = {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "avg_bars": 0.0,
        "avg_pnl_pct": 0.0,
    }
    exit_counter = Counter()
    bars_sum = 0
    pnl_sum = 0.0

    for row in results:
        if row.get("action") != "BET":
            continue
        metrics["total"] += 1
        outcome = row.get("result", "").upper()
        if outcome == "WIN":
            metrics["wins"] += 1
        elif outcome == "LOSS":
            metrics["losses"] += 1
        exit_counter[row.get("exit_reason", "UNKNOWN")] += 1
        try:
            bars_sum += int(row.get("bars_held", 0) or 0)
        except ValueError:
            pass
        try:
            pnl_sum += float(row.get("pnl_pct", 0.0) or 0.0)
        except ValueError:
            pass

    if metrics["total"]:
        metrics["avg_bars"] = bars_sum / metrics["total"]
        metrics["avg_pnl_pct"] = pnl_sum / metrics["total"]
    return metrics, exit_counter


def summarize_by_exit(results):
    by_exit = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})
    for row in results:
        if row.get("action") != "BET":
            continue
        reason = row.get("exit_reason", "UNKNOWN")
        entry = by_exit[reason]
        entry["total"] += 1
        outcome = row.get("result", "").upper()
        if outcome == "WIN":
            entry["wins"] += 1
        elif outcome == "LOSS":
            entry["losses"] += 1
    return by_exit


def main() -> None:
    try:
        results = load_results(RESULTS_PATH)
    except FileNotFoundError as exc:
        print(f"⚠️ {exc}")
        return

    metrics, exits = summarize(results)
    exit_breakdown = summarize_by_exit(results)

    print("Resumen general (solo BET):")
    print(f"  Trades totales : {metrics['total']}")
    print(f"  Wins / Losses  : {metrics['wins']} / {metrics['losses']}")
    winrate = (metrics['wins'] / metrics['total'] * 100) if metrics['total'] else 0.0
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
        print(f"  {reason:<10} -> total={total:5d} | wins={win:4d} | losses={loss:4d} | winrate={wr:5.2f}%")


if __name__ == "__main__":
    main()
