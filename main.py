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

PUNTOS DE EXTENSIÓN:
--------------------
• Reemplazar TableBacktest por TableRealtime cuando MODE="live".
• Añadir nuevas mesas en tables/ y nuevos croupiers en croupier/.
• Ajustar sensores en sensors/ (más estrategias de reversión).
"""

import logging
from datetime import datetime

import config
from sensors.sensor_manager import SensorManager
from gemini.gemini_core import Gemini
from croupier.croupier import Croupier
from croupier.broker_interface import BrokerInterface  # interfaz que entrega .engine.table
# ^ Si tu BrokerInterface aún no existe o tiene firma distinta, ajusta la sección SETUP_MESA abajo.


# =========================================================
# 🪙 LOGGING
# =========================================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)


# =========================================================
# 🧰 Helpers
# =========================================================
def ask_initial_balance() -> float:
    """Pide balance inicial por consola, con fallback a config.STARTING_BALANCE."""
    try:
        raw = input("💰 Ingrese balance inicial (ej. 10000): ").strip()
        if not raw:
            raise ValueError
        val = float(raw.replace(",", ""))
        if val <= 0:
            raise ValueError
        return val
    except Exception:
        print(f"⚠️ Valor inválido. Usando STARTING_BALANCE de config: {config.STARTING_BALANCE:.2f}")
        return float(config.STARTING_BALANCE)


def set_table_balance(table, amount: float) -> None:
    """
    Intenta setear el balance inicial de la mesa activa.
    Compatible con implementaciones que expongan distintos métodos.
    """
    bm = getattr(table, "balance_manager", None)
    if bm is None:
        return
    # PUNTOS DE EXTENSIÓN: ajusta a tu API real si difiere
    if hasattr(bm, "reset"):
        bm.reset(amount)
    elif hasattr(bm, "set_balance"):
        bm.set_balance(amount)
    else:
        try:
            bm.balance = amount  # fallback
        except Exception:
            pass


def get_table_state(table) -> dict:
    """
    Devuelve estado de balance/equity de la mesa, si está disponible.
    """
    bm = getattr(table, "balance_manager", None)
    if bm and hasattr(bm, "get_state"):
        try:
            return bm.get_state()
        except Exception:
            return {}
    return {}


def print_session_summary(title: str, stats: dict):
    print("\n" + "=" * 60)
    print(f"📊 Resumen de sesión: {title}")
    print("-" * 60)
    print(f"   Trades BET reales      : {stats.get('bet_trades', 0)}")
    print(f"   Trades GHOST (entreno) : {stats.get('ghost_trades', 0)}")
    print(f"   Wins (BET)             : {stats.get('wins', 0)}")
    print(f"   Losses (BET)           : {stats.get('losses', 0)}")
    wr = stats.get("winrate", 0.0)
    print(f"   WinRate (BET)          : {wr:.2f}%")
    print(f"   Balance final          : {stats.get('final_balance', 0):.2f}")
    print("=" * 60 + "\n")


# =========================================================
# 🎛️ SESIÓN DE CASINO SOBRE UNA MESA
# =========================================================
def run_session(dataset_path: str, initial_balance: float, gemini: Gemini) -> dict:
    """
    Ejecuta una sesión completa sobre un dataset (mesa única).
    Devuelve un dict con métricas de la sesión.

    dataset_path: ruta al CSV (ej: tables/data/raw/LTCUSDT_15min_bull.csv)
    initial_balance: balance con el que arranca esta mesa
    gemini: instancia compartida (memoria persiste entre mesas)
    """
    logger = logging.getLogger("Session")

    # 1) Crear mesa (feed) a través del Broker
    #    BrokerInterface debe proveer .engine.table con:
    #    - .next_candle() -> dict | None
    #    - .execute_order(order: dict, ghost: bool) -> dict (resultado normalizado)
    #    - .balance_manager con get_state() y set/reset de balance
    broker = BrokerInterface(csv_path=dataset_path)  # 🔧 Ajusta si tu firma difiere
    table = broker.engine.table
    set_table_balance(table, initial_balance)

    # 2) Croupier y Sensores
    croupier = Croupier(table)
    sensors = SensorManager()

    # 3) Métricas
    bet_trades = 0
    ghost_trades = 0
    wins = 0
    losses = 0

    # 4) Loop principal por velas
    while True:
        candle = table.next_candle()
        if candle is None:
            break

        # Sensores generan señales de oportunidad
        signals = sensors.process_candle(candle)
        if not signals:
            continue

        # Equity/Balance actual (para logs o decisiones si fuese necesario)
        equity = get_table_state(table).get("equity", None)
        # Decisión de Gemini (BET/GHOST/SKIP) para UNA apuesta por vela
        decision = gemini.evaluate_signals(signals, equity)

        if decision.action == "SKIP":
            continue

        # 🚩 Orden al Croupier: el Croupier siempre "opera" contra la mesa
        #    Para GHOST marcamos flag dentro de la orden, la mesa debe tratarlo como shadow trade
        order = decision.order or {}
        order["trade_id"] = decision.trade_id
        order["ghost"] = (decision.action == "GHOST")

        result = croupier.route_order(order)  # la mesa ejecuta (real o ghost según flag)

        # Reportar a Gemini el resultado normalizado
        gemini.on_trade_result(decision.trade_id, result)

        # Métricas
        if decision.action == "BET":
            bet_trades += 1
            outcome = (result.get("result", "").upper())
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
        elif decision.action == "GHOST":
            ghost_trades += 1

        # Log consolidado por vela con estado de balance
        state = get_table_state(table)
        balance = state.get("balance", None)
        logger.info(
            f"🎲 {decision.action} | {order.get('symbol','?')} {order.get('side','?')} "
            f"| size={order.get('size',0):.4f} | outcome={result.get('result','?')} "
            f"| balance={balance if balance is not None else 'n/a'}"
        )

    # Cierre de sesión: compilar métricas
    state = get_table_state(table)
    final_balance = state.get("balance", initial_balance)
    wr = (wins / bet_trades * 100) if bet_trades > 0 else 0.0

    return {
        "bet_trades": bet_trades,
        "ghost_trades": ghost_trades,
        "wins": wins,
        "losses": losses,
        "winrate": wr,
        "final_balance": final_balance
    }


# =========================================================
# 🚀 ENTRYPOINT
# =========================================================
def main():
    print("\n🎰 Bienvenido al Casino V2 — Sesión Backtest secuencial (Bull → Bear)\n")

    # 1) Pedir balance inicial por consola
    initial_balance = ask_initial_balance()

    # 2) Preparar datasets en secuencia
    bull_csv = "tables/data/raw/LTCUSDT_15min_bull.csv"
    bear_csv = "tables/data/raw/LTCUSDT_15min_bear.csv"

    # 3) Crear una instancia de Gemini compartida (memoria persiste entre mesas)
    gemini = Gemini()

    # 4) Ejecutar primera mesa (Bull)
    print("\n🟢 Mesa 1: Bull")
    stats_bull = run_session(bull_csv, initial_balance, gemini)
    print_session_summary("Bull", stats_bull)

    # 5) Ejecutar segunda mesa (Bear) — arranca con balance resultante de la mesa anterior
    print("\n🔴 Mesa 2: Bear")
    # Nota: usamos el balance final de la anterior como inicial aquí:
    stats_bear = run_session(bear_csv, stats_bull["final_balance"], gemini)
    print_session_summary("Bear", stats_bear)

    # 6) Resumen global
    total_bet = stats_bull["bet_trades"] + stats_bear["bet_trades"]
    total_wins = stats_bull["wins"] + stats_bear["wins"]
    total_losses = stats_bull["losses"] + stats_bear["losses"]
    total_ghost = stats_bull["ghost_trades"] + stats_bear["ghost_trades"]
    final_balance = stats_bear["final_balance"]

    wr_global = (total_wins / total_bet * 100) if total_bet > 0 else 0.0

    print("\n" + "#" * 60)
    print("🏁 RESUMEN GLOBAL (Bull → Bear)")
    print("#" * 60)
    print(f"   Trades BET totales     : {total_bet}")
    print(f"   Wins totales (BET)     : {total_wins}")
    print(f"   Losses totales (BET)   : {total_losses}")
    print(f"   WinRate global (BET)   : {wr_global:.2f}%")
    print(f"   Trades GHOST totales   : {total_ghost}")
    print(f"   Balance final global   : {final_balance:.2f}")
    print("#" * 60 + "\n")

    print("✅ Sesión completada.\n")


if __name__ == "__main__":
    # Validación de modo (por ahora, este main está centrado en backtest)
    if getattr(config, "MODE", "backtest").lower() != "backtest":
        print("⚠️ MODE no es 'backtest'. Este main está pensado para backtest. Ajusta según tu flujo live.")
    main()

