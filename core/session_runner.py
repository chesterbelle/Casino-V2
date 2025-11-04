"""
Session runner for Casino V2 trading system.

Contains the main session execution logic with Gemini + Player architecture.
"""

import os
from typing import Any, Dict, Optional, Union

from croupier.croupier import Croupier
from gemini.gemini_core import Gemini
from sensors.sensor_manager import SensorManager
from tables.ccxt_adapter import CCXTAdapter
from tables.position_tracker import PositionTracker

from . import config
from .exceptions import CasinoError, TradingError
from .logger import logger, performance_monitor
from .session_helpers import get_table_state, log_trade  # noqa: F401
from .validators import ValidationError, validate_positive_number, validate_string


@performance_monitor("run_session_with_player")
def run_session_with_player(
    dataset_path: str,
    initial_balance: float,
    gemini: Gemini,
    player_module: Any,
    player_name: str,
    mode: str = "backtest",
    multi_asset_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Union[str, float, int]]:
    """
    Ejecuta una sesión de backtest usando la arquitectura Gemini + Player con gestión de posiciones.

    Esta función coordina la ejecución completa de una sesión de trading, manejando:
    - Procesamiento vela por vela de datos históricos
    - Gestión de posiciones abiertas y cerradas
    - Interacción entre Gemini (validador), Player (sizing) y Croupier (ejecución)
    - Actualización de estadísticas y logging

    Args:
        dataset_path: Ruta al archivo CSV con datos históricos OHLCV.
        initial_balance: Capital inicial en USD para la sesión.
        gemini: Instancia de Gemini que valida señales y toma decisiones.
        player_module: Módulo del player que calcula tamaños de posición
            (ej: kelly_player, fixed_player, paroli_player).
        player_name: Nombre identificador del player para logging.
        mode: Modo de ejecución ('backtest', 'live_ccxt', 'multi_asset_backtest').
        multi_asset_config: Configuración opcional para modo multi-asset.

    Returns:
        Dict con estadísticas completas de la sesión incluyendo:
        - dataset: Nombre del dataset procesado
        - player: Nombre del player usado
        - initial_balance: Balance inicial
        - final_balance: Balance final
        - candles: Número total de velas procesadas
        - bet_trades: Número de trades reales ejecutados
        - ghost_trades: Número de trades simulados para entrenamiento
        - wins/losses: Conteo de resultados
        - winrate: Porcentaje de victorias
        - fees/funding: Costos totales
        - liquidations: Número de liquidaciones forzadas

    Raises:
        ValidationError: Si los parámetros de entrada son inválidos.
        TradingError: Si ocurre un error durante el trading.
        CasinoError: Para errores generales del sistema.
        NotImplementedError: Si se solicita modo multi-asset (pendiente v1.8).
        FileNotFoundError: Si el dataset_path no existe.
    """
    # Validación de parámetros de entrada
    try:
        validated_dataset = validate_string(dataset_path, "dataset_path", 1, 500)
        validated_balance = validate_positive_number(initial_balance, "initial_balance")  # noqa: F841
        validated_player_name = validate_string(player_name, "player_name", 1, 50)  # noqa: F841
        validated_mode = validate_string(mode, "mode", 1, 20)

        if validated_mode not in ["backtest", "live", "live_ccxt"]:
            raise ValidationError(f"Modo inválido: {validated_mode}")

    except ValidationError as e:
        logger.error(f"Parámetros de entrada inválidos: {e}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado en validación: {e}")
        raise CasinoError(f"Error en validación de parámetros: {e}")

    dataset_name = os.path.basename(validated_dataset)
    logger.info(f"🎰 Ejecutando dataset: {dataset_name}")
    logger.info(f"🎮 Player activo: {validated_player_name.upper()}")

    # Seleccionar tabla según modo
    try:
        if validated_mode == "multi_asset_backtest" and multi_asset_config:
            logger.info("🔄 Usando TableBacktestMultiAsset")
            # Placeholder - será implementado en v1.8
            raise NotImplementedError("Multi-asset backtest not yet implemented in v1.7")
        elif validated_mode == "live_ccxt":
            logger.info("🔄 Usando CCXTAdapter")
            # Configuración para live trading
            exchange_id = getattr(config, "EXCHANGE", "binance").lower()
            symbols = getattr(config, "MULTI_ASSET_SYMBOLS", ["BTC/USDT"])
            table = CCXTAdapter(
                exchange_id=exchange_id,
                symbols=symbols,
                timeframe=getattr(config, "TIMEFRAME", "1m"),
                testnet=getattr(config, "TESTNET", True),
            )
            # Balance ya inicializado en CCXTAdapter
        else:
            logger.info("🔄 Usando TableBacktest (single-asset)")
            if not os.path.exists(validated_dataset):
                raise FileNotFoundError(f"Dataset no encontrado: {validated_dataset}")

            # LEGACY: TableBacktest obsoleto, usar BacktestDataSource
            raise NotImplementedError("Use BacktestDataSource instead")
            # table = TableBacktest(validated_dataset)
            # set_table_balance(table, validated_balance)
    except Exception as e:
        logger.error(f"Error inicializando tabla: {e}")
        raise TradingError(f"No se pudo inicializar la tabla: {e}")

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
        if hasattr(table, "next_candle_batch"):
            # Modo multi-asset (placeholder)
            raise NotImplementedError("Multi-asset mode not implemented in v1.7")
        else:
            # Modo single-asset tradicional
            candle = table.next_candle()
            if candle is None:
                break

            candles += 1
            current_candle = candle
            current_symbol = candle.get("symbol", "UNKNOWN")

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
            current_balance = get_table_state(table).get("balance", initial_balance)
            new_balance = current_balance + pnl_net

            # Aplicar cambio de balance
            try:
                table.balance_manager.balance = new_balance
            except Exception:
                if hasattr(table.balance_manager, "set_balance"):
                    table.balance_manager.set_balance(new_balance)

            # Log del trade cerrado
            log_trade("CLOSE", None, closed_result, closed_result, new_balance)

            # Actualizar memoria de Gemini
            if closed_result.get("trade_id"):
                gemini.on_trade_result(closed_result["trade_id"], closed_result)

            # Actualizar estado del player
            if (
                player_state is not None
                and hasattr(player_module, "handle_trade_outcome")
                and outcome in {"WIN", "LOSS"}
            ):
                player_state = player_module.handle_trade_outcome(player_state, "BET", closed_result)

        # 2. SEGUNDO: Intentar abrir nuevas posiciones si hay capital disponible

        # Obtener equity actual (después de posibles cierres)
        current_balance = get_table_state(table).get("balance", initial_balance)
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
            log_trade(action, verdict, order, ghost_result, current_balance)

            if verdict.trade_id:
                gemini.on_trade_result(verdict.trade_id, ghost_result)
        else:
            # Verificar si se puede abrir la posición
            margin_required = order.get("margin_used", 0.0)

            if position_tracker.can_open_position(margin_required, available_equity):
                # Calcular precio de entrada (close de vela actual)
                entry_price = float(current_candle.get("close", 0.0))

                # Abrir posición en el tracker
                position = position_tracker.open_position(
                    order, entry_price, current_candle.get("timestamp", ""), available_equity
                )

                if position:
                    # Log de apertura
                    log_trade("OPEN", verdict, order, {"result": "OPEN"}, current_balance)

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
                logger.info(
                    f"⏭️  SKIP | Capital insuficiente | Disponible: {available_equity:.2f} | Requerido: {margin_required:.2f}"
                )

    # 3. Al final: Forzar cierre de posiciones abiertas
    if position_tracker.open_positions:
        logger.info(f"🔚 Cerrando {len(position_tracker.open_positions)} posiciones abiertas al final del backtest")
        final_candle = {
            "close": table.data[-1]["close"] if table.data else candle.get("close", 0),
            "timestamp": table.data[-1]["timestamp"] if table.data else candle.get("timestamp", ""),
            "market": table.market_id,
            "timeframe": table.timeframe,
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
            current_balance = get_table_state(table).get("balance", initial_balance)
            new_balance = current_balance + pnl_net

            try:
                table.balance_manager.balance = new_balance
            except Exception:
                if hasattr(table.balance_manager, "set_balance"):
                    table.balance_manager.set_balance(new_balance)

            log_trade("FORCE_CLOSE", None, closed_result, closed_result, new_balance)

            if closed_result.get("trade_id"):
                gemini.on_trade_result(closed_result["trade_id"], closed_result)

    # Resumen final
    final_state = get_table_state(table)
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
