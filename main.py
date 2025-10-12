"""
====================================================
🎰 CASINO V2 — Main (Backtest secuencial Bull → Bear)
====================================================

Flujo maestro:
--------------
1) Solicita balance inicial por consola.
2) Crea mesa (feed) para cada dataset (bull, luego bear).
3) Por cada vela:
   - Sensores generan señales
   - Gemini decide (BET o GHOST) con Kelly conservador
   - Croupier opera contra la mesa activa (feed)
   - Mesa devuelve resultado normalizado (WIN/LOSS + balance)
   - Gemini actualiza su memoria (por estrategia individual)
4) Imprime métricas al final por sesión y globales.

Principios de diseño:
---------------------
• El feed (mesa) es el que "simula o no" — el Croupier siempre opera igual.
• Gemini decide sin conocer el origen de los datos.
• Aun cuando no se apuesta (sin aprobaciones / sin edge), se genera GHOST
  para entrenar igualmente (shadow trading).
• Se procesan los dos datasets en secuencia (bull → bear), manteniendo memoria.

Modo Oscar:
-----------
• Para activar Oscar Grind, define en `config.py` → `ENABLE_OSCAR_MODE = True`.
• Opcionales `OSCAR_*` (fracciones, límites de unidades) ajustan sizing.
• Oscar usa su propio RangeSensor y state machine, pero sigue enviando
  órdenes al mismo Croupier/Mesa que Gemini.

PUNTOS DE EXTENSIÓN:
--------------------
• Reemplazar TableBacktest por BrokerInterface/TableRealtime cuando MODE="live".
• Añadir nuevas mesas en tables/ y nuevos croupiers en croupier/.
• Ajustar sensores en sensors/ (más estrategias de reversión).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional, Tuple

import config
from croupier.croupier import Croupier
from gemini.gemini_core import Decision, Gemini
from sensors.sensor_manager import SensorManager
from tables.table_backtest import TableBacktest

from oscar.session import run_oscar_session, print_oscar_summary


# ============================================================
# 🪙 LOGGING GLOBAL
# ============================================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


# ============================================================
# 🧰 HELPERS
# ============================================================
def ask_initial_balance() -> float:
    """Pide balance inicial por consola; fallback a config.STARTING_BALANCE."""
    try:
        raw = input("💰 Ingrese balance inicial (ej. 10000): ").strip()
        if not raw:
            raise ValueError
        value = float(raw.replace(",", ""))
        if value <= 0:
            raise ValueError
        return value
    except Exception:
        default = float(getattr(config, "STARTING_BALANCE", 10_000.0))
        print(f"⚠️ Valor inválido. Usando STARTING_BALANCE de config: {default:.2f}")
        return default


def _prepare_order(
    decision: Decision,
    fallback_symbol: str,
    fallback_timestamp: Optional[str],
    fallback_timeframe: Optional[str],
) -> Dict:
    """Normaliza la orden antes de enviarla al crupier."""
    order = dict(decision.order or {})
    order.setdefault("symbol", fallback_symbol)
    order.setdefault("timestamp", fallback_timestamp)
    order.setdefault("timeframe", fallback_timeframe)
    if fallback_symbol and fallback_timeframe and fallback_timeframe != "UNKNOWN":
        order.setdefault("market", f"{fallback_symbol}@{fallback_timeframe}")
    order.setdefault("side", decision.side)
    order.setdefault("size", 0.0)
    tp_default = 1.0 + getattr(config, "TAKE_PROFIT", 0.01)
    sl_default = 1.0 - getattr(config, "STOP_LOSS", 0.01)
    order.setdefault("take_profit", tp_default)
    order.setdefault("stop_loss", sl_default)
    order["trade_id"] = decision.trade_id
    order["ghost"] = decision.action == "GHOST"
    return order


def _set_table_balance(table: TableBacktest, amount: float) -> None:
    """Fuerza el balance inicial de la mesa."""
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


def _log_trade(decision: Decision, order: Dict, result: Dict, balance: Optional[float]) -> None:
    logger = logging.getLogger("Session")
    logger.info(
        "🎲 %s | %s %s | size=%.4f | outcome=%s | exit=%s | bars=%s | pnl_pct=%.4f | balance=%s",
        decision.action,
        order.get("symbol", "?"),
        order.get("side", "?"),
        float(order.get("size", 0.0)),
        result.get("result", "?"),
        result.get("exit_reason", "?"),
        result.get("bars_held", "?"),
        float(result.get("pnl_pct", 0.0)),
        f"{balance:.2f}" if balance is not None else "n/a",
    )


# ============================================================
# 🎛️ SESIÓN INDIVIDUAL
# ============================================================
def run_session(dataset_path: str, initial_balance: float, gemini: Gemini) -> Dict:
    dataset_name = os.path.basename(dataset_path)
    print(f"\n🎰 Ejecutando dataset: {dataset_name}")

    table = TableBacktest(dataset_path)
    _set_table_balance(table, initial_balance)

    sensors = SensorManager()
    croupier = Croupier(table)

    candles = 0
    bet_trades = 0
    ghost_trades = 0
    wins = 0
    losses = 0
    total_fees = 0.0

    while True:
        candle = table.next_candle()
        if candle is None:
            break

        candles += 1
        signals = sensors.process_candle(candle)
        if not signals:
            continue

        equity = candle.get("equity")
        if equity is None:
            equity = _get_table_state(table).get("equity", initial_balance)

        decision = gemini.evaluate_signals(signals, equity=equity)
        if decision.action == "SKIP":
            continue

        order = _prepare_order(
            decision,
            fallback_symbol=candle.get("symbol", table.symbol),
            fallback_timestamp=candle.get("timestamp"),
            fallback_timeframe=candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN")),
        )

        result = croupier.route_order(order)

        if decision.trade_id:
            gemini.on_trade_result(decision.trade_id, result)

        outcome = result.get("result", "").upper()
        if decision.action == "BET":
            bet_trades += 1
            total_fees += float(result.get("fee", 0.0) or 0.0)
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
        elif decision.action == "GHOST":
            ghost_trades += 1

        balance = _get_table_state(table).get("balance")
        _log_trade(decision, order, result, balance)

    final_state = _get_table_state(table)
    final_balance = float(final_state.get("balance", initial_balance))
    winrate = (wins / bet_trades * 100) if bet_trades > 0 else 0.0

    return {
        "dataset": dataset_name,
        "candles": candles,
        "bet_trades": bet_trades,
        "ghost_trades": ghost_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "fees": total_fees,
        "final_balance": final_balance,
    }


def print_session_summary(stats: Dict) -> None:
    print("\n" + "=" * 60)
    print(f"📌 Dataset: {stats['dataset']}")
    print("-" * 60)
    print(f"   Trades BET            : {stats['bet_trades']}")
    print(f"   Trades GHOST          : {stats['ghost_trades']}")
    print(f"   WinRate (BET)         : {stats['winrate']:.2f}%")
    print(f"   Comisiones totales    : {stats['fees']:.2f}")
    print(f"   Balance final         : {stats['final_balance']:.2f}")
    print("=" * 60 + "\n")


# ============================================================
# 🚀 ENTRYPOINT
# ============================================================
def main() -> None:
    enable_oscar = bool(getattr(config, "ENABLE_OSCAR_MODE", False))
    mode = getattr(config, "MODE", "backtest").lower()

    if enable_oscar:
        print("\n🎰 Bienvenido al Casino V2 — Sesión Oscar Grind\n")
        initial_balance = ask_initial_balance()
        datasets: Tuple[Tuple[str, str], ...] = (
            ("🟢 Mesa (Oscar) Bull", "tables/data/raw/LTCUSDT_15min_bull.csv"),
            ("🔴 Mesa (Oscar) Bear", "tables/data/raw/LTCUSDT_15min_bear.csv"),
        )

        current_balance = initial_balance
        total_trades = total_wins = total_losses = 0
        total_fees = 0.0

        for title, path in datasets:
            print(f"\n{title}")
            stats = run_oscar_session(path, current_balance)
            print_oscar_summary(stats)

            current_balance = stats["final_balance"]
            total_trades += stats["trades"]
            total_wins += stats["wins"]
            total_losses += stats["losses"]
            total_fees += stats["fees"]

        wr_global = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        print("\n" + "#" * 60)
        print("🏁 RESUMEN GLOBAL OSCAR (Bull → Bear)")
        print("#" * 60)
        print(f"   WinRate global        : {wr_global:.2f}%")
        print(f"   Trades totales        : {total_trades}")
        print(f"   Comisiones totales    : {total_fees:.2f}")
        print(f"   Balance final global  : {current_balance:.2f}")
        print("#" * 60 + "\n")
        print("✅ Sesión Oscar completada.\n")
        return

    print("\n🎰 Bienvenido al Casino V2 — Sesión Backtest secuencial (Bull → Bear)\n")

    initial_balance = ask_initial_balance()
    datasets: Tuple[Tuple[str, str], ...] = (
        ("🟢 Mesa 1: Bull", "tables/data/raw/LTCUSDT_15min_bull.csv"),
        ("🔴 Mesa 2: Bear", "tables/data/raw/LTCUSDT_15min_bear.csv"),
    )

    gemini = Gemini()
    current_balance = initial_balance

    total_bet = total_ghost = total_wins = total_losses = 0
    total_fees = 0.0
    session_history = []

    for title, path in datasets:
        print(f"\n{title}")
        stats = run_session(path, current_balance, gemini)
        session_history.append(stats)
        print_session_summary(stats)

        current_balance = stats["final_balance"]
        total_bet += stats["bet_trades"]
        total_ghost += stats["ghost_trades"]
        total_wins += stats["wins"]
        total_losses += stats["losses"]
        total_fees += stats["fees"]

    wr_global = (total_wins / total_bet * 100) if total_bet > 0 else 0.0

    print("\n" + "#" * 60)
    print("🏁 RESUMEN GLOBAL (Bull → Bear)")
    print("#" * 60)
    print(f"   WinRate global (BET)  : {wr_global:.2f}%")
    print(f"   Trades BET totales    : {total_bet}")
    print(f"   Trades GHOST totales  : {total_ghost}")
    print(f"   Comisiones totales    : {total_fees:.2f}")
    print(f"   Balance final global  : {current_balance:.2f}")
    print("#" * 60 + "\n")
    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    if getattr(config, "MODE", "backtest").lower() != "backtest":
        print("⚠️ MODE no es 'backtest'. Este main está enfocado al modo backtest.")
    main()
