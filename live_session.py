"""
Runtime loop for live or paper trading sessions (ASTERDEx compatible).
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import config
from croupier.broker_interface import BrokerInterface
from croupier.croupier import Croupier
from gemini.gemini_core import Decision, Gemini
from sensors.sensor_manager import SensorManager

LIVE_SLEEP_SECONDS = float(getattr(config, "LIVE_SLEEP_SECONDS", 1.0))
RESULT_LOGGER = logging.getLogger("LiveSession")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_positive_int(value) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _prepare_order(
    decision: Decision,
    fallback_symbol: Optional[str],
    fallback_timestamp: Optional[str],
    fallback_timeframe: Optional[str],
) -> Dict:
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


def _get_table_state(table) -> Dict:
    if hasattr(table, "get_state"):
        try:
            return table.get_state() or {}
        except Exception:  # pragma: no cover - defensive
            return {}
    return {}


def _print_live_summary(stats: Dict) -> None:
    winrate = (stats.get("wins", 0) / stats.get("bet_trades", 0) * 100) if stats.get("bet_trades") else 0.0
    duration_minutes = stats.get("duration_seconds", 0.0) / 60.0
    max_candles = stats.get("max_candles")
    max_candles_str = str(max_candles) if max_candles else "∞"
    print("\n" + "=" * 60)
    print("📊 Resumen sesión Live")
    print("-" * 60)
    print(f"   Exchange              : {stats.get('exchange', 'n/a')}")
    print(f"   Símbolo               : {stats.get('symbol', 'n/a')}")
    print(f"   Intervalo             : {stats.get('interval', 'n/a')}")
    print(f"   Velas procesadas      : {stats.get('candles', 0)}")
    print(f"   Límite configurado    : {max_candles_str}")
    print(f"   Trades BET            : {stats.get('bet_trades', 0)}")
    print(f"   Trades GHOST          : {stats.get('ghost_trades', 0)}")
    print(f"   Wins / Losses (BET)   : {stats.get('wins', 0)} / {stats.get('losses', 0)}")
    print(f"   WinRate (BET)         : {winrate:.2f}%")
    print(f"   Comisiones totales    : {stats.get('fees', 0.0):.4f}")
    print(f"   Funding total         : {stats.get('funding', 0.0):.4f}")
    print(f"   Liquidaciones         : {stats.get('liquidations', 0)}")
    print(f"   Balance inicial       : {stats.get('initial_balance', 0.0):.2f}")
    print(f"   Equity inicial        : {stats.get('initial_equity', 0.0):.2f}")
    print(f"   Balance final         : {stats.get('final_balance', 0.0):.2f}")
    print(f"   Equity final          : {stats.get('final_equity', 0.0):.2f}")
    print(f"   Duración (min)        : {duration_minutes:.2f}")
    print(f"   Motivo de salida      : {stats.get('stop_reason', 'Finalizado')}")
    print("=" * 60 + "\n")


def run_live_session(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    max_candles: Optional[int] = None,
) -> None:
    """Ejecuta el loop live reutilizando BrokerInterface (exchange actual)."""
    logging.getLogger().setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()
    RESULT_LOGGER.info("Iniciando sesión live (exchange=%s)", exchange)

    if "KRAKEN" in exchange:
        default_symbol = getattr(config, "KRAKEN_FUTURES_SYMBOL", "PF_XBTUSD")
        default_interval = getattr(config, "KRAKEN_FUTURES_INTERVAL", "1m")
    else:
        default_symbol = getattr(config, "ASTER_DEFAULT_SYMBOL", "BTCUSDT")
        default_interval = getattr(config, "ASTER_DEFAULT_INTERVAL", "1m")

    if not symbol:
        try:
            user_symbol = input(f"Símbolo a operar [{default_symbol}]: ").strip().upper()
        except EOFError:
            user_symbol = ""
        symbol = user_symbol or default_symbol

    if not interval:
        try:
            user_interval = input(f"Intervalo de velas [{default_interval}]: ").strip()
        except EOFError:
            user_interval = ""
        interval = user_interval or default_interval

    if max_candles is not None:
        max_candles = _parse_positive_int(max_candles)
    else:
        max_candles_config = getattr(config, "LIVE_MAX_CANDLES", None)
        max_candles = _parse_positive_int(max_candles_config)
        prompt_default = str(max_candles) if max_candles else "∞"
        try:
            raw_limit = input(f"Máximo de velas antes de detenerse [{prompt_default}]: ").strip()
        except EOFError:
            raw_limit = ""
        if raw_limit:
            parsed_limit = _parse_positive_int(raw_limit)
            if parsed_limit is None:
                RESULT_LOGGER.warning("Entrada inválida para límite de velas. Continuando sin límite.")
                max_candles = None
            else:
                max_candles = parsed_limit

    broker = BrokerInterface(symbol=symbol, interval=interval)
    table = broker.engine.table
    actual_symbol = getattr(table, "symbol", symbol)
    if actual_symbol and actual_symbol != symbol:
        RESULT_LOGGER.info("Símbolo normalizado por la mesa: %s -> %s", symbol, actual_symbol)
        symbol = actual_symbol
    initial_state = _get_table_state(table)
    default_balance = getattr(config, "STARTING_BALANCE", 0.0)
    initial_balance = _safe_float(initial_state.get("balance"), default_balance)
    initial_equity = _safe_float(initial_state.get("equity"), initial_balance)
    RESULT_LOGGER.info(
        "Mesa live lista | symbol=%s | interval=%s | balance=%.4f | equity=%.4f",
        symbol,
        interval,
        float(initial_state.get("balance", 0.0)),
        float(initial_state.get("equity", initial_state.get("balance", 0.0))),
    )

    sensors = SensorManager()
    gemini = Gemini()
    croupier = Croupier(table)

    stats = {
        "exchange": exchange,
        "symbol": symbol,
        "interval": interval,
        "candles": 0,
        "bet_trades": 0,
        "ghost_trades": 0,
        "wins": 0,
        "losses": 0,
        "fees": 0.0,
        "funding": 0.0,
        "liquidations": 0,
        "max_candles": max_candles,
    }
    stop_reason = "Sesión finalizada correctamente."
    start_time = time.time()

    def limit_reached() -> bool:
        return max_candles is not None and stats["candles"] >= max_candles

    def register_limit_exit() -> None:
        nonlocal stop_reason
        stop_reason = f"Límite de {max_candles} velas alcanzado."
        RESULT_LOGGER.info("Límite de velas alcanzado (%s). Finalizando sesión...", max_candles)

    try:
        while True:
            candle = table.next_candle()
            if candle is None:
                time.sleep(LIVE_SLEEP_SECONDS)
                continue

            stats["candles"] += 1

            signals = sensors.process_candle(candle)
            if not signals:
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            equity = candle.get("equity")
            if equity is None:
                state = _get_table_state(table)
                equity = state.get("equity")

            decision = gemini.evaluate_signals(signals, equity=equity or 0.0)
            if decision.action == "SKIP":
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            order = _prepare_order(
                decision,
                fallback_symbol=candle.get("symbol"),
                fallback_timestamp=candle.get("timestamp"),
                fallback_timeframe=candle.get("timeframe"),
            )

            try:
                result = croupier.route_order(order)
            except Exception as exc:  # pragma: no cover - defensivo
                RESULT_LOGGER.exception("Fallo al enrutar orden live: %s", exc)
                time.sleep(LIVE_SLEEP_SECONDS)
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            RESULT_LOGGER.info(
                "live_trade | %s %s | action=%s | result=%s | qty=%s | size=%.4f",
                order.get("symbol"),
                order.get("side"),
                decision.action,
                result.get("result"),
                result.get("executed_qty", order.get("size")),
                float(order.get("size", 0.0)),
            )
            updated_state = _get_table_state(table)
            RESULT_LOGGER.debug(
                "state_update | balance=%.4f | equity=%.4f",
                float(updated_state.get("balance", 0.0)),
                float(updated_state.get("equity", updated_state.get("balance", 0.0))),
            )

            if decision.trade_id and result.get("result") in {"WIN", "LOSS"}:
                gemini.on_trade_result(decision.trade_id, result)

            outcome = (result.get("result") or "").upper()
            if decision.action == "BET":
                stats["bet_trades"] += 1
                stats["fees"] += _safe_float(result.get("fee"))
                stats["funding"] += _safe_float(result.get("funding"))
                if result.get("liquidated"):
                    stats["liquidations"] += 1
                if outcome == "WIN":
                    stats["wins"] += 1
                elif outcome == "LOSS":
                    stats["losses"] += 1
            elif decision.action == "GHOST":
                stats["ghost_trades"] += 1

            if limit_reached():
                register_limit_exit()
                break

            time.sleep(LIVE_SLEEP_SECONDS)
    except KeyboardInterrupt:
        stop_reason = "Sesión finalizada manualmente (Ctrl+C)."
        RESULT_LOGGER.info("Sesión live finalizada por el usuario.")
    finally:
        if hasattr(table, "close_all_positions"):
            table.close_all_positions()
        final_state = _get_table_state(table)
        final_balance = _safe_float(final_state.get("balance"), initial_balance)
        final_equity = _safe_float(final_state.get("equity"), final_balance)
        stats.update(
            {
                "initial_balance": initial_balance,
                "initial_equity": initial_equity,
                "final_balance": final_balance,
                "final_equity": final_equity,
                "wins": stats.get("wins", 0),
                "losses": stats.get("losses", 0),
                "duration_seconds": max(time.time() - start_time, 0.0),
                "stop_reason": stop_reason,
            }
        )
        _print_live_summary(stats)
