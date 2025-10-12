"""
Orquestador de sesiones para el modo Oscar.

Se inspira en `main.run_session`, pero delega la toma de decisiones
al `OscarTrader` y mantiene el flujo de mesas/croupier existente.
"""

from __future__ import annotations

import os
from typing import Dict, List

import config
from croupier.croupier import Croupier
from sensors.sensor_manager import SensorManager
from tables.table_backtest import TableBacktest

from .oscar_trader import OscarTrader


def run_oscar_session(dataset_path: str, initial_balance: float) -> Dict:
    dataset_name = os.path.basename(dataset_path)
    print(f"\n🎰 (Oscar) Ejecutando dataset: {dataset_name}")

    table = TableBacktest(dataset_path)
    _set_table_balance(table, initial_balance)

    sensors = SensorManager()
    croupier = Croupier(table)
    trader = OscarTrader(croupier=croupier)

    candles = 0
    trades = 0
    wins = 0
    losses = 0
    total_fees = 0.0

    while True:
        candle = table.next_candle()
        if candle is None:
            break

        candles += 1
        sensors.process_candle(candle)  # Mantiene entrenamiento de sensores existentes

        table_state = _get_table_state(table)
        summary = trader.process_candle(candle, table_state)
        if not summary or not summary.get("executed"):
            continue

        trades += 1
        result = summary["result"]
        total_fees += float(result.get("fee", 0.0) or 0.0)

        outcome = str(result.get("result", "")).upper()
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1

    final_state = _get_table_state(table)
    final_balance = float(final_state.get("balance", initial_balance))
    winrate = (wins / trades * 100.0) if trades > 0 else 0.0

    return {
        "dataset": dataset_name,
        "candles": candles,
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "fees": total_fees,
        "final_balance": final_balance,
        "session": trader.state_machine.get_session_summary(),
    }


def print_oscar_summary(stats: Dict) -> None:
    print("\n" + "=" * 60)
    print(f"📌 Dataset (Oscar): {stats['dataset']}")
    print("-" * 60)
    print(f"   Trades ejecutados    : {stats['trades']}")
    print(f"   WinRate              : {stats['winrate']:.2f}%")
    print(f"   Comisiones totales   : {stats['fees']:.2f}")
    print(f"   Balance final        : {stats['final_balance']:.2f}")
    session = stats.get("session", {})
    print(f"   Estado sesión Oscar  : {session.get('status')}")
    print(f"   PnL sesión (unidades): {session.get('session_pnl')}")
    print("=" * 60 + "\n")


def _set_table_balance(table: TableBacktest, amount: float) -> None:
    bm = getattr(table, "balance_manager", None)
    if not bm:
        return
    try:
        bm.balance = amount
        bm.equity = amount
    except Exception:
        if hasattr(bm, "set_balance"):
            bm.set_balance(amount)


def _get_table_state(table: TableBacktest) -> Dict:
    bm = getattr(table, "balance_manager", None)
    if bm and hasattr(bm, "get_state"):
        try:
            return bm.get_state()
        except Exception:
            return {}
    return {}

