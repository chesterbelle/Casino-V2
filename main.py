"""
====================================================
🎰 CASINO V2 — Main con arquitectura Gemini + Player
====================================================

NUEVA ARQUITECTURA (Fase 1 - Separación de Responsabilidades):
---------------------------------------------------------------
1) Gemini valida oportunidades → retorna Verdict
2) Player decide tamaño → retorna size_fraction
3) Gemini construye orden → make_order_from_verdict()
4) Croupier ejecuta → route_order()
5) Gemini actualiza memoria → on_trade_result()

Ventajas sobre main.py:
-----------------------
✅ Gemini solo valida probabilidades (responsabilidad única)
✅ Players intercambiables (Kelly, Fixed%, Adaptive, etc.)
✅ Testing independiente de validación vs sizing
✅ Extensible para múltiples players simultáneos

Uso:
----
    python main_v2.py              # Usa Kelly Player (default)
    python main_v2.py --player=fixed  # Usa Fixed Player
    
Compatibilidad:
---------------
• Usa las mismas mesas, sensores y croupiers que V1
• Memoria Gemini 100% compatible
• Resultados matemáticamente idénticos a main.py (con Kelly)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Dict, Optional

import config
from croupier.croupier import Croupier
from gemini.gemini_core import Verdict, Gemini
from sensors.sensor_manager import SensorManager
from tables.table_backtest import TableBacktest
from tables.table_ccxt_pro import TableCCXTPro
from tables.table_backtest_multiasset import TableBacktestMultiAsset
from tables.position_tracker import PositionTracker
from players import kelly_player, fixed_player, paroli_player

from live_session import run_live_session


# ============================================================
# 🪙 LOGGING GLOBAL
# ============================================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("MainV2")


# ============================================================
# 🎮 CONFIGURACIÓN DE PLAYERS
# ============================================================
AVAILABLE_PLAYERS = {
    "kelly": kelly_player,
    "fixed": fixed_player,
    "paroli": paroli_player,
}

# Player por defecto (Kelly conservador)
DEFAULT_PLAYER = "paroli"


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


def _log_trade(action: str, verdict: Verdict, order: Dict, result: Dict, balance: Optional[float]) -> None:
    """Log estandarizado de trades"""
    notional_amount = result.get("notional")
    if notional_amount is None:
        size_fraction = float(order.get("size", 0.0))
        try:
            if balance is not None:
                equity_reference = float(balance)
            else:
                equity_reference = float(result.get("balance", 0.0))
        except (TypeError, ValueError):
            equity_reference = 0.0
        notional_amount = equity_reference * size_fraction
    try:
        notional_amount = float(notional_amount)
    except (TypeError, ValueError):
        notional_amount = 0.0
    unit_multiplier = order.get("unit_multiplier")
    try:
        unit_multiplier = float(unit_multiplier)
    except (TypeError, ValueError):
        unit_multiplier = None
    if unit_multiplier is None or unit_multiplier <= 0:
        unit_multiplier = 1.0

    unit_amount = order.get("unit_amount")
    try:
        unit_amount = float(unit_amount)
    except (TypeError, ValueError):
        unit_amount = None
    if unit_amount is None or unit_amount <= 0:
        unit_amount = notional_amount / unit_multiplier if unit_multiplier > 0 else notional_amount

    try:
        unit_display = float(unit_amount)
    except (TypeError, ValueError):
        unit_display = 0.0
    unit_count_display = int(unit_multiplier) if abs(unit_multiplier - round(unit_multiplier)) < 1e-6 else unit_multiplier

    logger.info(
        "🎲 %s | %s %s | Unidad=%su(%.2fUSD) | outcome=%s | exit=%s | bars=%s | pnl_pct=%.4f | balance=%s",
        action,
        order.get("symbol", "?"),
        order.get("side", "?"),
        unit_count_display,
        unit_display,
        result.get("result", "?"),
        result.get("exit_reason", "?"),
        result.get("bars_held", "?"),
        float(result.get("pnl_pct", 0.0)),
        f"{balance:.2f}" if balance is not None else "n/a",
    )


# ============================================================
# 🎛️ SESIÓN INDIVIDUAL CON PLAYER
# ============================================================
def run_session_with_player(
    dataset_path: str,
    initial_balance: float,
    gemini: Gemini,
    player_module,
    player_name: str,
    mode: str = "backtest",
    multi_asset_config: Optional[Dict] = None
) -> Dict:
    """
    Ejecuta una sesión de backtest usando la arquitectura Gemini + Player con gestión de posiciones.

    Args:
        dataset_path: Ruta al CSV con datos históricos
        initial_balance: Capital inicial
        gemini: Instancia de Gemini (validador)
        player_module: Módulo del player (kelly_player, fixed_player, etc.)
        player_name: Nombre del player para logging

    Returns:
        Dict con estadísticas de la sesión
    """
    dataset_name = os.path.basename(dataset_path)
    print(f"\n🎰 Ejecutando dataset: {dataset_name}")
    print(f"🎮 Player activo: {player_name.upper()}")

    # Seleccionar tabla según modo
    if mode == "multi_asset_backtest" and multi_asset_config:
        print("🔄 Usando TableBacktestMultiAsset")
        table = TableBacktestMultiAsset(
            symbol_configs=multi_asset_config,
            start_date=getattr(config, 'START_DATE', None),
            end_date=getattr(config, 'END_DATE', None)
        )
        # Para multi-asset, usar balance unificado
        _set_table_balance(table, initial_balance)
    elif mode == "live_ccxt":
        print("🔄 Usando TableCCXTPro")
        # Configuración para live trading
        exchange_id = getattr(config, 'EXCHANGE', 'binance').lower()
        symbols = getattr(config, 'MULTI_ASSET_SYMBOLS', ['BTC/USDT'])
        table = TableCCXTPro(
            exchange_id=exchange_id,
            symbols=symbols,
            timeframe=getattr(config, 'TIMEFRAME', '1m'),
            testnet=getattr(config, 'TESTNET', True)
        )
        # Balance ya inicializado en TableCCXTPro
    else:
        print("🔄 Usando TableBacktest (single-asset)")
        table = TableBacktest(dataset_path)
        _set_table_balance(table, initial_balance)

    sensors = SensorManager()
    croupier = Croupier(table)

    # Inicializar Position Tracker
    position_tracker = PositionTracker(max_concurrent_positions=1)  # Una posición por vez

    player_state = player_module.init_state() if hasattr(player_module, "init_state") else None

    # Estadísticas
    candles = 0
    bet_trades = 0
    ghost_trades = 0
    skip_trades = 0
    wins = 0
    losses = 0
    total_fees = 0.0
    total_funding = 0.0
    total_liquidations = 0

    # Loop principal vela por vela
    while True:
        if hasattr(table, 'next_candle_batch'):
            # Modo multi-asset
            batch = table.next_candle_batch()
            if batch is None:
                break

            # Procesar batch multi-asset
            # Por ahora, procesamos solo el primer símbolo con datos
            current_candle = None
            current_symbol = None

            for symbol, timeframes in batch.items():
                for timeframe, candle in timeframes.items():
                    if candle is not None:
                        candles += 1
                        current_candle = candle
                        current_symbol = symbol
                        break
                if current_candle:
                    break

            if not current_candle:
                continue  # Continuar con el siguiente batch
        else:
            # Modo single-asset tradicional
            candle = table.next_candle()
            if candle is None:
                break

            candles += 1
            current_candle = candle
            current_symbol = candle.get('symbol', 'UNKNOWN')

        # 1. PRIMERO: Cerrar posiciones que tocaron TP/SL en esta vela
        closed_positions = position_tracker.check_and_close_positions(current_candle)

        # Procesar cierres de posiciones
        for closed_result in closed_positions:
            outcome = (closed_result.get("result") or "").upper()

            bet_trades += 1
            total_fees += float(closed_result.get("fee", 0.0) or 0.0)
            total_funding += float(closed_result.get("funding", 0.0) or 0.0)
            if closed_result.get("liquidated"):
                total_liquidations += 1
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1

            # Actualizar balance en la mesa
            pnl_net = float(closed_result.get("pnl", 0.0)) - float(closed_result.get("fee", 0.0))
            current_balance = _get_table_state(table).get("balance", initial_balance)
            new_balance = current_balance + pnl_net

            # Aplicar cambio de balance
            try:
                table.balance_manager.balance = new_balance
            except Exception:
                if hasattr(table.balance_manager, "set_balance"):
                    table.balance_manager.set_balance(new_balance)

            # Log del trade cerrado
            _log_trade("CLOSE", None, closed_result, closed_result, new_balance)

            # Actualizar memoria de Gemini
            if closed_result.get("trade_id"):
                gemini.on_trade_result(closed_result["trade_id"], closed_result)

            # Actualizar estado del player
            if player_state is not None and hasattr(player_module, "handle_trade_outcome") and outcome in {"WIN", "LOSS"}:
                player_state = player_module.handle_trade_outcome(player_state, "BET", closed_result)

        # 2. SEGUNDO: Intentar abrir nuevas posiciones si hay capital disponible

        # Obtener equity actual (después de posibles cierres)
        current_balance = _get_table_state(table).get("balance", initial_balance)
        available_equity = position_tracker.get_available_equity(current_balance)

        # Sensores detectan señales
        signals = sensors.process_candle(current_candle)
        if not signals:
            continue

        # Gemini valida oportunidad
        verdict = gemini.evaluate_signals_v2(signals, equity=available_equity)

        # Si no hay side, no se puede operar
        if not verdict.side:
            skip_trades += 1
            # Si hay trade_id registrado, finalizar como GHOST para entrenar
            if verdict.trade_id and verdict.reason == "conflicto_de_lado":
                ghost_order = gemini.make_order_from_verdict(verdict, size_fraction=0.0, ghost=True)
                ghost_order["symbol"] = current_candle.get("symbol", current_symbol)
                ghost_order["timestamp"] = current_candle.get("timestamp")
                ghost_order["timeframe"] = current_candle.get("timeframe", "multi")

                ghost_result = croupier.route_order(ghost_order)
                gemini.on_trade_result(verdict.trade_id, ghost_result)
                ghost_trades += 1
            continue

        # Preparar estado del player
        meta = None
        if player_state is not None and hasattr(player_module, "prepare_state"):
            player_state, meta = player_module.prepare_state(player_state, available_equity)

        # Player calcula tamaño de posición
        size_fraction = None
        if hasattr(player_module, "calculate_position_size"):
            size_fraction = player_module.calculate_position_size(verdict, available_equity, meta)

        if size_fraction and size_fraction > 0:
            action = "BET"
            ghost = False
        else:
            action = "GHOST"
            ghost = True
            size_fraction = 0.0

        # Crear orden
        order = gemini.make_order_from_verdict(verdict, size_fraction, ghost=ghost)
        if isinstance(meta, dict):
            unit_amount = meta.get("paroli_unit_amount")
            unit_multiplier = meta.get("paroli_multiplier")
            if unit_amount is not None:
                try:
                    order["unit_amount"] = float(unit_amount)
                except (TypeError, ValueError):
                    pass
            if unit_multiplier is not None:
                try:
                    order["unit_multiplier"] = float(unit_multiplier)
                except (TypeError, ValueError):
                    pass

        order.setdefault("symbol", current_symbol)
        order.setdefault("timestamp", current_candle.get("timestamp"))
        order.setdefault("timeframe", current_candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN")))

        if ghost:
            # Ejecutar GHOST trade inmediatamente (no afecta balance)
            ghost_result = croupier.route_order(order)
            ghost_trades += 1

            # Log del ghost trade
            _log_trade(action, verdict, order, ghost_result, current_balance)

            if verdict.trade_id:
                gemini.on_trade_result(verdict.trade_id, ghost_result)
        else:
            # Verificar si se puede abrir la posición
            margin_required = order.get("margin_used", 0.0)

            if position_tracker.can_open_position(margin_required, available_equity):
                # Calcular precio de entrada (close de vela actual)
                entry_price = float(current_candle.get("close", 0.0))

                # Abrir posición en el tracker
                position = position_tracker.open_position(order, entry_price, current_candle.get("timestamp", ""), available_equity)

                if position:
                    # Log de apertura
                    _log_trade("OPEN", verdict, order, {"result": "OPEN"}, current_balance)

                    # Aplicar fees de apertura al balance
                    entry_fee = float(order.get("fee", 0.0))
                    if entry_fee > 0:
                        try:
                            table.balance_manager.balance = current_balance - entry_fee
                            total_fees += entry_fee
                        except Exception:
                            pass
                else:
                    logger.warning("No se pudo abrir posición a pesar de validación")
            else:
                # No hay capital suficiente - log como skip
                skip_trades += 1
                logger.info(f"⏭️  SKIP | Capital insuficiente | Disponible: {available_equity:.2f} | Requerido: {margin_required:.2f}")

    # 3. Al final: Forzar cierre de posiciones abiertas
    if position_tracker.open_positions:
        logger.info(f"🔚 Cerrando {len(position_tracker.open_positions)} posiciones abiertas al final del backtest")
        final_candle = {
            "close": table.data[-1]["close"] if table.data else candle.get("close", 0),
            "timestamp": table.data[-1]["timestamp"] if table.data else candle.get("timestamp", ""),
            "market": table.market_id,
            "timeframe": table.timeframe
        }

        forced_closes = position_tracker.force_close_all_positions(final_candle)

        for closed_result in forced_closes:
            outcome = (closed_result.get("result") or "").upper()

            bet_trades += 1
            total_fees += float(closed_result.get("fee", 0.0) or 0.0)
            total_funding += float(closed_result.get("funding", 0.0) or 0.0)

            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1

            # Aplicar P&L final
            pnl_net = float(closed_result.get("pnl", 0.0)) - float(closed_result.get("fee", 0.0))
            current_balance = _get_table_state(table).get("balance", initial_balance)
            new_balance = current_balance + pnl_net

            try:
                table.balance_manager.balance = new_balance
            except Exception:
                if hasattr(table.balance_manager, "set_balance"):
                    table.balance_manager.set_balance(new_balance)

            _log_trade("FORCE_CLOSE", None, closed_result, closed_result, new_balance)

            if closed_result.get("trade_id"):
                gemini.on_trade_result(closed_result["trade_id"], closed_result)

    # Resumen final
    final_state = _get_table_state(table)
    final_balance = float(final_state.get("balance", initial_balance))
    winrate = (wins / bet_trades * 100) if bet_trades > 0 else 0.0

    # Log estadísticas del position tracker
    tracker_stats = position_tracker.get_stats()
    logger.info(f"📊 Position Tracker: {tracker_stats}")

    return {
        "dataset": dataset_name,
        "player": player_name,
        "initial_balance": initial_balance,
        "candles": candles,
        "bet_trades": bet_trades,
        "ghost_trades": ghost_trades,
        "skip_trades": skip_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "fees": total_fees,
        "funding": total_funding,
        "final_balance": final_balance,
        "liquidations": total_liquidations,
        "open_positions_final": tracker_stats["open_positions"],
        "blocked_capital_final": tracker_stats["blocked_capital"],
    }


def print_session_summary(stats: Dict) -> None:
    """Imprime resumen de la sesión"""
    print("\n" + "=" * 60)
    print(f"📌 Dataset: {stats['dataset']}")
    print(f"🎮 Player:  {stats['player'].upper()}")
    print("-" * 60)
    init_balance = stats.get("initial_balance")
    if isinstance(init_balance, (int, float)):
        init_str = f"{init_balance:.2f}"
    else:
        init_str = str(init_balance) if init_balance is not None else "n/a"
    print(f"   Balance inicial       : {init_str}")
    print(f"   Velas procesadas      : {stats['candles']}")
    print(f"   Trades BET            : {stats['bet_trades']}")
    print(f"   Trades GHOST          : {stats['ghost_trades']}")
    print(f"   Trades SKIP           : {stats.get('skip_trades', 0)}")
    print(f"   Wins / Losses         : {stats['wins']} / {stats['losses']}")
    print(f"   WinRate (BET)         : {stats['winrate']:.2f}%")
    print(f"   Comisiones totales    : {stats['fees']:.2f}")
    print(f"   Funding total         : {stats.get('funding', 0.0):.2f}")
    print(f"   Liquidaciones         : {stats.get('liquidations', 0)}")
    print(f"   Balance final         : {stats['final_balance']:.2f}")
    pnl = stats['final_balance'] - stats['initial_balance']
    pnl_pct = (pnl / stats['initial_balance'] * 100) if stats['initial_balance'] > 0 else 0.0
    print(f"   PnL Total             : {pnl:+.2f} ({pnl_pct:+.2f}%)")
    print("=" * 60 + "\n")


# ============================================================
# 🚀 ENTRYPOINT
# ============================================================
def main() -> None:
    """Main unificado: detecta MODE de config y ejecuta live o backtest"""
    mode = getattr(config, "MODE", "backtest").lower()

    player_name = DEFAULT_PLAYER
    multi_asset_config = None

    # Parsear argumentos de línea de comandos
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            arg = arg.lower()
            if arg.startswith("--player="):
                player_name = arg.replace("--player=", "")
            elif arg == "--multi-asset":
                mode = "multi_asset_backtest"
            elif arg == "--ccxt-live":
                mode = "live_ccxt"

    if player_name not in AVAILABLE_PLAYERS:
        print(f"⚠️ Player '{player_name}' no encontrado. Usando {DEFAULT_PLAYER}")
        print(f"Players disponibles: {', '.join(AVAILABLE_PLAYERS.keys())}")
        player_name = DEFAULT_PLAYER

    player_module = AVAILABLE_PLAYERS[player_name]

    # =====================================================
    # 🎯 DETECCIÓN AUTOMÁTICA DE MODO
    # =====================================================

    if mode == "live":
        print("\n🎰 Casino V2 — Live Trading (Testnet)\n")
        print(f"🎮 Player seleccionado: {player_name.upper()}")
        print(f"🏦 Exchange: {getattr(config, 'EXCHANGE', 'HYPERLIQUID')}")

        # Verificar credenciales antes de iniciar
        exchange = getattr(config, 'EXCHANGE', 'HYPERLIQUID')
        if exchange == 'HYPERLIQUID':
            from utils.hyperliquid_env_loader import validate_hyperliquid_config, load_hyperliquid_config
            if not validate_hyperliquid_config(load_hyperliquid_config()):
                print("❌ Credenciales de Hyperliquid no configuradas.")
                print("Configura HYPERLIQUID_API_KEY y HYPERLIQUID_API_SECRET en tu .env")
                return
        elif exchange == 'BINANCE_FUTURES_TESTNET':
            from utils.binance_env_loader import validate_binance_config, load_binance_config
            if not validate_binance_config(load_binance_config()):
                print("❌ Credenciales de Binance no configuradas.")
                print("Configura BINANCE_API_KEY y BINANCE_API_SECRET en tu .env")
                return
        elif exchange == 'KRAKEN_DEMO':
            from utils.kraken_env_loader import validate_kraken_config, load_kraken_config
            if not validate_kraken_config(load_kraken_config()):
                print("❌ Credenciales de Kraken no configuradas.")
                print("Configura KRAKEN_API_KEY y KRAKEN_API_SECRET en tu .env")
                return

        # Ejecutar live session integrada
        run_live_session(symbol=None, interval=None, player_module=player_module, player_name=player_name)
        return

    # =====================================================
    # 📊 MODO BACKTEST
    # =====================================================

    print("\n🎰 Casino V2 — Backtest Mode\n")

    # Configurar modo backtest
    if mode == "multi_asset_backtest":
        print("🔄 MODO: Multi-Asset Backtest")
        # Configuración multi-asset desde config
        multi_asset_config = getattr(config, "MULTI_ASSET_CONFIG", {
            'BTCUSDT': {'timeframes': ['5m', '15m'], 'data_path': ''},
            'ETHUSDT': {'timeframes': ['1m'], 'data_path': ''},
            'LTCUSDT': {'timeframes': ['1m'], 'data_path': ''}
        })
        dataset_path = "multi_asset"  # Placeholder
    elif mode == "live_ccxt":
        print("🔄 MODO: Live Trading con CCXT Pro")
        dataset_path = "live_ccxt"  # Placeholder
    else:
        print("🔄 MODO: Single-Asset Backtest")
        dataset_path = getattr(config, "DATASET_PATH", "tables/data/raw/BTCUSDT_1m__30d.csv")

    print(f"🎮 Player seleccionado: {player_name.upper()}")
    print(f"📁 Dataset: {dataset_path}")

    # Configuración de sesión
    initial_balance = ask_initial_balance()

    # Inicializar Gemini (validador)
    gemini = Gemini()

    print(f"\n🟢 Iniciando sesión: {mode}")

    # Ejecutar sesión con configuración apropiada
    stats = run_session_with_player(
        dataset_path,
        initial_balance,
        gemini,
        player_module,
        player_name,
        mode=mode,
        multi_asset_config=multi_asset_config
    )

    print_session_summary(stats)

    # Guardar memoria
    gemini.memory.save()
    print("💾 Memoria de Gemini guardada.")

    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    main()
