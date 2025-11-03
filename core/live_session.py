"""
Runtime loop for live or paper trading sessions (ASTERDEx compatible).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from croupier.broker_interface import BrokerInterface
from croupier.croupier import Croupier
from gemini.gemini_core import Gemini, Verdict
from sensors.sensor_manager import SensorManager

from . import config

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


def _normalize_symbol_for_exchange(symbol: str, exchange: str) -> str:
    """
    Normalize trading symbol based on exchange-specific requirements.

    Args:
        symbol: Raw symbol input from user
        exchange: Exchange name (KRAKEN, HYPERLIQUID, BINANCE, etc.)

    Returns:
        Normalized symbol for the specific exchange
    """
    if "KRAKEN" in exchange:
        # Kraken Futures uses SYMBOL/USD:USD format for perpetual futures
        symbol = symbol.upper()
        if not symbol.endswith(":USD"):
            if "/" in symbol:
                # Already has / separator, convert to :USD format
                base = symbol.split("/")[0]
                symbol = f"{base}/USD:USD"
            else:
                # No separator, assume base symbol and add /USD:USD
                symbol = f"{symbol}/USD:USD"
            RESULT_LOGGER.info("Símbolo normalizado para Kraken Futures: %s", symbol)
    elif "HYPERLIQUID" in exchange:
        # Hyperliquid usa formato BASE/USDC:USDC para perpetuos
        original_symbol = symbol

        # Si ya tiene el formato correcto, no hacer nada
        if "/" in symbol and ":" in symbol:
            pass  # Ya está en formato correcto
        else:
            # Extraer base symbol
            base = symbol
            if symbol.endswith("USDT"):
                base = symbol[:-4]
            elif symbol.endswith("USD"):
                base = symbol[:-3]
            elif symbol.endswith("BTC"):
                base = symbol[:-3]

            # Formato perpetuo de Hyperliquid
            symbol = f"{base}/USDC:USDC"

        if symbol != original_symbol:
            RESULT_LOGGER.info("Símbolo normalizado para Hyperliquid: %s → %s", original_symbol, symbol)
    elif "BINANCE" in exchange:
        # Binance typically uses SYMBOLUSDT format, ensure uppercase
        symbol = symbol.upper()
        if not symbol.endswith(("USDT", "BUSD", "USDC", "BTC", "ETH")):
            symbol = f"{symbol}USDT"
            RESULT_LOGGER.info("Símbolo normalizado para Binance: %s", symbol)

    return symbol


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
    currency = stats.get("currency", "USD?")
    print("\n" + "=" * 60)
    print("📊 Resumen sesión Live")
    print("-" * 60)
    print(f"   Exchange              : {stats.get('exchange', 'n/a')}")
    if stats.get("player"):
        print(f"   Player                : {stats.get('player')}")
    print(f"   Símbolo               : {stats.get('symbol', 'n/a')}")
    print(f"   Intervalo             : {stats.get('interval', 'n/a')}")
    print(f"   Moneda base           : {currency}")
    print(f"   Velas procesadas      : {stats.get('candles', 0)}")
    print(f"   Límite configurado    : {max_candles_str}")
    print(f"   Trades BET            : {stats.get('bet_trades', 0)}")
    print(f"   Trades GHOST          : {stats.get('ghost_trades', 0)}")
    if stats.get("skip_trades"):
        print(f"   Trades SKIP           : {stats.get('skip_trades', 0)}")
    print(f"   Wins / Losses (BET)   : {stats.get('wins', 0)} / {stats.get('losses', 0)}")
    print(f"   WinRate (BET)         : {winrate:.2f}%")
    print(f"   Comisiones totales    : {stats.get('fees', 0.0):.4f} {currency}")
    print(f"   Funding total         : {stats.get('funding', 0.0):.4f} {currency}")
    print(f"   Liquidaciones         : {stats.get('liquidations', 0)}")
    print(f"   Balance inicial       : {stats.get('initial_balance', 0.0):.2f} {currency}")
    print(f"   Equity inicial        : {stats.get('initial_equity', 0.0):.2f} {currency}")
    print(f"   Balance final         : {stats.get('final_balance', 0.0):.2f} {currency}")
    print(f"   Equity final          : {stats.get('final_equity', 0.0):.2f} {currency}")
    if stats.get("balance_source"):
        print(f"   Fuente balance        : {stats.get('balance_source')}")
    print(f"   Duración (min)        : {duration_minutes:.2f}")
    print(f"   Motivo de salida      : {stats.get('stop_reason', 'Finalizado')}")
    print("=" * 60 + "\n")


async def run_live_session(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    max_candles: Optional[int] = None,
    player_module=None,
    player_name: str = "paroli",
) -> Dict:
    """Ejecuta el loop live reutilizando BrokerInterface (exchange actual)."""
    logging.getLogger().setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    exchange = getattr(config, "EXCHANGE", "SIMULATION").upper()
    RESULT_LOGGER.info("Iniciando sesión live (exchange=%s)", exchange)

    if player_module is None:
        raise ValueError("Se requiere un player_module para ejecutar sesiones live.")

    if "KRAKEN" in exchange:
        default_symbol = getattr(config, "KRAKEN_FUTURES_SYMBOL", "PF_XBTUSD")
        default_interval = getattr(config, "KRAKEN_FUTURES_INTERVAL", "1m")
    elif "BINANCE" in exchange:
        default_symbol = getattr(config, "BINANCE_DEFAULT_SYMBOL", "BTCUSDT")
        default_interval = getattr(config, "BINANCE_DEFAULT_INTERVAL", "1m")
    elif "HYPERLIQUID" in exchange:
        default_symbol = getattr(config, "HYPERLIQUID_DEFAULT_SYMBOL", "BTC")
        default_interval = getattr(config, "HYPERLIQUID_DEFAULT_INTERVAL", "1m")
    else:
        default_symbol = getattr(config, "ASTER_DEFAULT_SYMBOL", "BTCUSDT")
        default_interval = getattr(config, "ASTER_DEFAULT_INTERVAL", "1m")

    # Override defaults based on exchange capabilities
    if "KRAKEN" in exchange and default_symbol == "PF_XBTUSD":
        # Kraken uses different symbol format
        pass
    elif "HYPERLIQUID" in exchange and default_symbol == "BTC":
        # Hyperliquid uses base symbol only
        pass

    # Interactive mode: ask for symbol and interval
    if not symbol:
        try:
            symbol_input = input(f"Símbolo a operar [{default_symbol}]: ").strip()
            symbol = symbol_input if symbol_input else default_symbol
        except EOFError:
            symbol = default_symbol
            RESULT_LOGGER.info("Usando símbolo por defecto: %s", symbol)

    if not interval:
        try:
            interval_input = input(f"Intervalo de tiempo [{default_interval}]: ").strip()
            interval = interval_input if interval_input else default_interval
        except EOFError:
            interval = default_interval
            RESULT_LOGGER.info("Usando intervalo por defecto: %s", interval)

    # Validate and normalize symbol based on exchange
    symbol = _normalize_symbol_for_exchange(symbol, exchange)

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

    # Configurar la mesa live
    table = broker.engine.table

    # Set margin type to ISOLATED for safety
    margin_type = getattr(config, "DEFAULT_MARGIN_TYPE", "ISOLATED").upper()
    if margin_type == "ISOLATED":
        RESULT_LOGGER.info("Attempting to set margin type to ISOLATED for %s...", symbol)
        broker.set_margin_type(symbol=symbol, margin_type=margin_type)
    actual_symbol = getattr(table, "symbol", symbol)
    if actual_symbol and actual_symbol != symbol:
        RESULT_LOGGER.info("Símbolo normalizado por la mesa: %s -> %s", symbol, actual_symbol)
        symbol = actual_symbol
    initial_state = _get_table_state(table)
    currency = initial_state.get("currency") or getattr(config, "ACCOUNT_CURRENCY", "USDT")
    balance_source = getattr(table, "balance_source", "table.get_state() / BalanceManager")
    default_balance = getattr(config, "STARTING_BALANCE", 0.0)
    initial_balance = _safe_float(initial_state.get("balance"), default_balance)
    initial_equity = _safe_float(initial_state.get("equity"), initial_balance)

    # Log additional info about balance source
    balance_source_info = ""
    if balance_source != "table.get_state() / BalanceManager":
        balance_source_info = f" | source={balance_source}"

    # En modo LIVE, intentar obtener balance real del exchange
    real_balance = None
    if hasattr(table, "exchange") and table.exchange:
        try:
            # Usar el método get_balance_sync de la mesa si existe
            # Esto evita problemas con event loops
            if hasattr(table, "get_balance_sync"):
                balance_data = table.get_balance_sync()
            else:
                # Fallback: usar asyncio de manera segura
                import asyncio

                try:
                    # Intentar obtener el loop actual
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si hay un loop corriendo, crear tarea
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

                            def get_balance():
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    return new_loop.run_until_complete(table.exchange.fetch_balance())
                                finally:
                                    new_loop.close()

                            future = executor.submit(get_balance)
                            balance_data = future.result(timeout=10)
                    else:
                        # No hay loop corriendo, usar directamente
                        balance_data = loop.run_until_complete(table.exchange.fetch_balance())
                except RuntimeError:
                    # No hay loop, crear uno nuevo
                    balance_data = asyncio.run(table.exchange.fetch_balance())

            RESULT_LOGGER.info("📊 Balance data type: %s", type(balance_data))
            RESULT_LOGGER.debug("Balance data completa: %s", balance_data)

            # Para Kraken, buscar USD o USDT
            for curr in ["USD", "USDT", "USDC"]:
                if curr in balance_data:
                    curr_data = balance_data[curr]
                    RESULT_LOGGER.debug(f"Datos de {curr}: {curr_data} (type: {type(curr_data)})")

                    # Verificar si es un dict con 'total'
                    if isinstance(curr_data, dict) and "total" in curr_data:
                        total = curr_data["total"]
                        if total and float(total) > 0:
                            real_balance = float(total)
                            currency = curr
                            RESULT_LOGGER.info("✅ Balance encontrado en %s: %.4f", currency, real_balance)
                            break

            # Si no hay balance en monedas específicas, buscar cualquier balance positivo
            if real_balance is None:
                RESULT_LOGGER.info("Buscando balance en otras monedas...")
                for curr, data in balance_data.items():
                    if curr in ["info", "free", "used", "total", "timestamp", "datetime"]:
                        continue  # Skip metadata fields

                    RESULT_LOGGER.debug(f"Revisando {curr}: {data} (type: {type(data)})")

                    if isinstance(data, dict):
                        total = data.get("total", 0)
                        if total and float(total) > 0:
                            real_balance = float(total)
                            currency = curr
                            RESULT_LOGGER.info("✅ Balance encontrado en %s: %.4f", currency, real_balance)
                            break

        except Exception as e:
            error_msg = str(e)
            RESULT_LOGGER.error(f"❌ Error obteniendo balance del exchange: {error_msg}")
            RESULT_LOGGER.error("Detalles del error:", exc_info=True)

            # CRÍTICO: En modo LIVE nunca usar balance simulado
            # Si no se puede obtener balance real, DETENER el sistema
            raise RuntimeError(
                f"❌ MODO LIVE: No se pudo obtener balance real del exchange.\n"
                f"Error: {error_msg}\n"
                f"El sistema NO puede continuar sin balance real.\n"
                f"Verifique:\n"
                f"  1. Credenciales correctas en .env\n"
                f"  2. Cuenta tiene fondos disponibles\n"
                f"  3. API keys tienen permisos de lectura de balance\n"
                f"  4. Exchange está accesible (no hay problemas de red/SSL)"
            )

    # En modo LIVE, requerir balance real - incluso para Kraken Demo
    if real_balance is not None and real_balance > 0:
        initial_balance = real_balance
        initial_equity = real_balance
        balance_source = "Exchange API (real)"
        RESULT_LOGGER.info("✅ Balance real obtenido del exchange: %.4f %s", real_balance, currency)
    else:
        # En modo LIVE, no podemos continuar sin balance real - ni siquiera para Kraken Demo
        RESULT_LOGGER.error("❌ Balance obtenido del exchange: %s", real_balance)
        RESULT_LOGGER.error("Credenciales válidas pero sin balance en la cuenta")
        raise RuntimeError(
            "❌ MODO LIVE requiere balance real del exchange. "
            "Verifique que su cuenta tenga fondos disponibles. "
            f"Balance obtenido: {real_balance}. "
            "Para Kraken Demo, asegúrese de tener fondos en su cuenta demo."
        )

    RESULT_LOGGER.info(
        "Mesa live lista | symbol=%s | interval=%s | balance=%.4f | equity=%.4f | source=%s",
        symbol,
        interval,
        initial_balance,
        initial_equity,
        balance_source,
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
        "skip_trades": 0,
        "player": player_name or "legacy",
        "final_balance": initial_balance,
        "final_equity": initial_equity,
        "currency": currency,
        "balance_source": balance_source,
    }
    stop_reason = "Sesión finalizada correctamente."
    import time as time_module

    start_time = time_module.time()
    RESULT_LOGGER.info("✅ Sesión live inicializada correctamente")

    def limit_reached() -> bool:
        return max_candles is not None and stats["candles"] >= max_candles

    def register_limit_exit() -> None:
        nonlocal stop_reason
        stop_reason = f"Límite de {max_candles} velas alcanzado."
        RESULT_LOGGER.info("Límite de velas alcanzado (%s). Finalizando sesión...", max_candles)

    player_state = None
    if hasattr(player_module, "init_state"):
        player_state = player_module.init_state()

    def handle_completed_trade(trade: Dict[str, Any]) -> None:
        nonlocal player_state
        if not isinstance(trade, dict):
            return

        outcome = (trade.get("result") or "").upper()
        ghost_trade = bool(trade.get("ghost", False))
        if outcome in {"WIN", "LOSS"}:
            if not ghost_trade:
                if outcome == "WIN":
                    stats["wins"] += 1
                else:
                    stats["losses"] += 1
                stats["fees"] += _safe_float(trade.get("fee"))
                stats["funding"] += _safe_float(trade.get("funding"))
                if trade.get("liquidated"):
                    stats["liquidations"] += 1
            new_balance = trade.get("balance")
            if new_balance is not None:
                stats["final_balance"] = _safe_float(new_balance, stats["final_balance"])
                stats["final_equity"] = stats["final_balance"]
            trade_id = trade.get("trade_id")
            if trade_id:
                try:
                    gemini.on_trade_result(trade_id, trade)
                except Exception as exc:  # pragma: no cover - defensivo
                    RESULT_LOGGER.exception("Error actualizando memoria Gemini (%s): %s", trade_id, exc)

            if player_state is not None and hasattr(player_module, "handle_trade_outcome"):
                action_for_player = "GHOST" if ghost_trade else "BET"
                previous_state = player_state
                updated_state = player_module.handle_trade_outcome(player_state, action_for_player, trade)

                if (
                    action_for_player == "BET"
                    and getattr(player_module, "PROGRESSION", None)
                    and isinstance(previous_state, dict)
                ):
                    progression = tuple(getattr(player_module, "PROGRESSION", ()) or ())
                    if progression:
                        prev_step = int(previous_state.get("step", 0))
                        prev_unit = float(previous_state.get("unit") or 0.0)
                        result_label = outcome
                        multiplier_used = progression[min(prev_step, len(progression) - 1)]

                        if result_label == "WIN":
                            if prev_step >= len(progression) - 1:
                                RESULT_LOGGER.info(
                                    "Paroli | WIN completó ciclo (%s pasos) | mult=%s | unidad=%.4f %s",
                                    len(progression),
                                    multiplier_used,
                                    prev_unit,
                                    currency,
                                )
                            else:
                                next_step = int(updated_state.get("step", prev_step + 1))
                                next_multiplier = progression[min(next_step, len(progression) - 1)]
                                next_unit = float(updated_state.get("unit") or prev_unit)
                                RESULT_LOGGER.info(
                                    "Paroli | WIN avanza a paso %s/%s | mult actual=%s → próximo=%s | unidad %.4f→%.4f %s",
                                    prev_step + 2,
                                    len(progression),
                                    multiplier_used,
                                    next_multiplier,
                                    prev_unit,
                                    next_unit,
                                    currency,
                                )
                        elif result_label == "LOSS":
                            RESULT_LOGGER.info(
                                "Paroli | LOSS reinicia ciclo | perdió en paso %s/%s con mult=%s | unidad previa=%.4f %s",
                                prev_step + 1,
                                len(progression),
                                multiplier_used,
                                prev_unit,
                                currency,
                            )
                        else:
                            RESULT_LOGGER.info(
                                "Paroli | Resultado %s | paso %s/%s | mult=%s | unidad=%.4f %s",
                                result_label,
                                prev_step + 1,
                                len(progression),
                                multiplier_used,
                                prev_unit,
                                currency,
                            )

                player_state = updated_state

    def consume_completed_trades_from_table() -> None:
        consumer = getattr(table, "consume_completed_trades", None)
        if callable(consumer):
            for completed_trade in consumer():
                handle_completed_trade(completed_trade)

    # Crear event loop persistente para el listener
    import asyncio

    # Variable para almacenar el listener task
    listener_task = None

    # Conectar la mesa (async)
    if hasattr(table, "connect"):
        await table.connect()
        RESULT_LOGGER.info("✅ Mesa live conectada")

    # Iniciar listener task en background
    if hasattr(table, "start_listening"):
        import asyncio

        listener_task = asyncio.create_task(table.start_listening())
        RESULT_LOGGER.info("✅ Listener task iniciado")

        # Esperar un poco para que el listener se inicie
        await asyncio.sleep(2)
        RESULT_LOGGER.info("✅ Listener async iniciado y esperando datos...")

    # Tracking de velas procesadas para evitar duplicados
    # Estructura: {symbol: last_timestamp} para soportar multi-asset en v1.8
    processed_candles = {}

    try:
        while True:
            consume_completed_trades_from_table()

            candle = table.next_candle()
            if candle is None:
                # Solo log cada 10 segundos para no spam
                current_time = int(asyncio.get_event_loop().time())
                if current_time % 10 == 0:
                    RESULT_LOGGER.info("⏳ Esperando nueva vela... (sin datos disponibles)")
                await asyncio.sleep(LIVE_SLEEP_SECONDS)
                continue

            # Validar que sea una vela NUEVA (no procesada antes)
            candle_symbol = candle.get("symbol", symbol)
            candle_timestamp = candle.get("timestamp")

            # Si ya procesamos esta vela, esperar a la siguiente
            if candle_symbol in processed_candles:
                if processed_candles[candle_symbol] == candle_timestamp:
                    # Misma vela, no procesar de nuevo
                    await asyncio.sleep(LIVE_SLEEP_SECONDS)
                    continue

            # Vela nueva detectada - registrar y procesar
            processed_candles[candle_symbol] = candle_timestamp
            stats["candles"] += 1
            RESULT_LOGGER.info(
                "📊 Vela #%d procesada | timestamp=%s | price=%.2f",
                stats["candles"],
                candle_timestamp,
                candle.get("close", 0),
            )

            # 1. PRIMERO: Verificar si posiciones abiertas tocaron TP/SL en esta vela
            if hasattr(table, "position_tracker") and hasattr(table.position_tracker, "check_and_close_positions"):
                RESULT_LOGGER.debug(
                    f"🔍 Verificando TP/SL para vela: high={candle.get('high')}, low={candle.get('low')}"
                )
                closed_positions = table.position_tracker.check_and_close_positions(candle)
                RESULT_LOGGER.debug(f"🔍 Posiciones cerradas en esta vela: {len(closed_positions)}")

                for closed_result in closed_positions:
                    outcome = (closed_result.get("result") or "").upper()

                    # Log del cierre (el contador se actualiza en handle_completed_trade)
                    if outcome == "WIN":
                        RESULT_LOGGER.info("✅ Posición cerrada: WIN | PnL: %.2f", closed_result.get("pnl", 0.0))
                    elif outcome == "LOSS":
                        RESULT_LOGGER.info("❌ Posición cerrada: LOSS | PnL: %.2f", closed_result.get("pnl", 0.0))

                    # Procesar resultado (esto actualiza stats["wins"]/stats["losses"])
                    handle_completed_trade(closed_result)

                    # Actualizar memoria de Gemini
                    if closed_result.get("trade_id"):
                        gemini.on_trade_result(closed_result["trade_id"], closed_result)

            # 2. SEGUNDO: Verificar si hay posición abierta (después de cerrar las que tocaron TP/SL)
            if getattr(table, "position_manager", None) and table.position_manager.is_position_open():
                RESULT_LOGGER.debug("Posición abierta aún en curso; esperando cierre antes de nuevas entradas.")
                stats["skip_trades"] += 1
                if limit_reached():
                    register_limit_exit()
                    break
                await asyncio.sleep(LIVE_SLEEP_SECONDS)
                continue

            signals = sensors.process_candle(candle)
            if not signals:
                RESULT_LOGGER.debug("No se encontraron señales para esta vela")
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            RESULT_LOGGER.info("🎯 Señales encontradas: %d", len(signals))

            equity = candle.get("equity")
            if equity is None:
                state = _get_table_state(table)
                equity = state.get("equity")

            verdict: Verdict = gemini.evaluate_signals_v2(signals, equity=equity or 0.0)
            if not verdict.side:
                RESULT_LOGGER.debug("Gemini rechazó las señales: %s", verdict.reason)
                stats["skip_trades"] += 1
                if verdict.trade_id and verdict.reason == "conflicto_de_lado":
                    ghost_order = gemini.make_order_from_verdict(verdict, size_fraction=0.0, ghost=True)
                    ghost_order.setdefault(
                        "symbol", candle.get("symbol", table.symbols[0] if table.symbols else symbol)
                    )
                    ghost_order.setdefault("timestamp", candle.get("timestamp"))
                    ghost_order.setdefault("timeframe", candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN")))
                    try:
                        # Llamar directamente a execute_order (async) para órdenes GHOST
                        if hasattr(table, "execute_order") and asyncio.iscoroutinefunction(table.execute_order):
                            ghost_result = await table.execute_order(ghost_order)
                        else:
                            ghost_result = croupier.route_order(ghost_order)
                        if verdict.trade_id:
                            gemini.on_trade_result(verdict.trade_id, ghost_result)
                    except Exception as exc:  # pragma: no cover - defensivo
                        RESULT_LOGGER.exception("Fallo en orden GHOST por conflicto de lado: %s", exc)
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            RESULT_LOGGER.info("✅ Gemini aprobó trade: %s %s", verdict.side, verdict.reason)

            meta = None
            if player_state is not None and hasattr(player_module, "prepare_state"):
                RESULT_LOGGER.debug(f"🔍 Antes prepare_state: player_state={player_state}, equity={equity}")
                player_state, meta = player_module.prepare_state(player_state, equity)
                RESULT_LOGGER.debug(f"🔍 Después prepare_state: player_state={player_state}, meta={meta}")

            table_meta = {
                "min_qty": getattr(table, "min_qty", None),
                "step_size": getattr(table, "step_size", None),
                "price": candle.get("close"),
                "symbol": candle.get("symbol", table.symbols[0] if table.symbols else symbol),
                "max_position_fraction": getattr(config, "MAX_POSITION_SIZE", 0.0),
            }

            if meta is None:
                meta = {}
            meta.setdefault("table", {})
            meta["table"].update({k: v for k, v in table_meta.items() if v is not None})

            size_fraction = None
            if hasattr(player_module, "calculate_position_size"):
                RESULT_LOGGER.debug(
                    f"🔍 Calculando size: equity={equity}, meta keys={list(meta.keys()) if meta else None}"
                )
                size_fraction = player_module.calculate_position_size(verdict, equity, meta)
                RESULT_LOGGER.info(f"💰 Player calculó size_fraction={size_fraction}")

            if size_fraction and size_fraction > 0:
                action_label = "BET"
                ghost_flag = False
            else:
                action_label = "GHOST"
                ghost_flag = True
                size_fraction = 0.0

            order = gemini.make_order_from_verdict(verdict, size_fraction, ghost=ghost_flag)
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
            order.setdefault("symbol", candle.get("symbol", table.symbols[0] if table.symbols else symbol))
            order.setdefault("timestamp", candle.get("timestamp"))
            order.setdefault("timeframe", candle.get("timeframe", getattr(table, "timeframe", "UNKNOWN")))
            trade_id = verdict.trade_id

            try:
                # Llamar directamente a execute_order (async) en lugar de pasar por Croupier
                if hasattr(table, "execute_order") and asyncio.iscoroutinefunction(table.execute_order):
                    result = await table.execute_order(order)
                else:
                    # Fallback a Croupier para mesas síncronas
                    result = croupier.route_order(order)
            except Exception as exc:  # pragma: no cover - defensivo
                RESULT_LOGGER.exception("Fallo al enrutar orden live: %s", exc)
                await asyncio.sleep(LIVE_SLEEP_SECONDS)
                if limit_reached():
                    register_limit_exit()
                    break
                continue

            actual_size_fraction = result.get("size_fraction")
            if actual_size_fraction is not None:
                order["size"] = actual_size_fraction

            executed_qty = result.get("executed_qty")
            entry_price = result.get("entry_price")
            if executed_qty is not None and entry_price is not None:
                try:
                    notional_amount = float(executed_qty) * float(entry_price)
                except (TypeError, ValueError):
                    notional_amount = 0.0
            elif result.get("notional") is not None:
                try:
                    notional_amount = float(result.get("notional", 0.0))
                except (TypeError, ValueError):
                    notional_amount = 0.0
            else:
                equity_reference = equity if equity else 0.0
                notional_amount = float(order.get("size", 0.0)) * equity_reference

            unit_multiplier_value = order.get("unit_multiplier")
            try:
                unit_multiplier_value = float(unit_multiplier_value)
            except (TypeError, ValueError):
                unit_multiplier_value = None
            if unit_multiplier_value is None or unit_multiplier_value <= 0:
                unit_multiplier_value = 1.0

            unit_amount_value = order.get("unit_amount")
            try:
                unit_amount_value = float(unit_amount_value)
            except (TypeError, ValueError):
                unit_amount_value = None
            if unit_amount_value is None or unit_amount_value <= 0:
                unit_amount_value = (
                    notional_amount / unit_multiplier_value if unit_multiplier_value > 0 else notional_amount
                )

            unit_count_display = (
                int(unit_multiplier_value)
                if abs(unit_multiplier_value - round(unit_multiplier_value)) < 1e-6
                else unit_multiplier_value
            )

            try:
                notional_display = float(notional_amount)
            except (TypeError, ValueError):
                notional_display = 0.0

            RESULT_LOGGER.info(
                "🎰 LIVE TRADE | %s %s | action=%s | result=%s | Unidad=%su(%.2f %s)",
                order.get("symbol"),
                order.get("side"),
                action_label,
                result.get("result"),
                unit_count_display,
                notional_display,
                currency,
            )
            updated_state = _get_table_state(table)
            RESULT_LOGGER.debug(
                "state_update | balance=%.4f | equity=%.4f",
                float(updated_state.get("balance", 0.0)),
                float(updated_state.get("equity", updated_state.get("balance", 0.0))),
            )

            status = (result.get("status") or "").upper()
            outcome = (result.get("result") or "").upper()

            if action_label == "BET":
                if outcome in {"WIN", "LOSS"}:
                    stats["bet_trades"] += 1
                    handle_completed_trade(result)
                elif status == "OPENED" or outcome == "OPENED":
                    stats["bet_trades"] += 1
                    # Registrar posición abierta en el tracker para poder cerrarla con TP/SL
                    if hasattr(table, "position_tracker") and hasattr(table.position_tracker, "open_position"):
                        entry_price = float(candle.get("close", 0.0))
                        current_equity = _safe_float(updated_state.get("equity"), equity or 0.0)
                        table.position_tracker.open_position(
                            order, entry_price, candle.get("timestamp", ""), current_equity
                        )
                        RESULT_LOGGER.debug(f"📍 Posición registrada en tracker: {order.get('side')} @ {entry_price}")
                elif outcome == "EXECUTED" or status == "CLOSED":
                    # Trade ejecutado exitosamente (posición abierta o cerrada inmediatamente)
                    stats["bet_trades"] += 1
                    # Registrar posición abierta en el tracker para poder cerrarla con TP/SL
                    if hasattr(table, "position_tracker") and hasattr(table.position_tracker, "open_position"):
                        entry_price = float(result.get("entry_price") or candle.get("close", 0.0))
                        current_equity = _safe_float(updated_state.get("equity"), equity or 0.0)
                        table.position_tracker.open_position(
                            order, entry_price, candle.get("timestamp", ""), current_equity
                        )
                        RESULT_LOGGER.debug(f"📍 Posición registrada en tracker: {order.get('side')} @ {entry_price}")
                elif status == "SKIPPED":
                    stats["skip_trades"] += 1
            elif action_label == "GHOST":
                stats["ghost_trades"] += 1
                if outcome in {"WIN", "LOSS"}:
                    handle_completed_trade(result)

            if limit_reached():
                register_limit_exit()
                break

            await asyncio.sleep(LIVE_SLEEP_SECONDS)
            consume_completed_trades_from_table()
    except KeyboardInterrupt:
        stop_reason = "Sesión finalizada manualmente (Ctrl+C)."
        RESULT_LOGGER.info("Sesión live finalizada por el usuario.")
    finally:
        # Cancelar el listener task si existe
        if listener_task and not listener_task.done():
            listener_task.cancel()
            RESULT_LOGGER.info("Listener task cancelado")

        # Listener task ya fue cancelado arriba si existía

        consume_completed_trades_from_table()

        # Cerrar todas las posiciones abiertas ANTES de desconectar
        try:
            if hasattr(table, "close_all_positions"):
                RESULT_LOGGER.info("🔒 Cerrando posiciones abiertas...")
                await table.close_all_positions()
                RESULT_LOGGER.info("✅ Posiciones cerradas correctamente")
        except Exception as e:
            RESULT_LOGGER.error(f"❌ Error cerrando posiciones: {e}")

        # Desconectar el broker para limpiar tareas async y cerrar conexiones
        try:
            if hasattr(broker, "disconnect"):
                await broker.disconnect()
                RESULT_LOGGER.info("Broker desconectado correctamente")

            # Cerrar conexión del exchange si existe
            if hasattr(table, "disconnect"):
                await table.disconnect()
                RESULT_LOGGER.info("Mesa desconectada correctamente")
        except Exception as e:
            RESULT_LOGGER.warning(f"Error desconectando: {e}")

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
