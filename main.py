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
from players import kelly_player, fixed_player

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
}

# Player por defecto (Kelly conservador)
DEFAULT_PLAYER = "kelly"


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
    logger.info(
        "🎲 %s | %s %s | size=%.4f | outcome=%s | exit=%s | bars=%s | pnl_pct=%.4f | balance=%s",
        action,
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
# 🎛️ SESIÓN INDIVIDUAL CON PLAYER
# ============================================================
def run_session_with_player(
    dataset_path: str,
    initial_balance: float,
    gemini: Gemini,
    player_module,
    player_name: str
) -> Dict:
    """
    Ejecuta una sesión de backtest usando la arquitectura Gemini + Player.
    
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

    table = TableBacktest(dataset_path)
    _set_table_balance(table, initial_balance)

    sensors = SensorManager()
    croupier = Croupier(table)

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
        candle = table.next_candle()
        if candle is None:
            break

        candles += 1
        
        # 1. Sensores detectan señales
        signals = sensors.process_candle(candle)
        if not signals:
            continue

        # 2. Obtener equity actual
        equity = candle.get("equity")
        if equity is None:
            equity = _get_table_state(table).get("equity", initial_balance)

        # 3. Gemini valida oportunidad (NUEVO: retorna Verdict)
        verdict = gemini.evaluate_signals_v2(signals, equity=equity)
        
        # Si no hay side, no se puede operar
        if not verdict.side:
            skip_trades += 1
            # Si hay trade_id registrado, finalizar como GHOST para entrenar
            if verdict.trade_id and verdict.reason == "conflicto_de_lado":
                # Simular resultado para entrenar (usamos WIN/LOSS aleatorio basado en cierre)
                ghost_order = gemini.make_order_from_verdict(verdict, size_fraction=0.0, ghost=True)
                ghost_order["symbol"] = candle.get("symbol", table.symbol)
                ghost_order["timestamp"] = candle.get("timestamp")
                ghost_order["timeframe"] = candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN"))
                
                ghost_result = croupier.route_order(ghost_order)
                gemini.on_trade_result(verdict.trade_id, ghost_result)
                ghost_trades += 1
            continue

        # 4. Player decide tamaño (NUEVO: separado de validación)
        size_fraction = player_module.calculate_position_size(verdict, equity)
        
        # 5. Decidir acción: BET o GHOST
        if size_fraction and size_fraction > 0:
            # BET: Apuesta real
            action = "BET"
            ghost = False
        else:
            # GHOST: Shadow trading para entrenar sin riesgo
            action = "GHOST"
            ghost = True
            size_fraction = 0.0  # Tamaño 0 para GHOST
        
        # 6. Construir orden (NUEVO: desde Verdict + size)
        order = gemini.make_order_from_verdict(verdict, size_fraction, ghost=ghost)
        
        # Asegurar campos adicionales del candle
        order.setdefault("symbol", candle.get("symbol", table.symbol))
        order.setdefault("timestamp", candle.get("timestamp"))
        order.setdefault("timeframe", candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN")))
        
        # 7. Ejecutar con Croupier (igual que antes)
        result = croupier.route_order(order)
        
        # 8. Actualizar memoria de Gemini (igual que antes)
        if verdict.trade_id:
            gemini.on_trade_result(verdict.trade_id, result)
        
        # 9. Contabilizar estadísticas
        outcome = result.get("result", "").upper()
        if action == "BET":
            bet_trades += 1
            total_fees += float(result.get("fee", 0.0) or 0.0)
            total_funding += float(result.get("funding", 0.0) or 0.0)
            if result.get("liquidated"):
                total_liquidations += 1
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
        elif action == "GHOST":
            ghost_trades += 1
        
        # 10. Log del trade
        balance = _get_table_state(table).get("balance")
        _log_trade(action, verdict, order, result, balance)

    # Resumen final
    final_state = _get_table_state(table)
    final_balance = float(final_state.get("balance", initial_balance))
    winrate = (wins / bet_trades * 100) if bet_trades > 0 else 0.0

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
    """Main con soporte para múltiples players"""
    mode = getattr(config, "MODE", "backtest").lower()

    if mode == "live":
        logger.warning("Modo LIVE aún no soporta arquitectura Player. Usando main.py...")
        run_live_session(symbol=None, interval=None)
        return

    print("\n🎰 Bienvenido al Casino V2 — Arquitectura Gemini + Player\n")

    # Seleccionar player desde argumentos o usar default
    player_name = DEFAULT_PLAYER
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().replace("--player=", "")
        if arg in AVAILABLE_PLAYERS:
            player_name = arg
        else:
            print(f"⚠️ Player '{arg}' no encontrado. Usando {DEFAULT_PLAYER}")
            print(f"Players disponibles: {', '.join(AVAILABLE_PLAYERS.keys())}")
    
    player_module = AVAILABLE_PLAYERS[player_name]
    print(f"🎮 Player seleccionado: {player_name.upper()}")

    # Configuración de sesión
    initial_balance = ask_initial_balance()
    dataset_path = getattr(config, "DATASET_PATH", "tables/data/raw/BTCUSDT_5m__30d.csv")

    # Inicializar Gemini (validador)
    gemini = Gemini()

    print(f"\n🟢 Iniciando sesión de backtest: {dataset_path}")
    
    # Ejecutar sesión con player seleccionado
    stats = run_session_with_player(
        dataset_path,
        initial_balance,
        gemini,
        player_module,
        player_name
    )
    
    print_session_summary(stats)

    # Guardar memoria
    gemini.memory.save()
    print("💾 Memoria de Gemini guardada.")
    
    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    main()
