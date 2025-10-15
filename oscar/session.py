"""
Orquestador de sesiones para el modo Oscar.

Backtest:
    - Recorre datasets CSV con TableBacktest.
Live/Paper:
    - Usa BrokerInterface (TableAsterPaper) y ejecuta en tiempo real.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import config
from croupier.croupier import Croupier
from croupier.broker_interface import BrokerInterface
from sensors.sensor_manager import SensorManager
from tables.table_backtest import TableBacktest

from .oscar_grind_machine import SessionStatus
from .oscar_trader import OscarTrader


def run_oscar_session(dataset_path: str, initial_balance: float) -> Dict:
    dataset_name = os.path.basename(dataset_path)
    print(f"\n🎰 (Oscar) Ejecutando dataset: {dataset_name}")

    table = TableBacktest(dataset_path)
    _set_table_balance(table, initial_balance)

    logging.getLogger("SensorManager").setLevel(logging.WARNING)
    sensors = SensorManager()
    croupier = Croupier(table)
    trader = OscarTrader(croupier=croupier)

    candles = 0
    trades = 0
    wins = 0
    losses = 0
    total_fees = 0.0
    total_funding = 0.0
    liquidations = 0

    while True:
        candle = table.next_candle()
        if candle is None:
            break

        candles += 1
        sensors.process_candle(candle)

        table_state = _get_table_state(table)
        equity = float(table_state.get("equity", 0.0))

        # En backtest, no hay gestión de posición abierta/cerrada explícita
        # como en live. Cada vela es una oportunidad.
        entry_order = trader.check_for_entry(candle, equity)
        if not entry_order:
            continue

        result = croupier.route_order(entry_order)
        if not result:
            continue

        trades += 1
        total_fees += float(result.get("fee", 0.0) or 0.0)
        total_funding += float(result.get("funding", 0.0) or 0.0)
        if result.get("liquidated"):
            liquidations += 1

        outcome = str(result.get("result", "")).upper()
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1

        # Actualizar la state machine de Oscar
        pnl_units = trader._compute_pnl_units(result, equity)
        trader.state_machine.record_result(pnl_units)

        # Si la sesión alcanza el objetivo, se reinicia para seguir operando.
        if trader.state_machine.state.status == SessionStatus.TARGET_HIT:
            logging.getLogger("OscarSession").info(
                "🎯 Profit target hit! Reiniciando sesión de Oscar Grind."
            )
            trader.state_machine.start_new_session()

    final_state = _get_table_state(table)
    final_balance = float(final_state.get("balance", initial_balance))
    winrate = (wins / trades * 100.0) if trades > 0 else 0.0

    return {
        "dataset": dataset_name,
        "initial_balance": initial_balance,
        "candles": candles,
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "fees": total_fees,
        "funding": total_funding,
        "liquidations": liquidations,
        "final_balance": final_balance,
        "session": trader.state_machine.get_session_summary(),
    }


def print_oscar_summary(stats: Dict) -> None:
    session = stats.get("session", {})
    print("\n" + "=" * 70)
    print(f"📌 Dataset (Oscar)     : {stats['dataset']}")
    init_balance = stats.get("initial_balance")
    if isinstance(init_balance, (int, float)):
        init_str = f"{init_balance:.2f}"
    else:
        init_str = str(init_balance) if init_balance is not None else "n/a"
    print(f"💵 Balance inicial     : {init_str}")
    print(f"🧮 Trades              : {stats['trades']} (Wins {stats['wins']} / Losses {stats['losses']})")
    print(f"🎯 WinRate             : {stats['winrate']:.2f}%")
    print(f"💸 Comisiones          : {stats['fees']:.2f}")
    print(f"🏦 Funding             : {stats.get('funding', 0.0):.2f}")
    print(f"⚠️ Liquidaciones       : {stats.get('liquidations', 0)}")
    final_balance = stats.get("final_balance", 0.0)
    print(f"💰 Balance final       : {final_balance:.2f}")
    if isinstance(init_balance, (int, float)):
        profit = final_balance - init_balance
        print(f"📈 Ganancia/Perdida    : {profit:.2f}")
    pnl_units = session.get("session_pnl")
    pnl_str = f"{pnl_units:.4f}" if isinstance(pnl_units, (int, float)) else pnl_units
    print(f"♟️ Sesión Oscar        : {session.get('status')} | PnL unidades {pnl_str}")
    print("=" * 70 + "\n")


def _set_table_balance(table, amount: float) -> None:
    bm = getattr(table, "balance_manager", None)
    if not bm:
        return
    try:
        bm.balance = amount
        bm.equity = amount
    except Exception:
        if hasattr(bm, "set_balance"):
            bm.set_balance(amount)


def _get_table_state(table) -> Dict:
    bm = getattr(table, "balance_manager", None)
    if bm and hasattr(bm, "get_state"):
        try:
            return bm.get_state()
        except Exception:
            return {}
    return {}


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


LIVE_SLEEP_SECONDS = float(getattr(config, "LIVE_SLEEP_SECONDS", 1.0))
OSCAR_LIVE_LOGGER = logging.getLogger("OscarLiveSession")


def run_oscar_live_session(symbol: Optional[str] = None, interval: Optional[str] = None) -> None:
    """
    Ejecuta Oscar Grind en modo live/paper con gestión de estado de posición.
    """
    logging.getLogger().setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()
    if "KRAKEN" in exchange:
        default_symbol = getattr(config, "KRAKEN_FUTURES_SYMBOL", "PF_XBTUSD")
        default_interval = getattr(config, "KRAKEN_FUTURES_INTERVAL", "1m")
    else:
        default_symbol = getattr(config, "ASTER_DEFAULT_SYMBOL", "BTCUSDT")
        default_interval = getattr(config, "ASTER_DEFAULT_INTERVAL", "1m")

    if not symbol:
        try:
            user_symbol = input(f"Símbolo Oscar [{default_symbol}]: ").strip().upper()
        except EOFError:
            user_symbol = ""
        symbol = user_symbol or default_symbol

    if not interval:
        try:
            user_interval = input(f"Intervalo Oscar [{default_interval}]: ").strip()
        except EOFError:
            user_interval = ""
        
        if user_interval.isdigit():
            user_interval += "m"
            
        interval = user_interval or default_interval

    OSCAR_LIVE_LOGGER.info(
        "Iniciando Oscar Live | exchange=%s | symbol=%s | interval=%s",
        exchange,
        symbol,
        interval,
    )

    broker = BrokerInterface(symbol=symbol, interval=interval)
    table = broker.engine.table
    actual_symbol = getattr(table, "symbol", symbol)
    if actual_symbol and actual_symbol != symbol:
        OSCAR_LIVE_LOGGER.info("Símbolo normalizado por la mesa: %s -> %s", symbol, actual_symbol)
        symbol = actual_symbol

    croupier = Croupier(table)
    trader = OscarTrader(croupier=croupier)

    initial_state = _get_table_state(table)
    OSCAR_LIVE_LOGGER.info(
        "Balance inicial reportado | balance=%.4f | equity=%.4f",
        float(initial_state.get("balance", 0.0)),
        float(initial_state.get("equity", initial_state.get("balance", 0.0))),
    )
    initial_equity = _as_float(initial_state.get("equity"), _as_float(initial_state.get("balance")))

    trade_count = 0

    try:
        while True:
            candle = table.next_candle()
            if candle is None:
                time.sleep(LIVE_SLEEP_SECONDS)
                continue

            # El PositionManager está en la mesa
            pm = getattr(table, "position_manager", None)
            if not pm:
                raise RuntimeError("La mesa seleccionada no tiene un PositionManager.")

            equity_before = _get_table_state(table).get("equity", 0.0)

            # 1. Si hay una posición abierta, vigilar para cerrar
            if pm.is_position_open():
                open_pos = pm.get_open_position()
                exit_reason = pm.check_exit(candle["high"], candle["low"])

                if exit_reason:
                    exit_price = open_pos.stop_loss_price if exit_reason == "SL" else open_pos.take_profit_price
                    result = table.close_open_position(exit_price, exit_reason)
                    trade_count += 1

                    pnl_units = trader._compute_pnl_units(result, equity_before)
                    trader.state_machine.record_result(pnl_units)

                    session_summary = trader.state_machine.get_session_summary()
                    OSCAR_LIVE_LOGGER.info(
                        f"CIERRE: {result.get('result')} | PnL: {result.get('pnl_net'):.4f} | Razón: {exit_reason} | "
                        f"Trades: {trade_count} | Winrate: {session_summary.get('winrate_pct'):.2f}% | "
                        f"PnL Unidades: {session_summary.get('session_pnl'):.4f}u"
                    )

                    # Si la sesión alcanza el objetivo, se reinicia para seguir operando.
                    if trader.state_machine.state.status == SessionStatus.TARGET_HIT:
                        OSCAR_LIVE_LOGGER.info(
                            "🎯 Profit target hit! Reiniciando sesión de Oscar Grind."
                        )
                        trader.state_machine.start_new_session()
            
            # 2. Si no hay posición, buscar oportunidad para abrir
            else:
                entry_order = trader.check_for_entry(candle, equity_before)
                if entry_order:
                    croupier.route_order(entry_order)

    except KeyboardInterrupt:
        OSCAR_LIVE_LOGGER.info("🏁 Sesión Oscar finalizada manualmente por el usuario.")
    finally:
        if hasattr(table, "close_all_positions"):
            table.close_all_positions()

        final_state = _get_table_state(table)
        final_equity = _as_float(final_state.get("equity"), _as_float(final_state.get("balance")))
        change_equity = final_equity - initial_equity
        equity_span = f"${initial_equity:,.2f}->${final_equity:,.2f}"
        change_str = f"${change_equity:+,.2f}"
        session_summary = trader.state_machine.get_session_summary()
        session_status = session_summary.get("status", "UNKNOWN")
        session_pnl = session_summary.get("session_pnl")
        if isinstance(session_pnl, (int, float)):
            session_pnl_str = f"{session_pnl:+.4f}u"
        else:
            session_pnl_str = "n/a"
        wins = int(_as_float(session_summary.get("wins")))
        losses = int(_as_float(session_summary.get("losses")))
        draws = int(_as_float(session_summary.get("draws")))
        total_trades = wins + losses + draws
        winrate_pct = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

        OSCAR_LIVE_LOGGER.info(
            "🏁 Resumen final | trades=%d | status=%s | winrate=%.2f%% | historial=W%d/L%d/D%d | pnl_units=%s | equity=%s (%s)",
            trade_count,
            session_status,
            winrate_pct,
            wins,
            losses,
            draws,
            session_pnl_str,
            equity_span,
            change_str,
        )
