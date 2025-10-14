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
• El modo Oscar utiliza el dataset configurado en `DATASET_PATH` y produce
  un informe resumido con métricas clave.
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

from oscar.session import run_oscar_session, print_oscar_summary, run_oscar_live_session
from live_session import run_live_session


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
    total_funding = 0.0
    total_liquidations = 0

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
            total_funding += float(result.get("funding", 0.0) or 0.0)
            if result.get("liquidated"):
                total_liquidations += 1
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
        "initial_balance": initial_balance,
        "candles": candles,
        "bet_trades": bet_trades,
        "ghost_trades": ghost_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "fees": total_fees,
        "funding": total_funding,
        "final_balance": final_balance,
        "liquidations": total_liquidations,
    }


def print_session_summary(stats: Dict) -> None:
    print("\n" + "=" * 60)
    print(f"📌 Dataset: {stats['dataset']}")
    print("-" * 60)
    init_balance = stats.get("initial_balance")
    if isinstance(init_balance, (int, float)):
        init_str = f"{init_balance:.2f}"
    else:
        init_str = str(init_balance) if init_balance is not None else "n/a"
    print(f"   Balance inicial       : {init_str}")
    print(f"   Trades BET            : {stats['bet_trades']}")
    print(f"   Trades GHOST          : {stats['ghost_trades']}")
    print(f"   WinRate (BET)         : {stats['winrate']:.2f}%")
    print(f"   Comisiones totales    : {stats['fees']:.2f}")
    print(f"   Funding total         : {stats.get('funding', 0.0):.2f}")
    print(f"   Liquidaciones         : {stats.get('liquidations', 0)}")
    print(f"   Balance final         : {stats['final_balance']:.2f}")
    print("=" * 60 + "\n")


# ============================================================
# 🚀 ENTRYPOINT
# ============================================================
def main() -> None:
    enable_oscar = bool(getattr(config, "ENABLE_OSCAR_MODE", False))
    mode = getattr(config, "MODE", "backtest").lower()

    if mode == "live":
        if enable_oscar:
            run_oscar_live_session(symbol=None, interval=None)
        else:
            run_live_session(symbol=None, interval=None)
        return

    if enable_oscar:
        print("\n🎰 Bienvenido al Casino V2 — Sesión Oscar Grind\n")
        initial_balance = ask_initial_balance()
        dataset_path = getattr(config, "DATASET_PATH", "tables/data/raw/LTCUSDT_15min_bull.csv")
        stats = run_oscar_session(dataset_path, initial_balance)
        print_oscar_summary(stats)
        print("✅ Sesión Oscar completada.\n")
        return

    print("\n🎰 Bienvenido al Casino V2 — Sesión Backtest Gemini\n")

    initial_balance = ask_initial_balance()
    dataset_path = getattr(config, "DATASET_PATH", "tables/data/raw/LTCUSDT_15min_bull.csv")

    gemini = Gemini()

    print(f"\n🟢 Mesa única: {dataset_path}")
    stats = run_session(dataset_path, initial_balance, gemini)
    print_session_summary(stats)

    print("✅ Sesión Gemini completada.\n")


if __name__ == "__main__":
    main()
