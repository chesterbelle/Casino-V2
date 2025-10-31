"""
===================================================
🪙 TableBacktestMultiAsset — Mesa Multi-Símbolo
===================================================

Rol:
----
• Proveer velas históricas sincronizadas desde múltiples CSVs
• Ejecutar órdenes del Croupier con TP/SL sobre velas futuras
• Gestionar posiciones concurrentes en múltiples símbolos
• Mantener balance unificado y capital bloqueado

Características:
-------------
• Multi-asset: Múltiples símbolos concurrentes
• Temporal sync: Sincronización precisa de timestamps
• Position tracking: Gestión realista de posiciones abiertas
• Capital management: Balance unificado con bloqueo de margen

CSV esperado (cabecera):
------------------------
timestamp,open,high,low,close,volume

Configuración:
-------------
• TAKE_PROFIT (R) • STOP_LOSS (L)
• COMMISSION_RATE • SLIPPAGE_DEFAULT
• MAX_CONCURRENT_POSITIONS
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import config
except ImportError:
    import os
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        from core import config

from .balance_manager import BalanceManager
from .position_tracker import PositionTracker
from .table_base import BaseTable


class TableBacktestMultiAsset(BaseTable):
    """
    Backtest multi-asset con sincronización temporal.
    next_candle() avanza el cursor global y retorna vela del símbolo activo.
    execute_order() abre posiciones reales usando PositionTracker.
    """

    def __init__(
        self, csv_paths: List[str], symbols: Optional[List[str]] = None, timeframes: Optional[List[str]] = None
    ):
        """
        Inicializa mesa multi-asset.

        Args:
            csv_paths: Lista de rutas a CSVs (uno por símbolo)
            symbols: Lista de símbolos (opcional, se infiere de paths)
            timeframes: Lista de timeframes (opcional, se infiere de paths)
        """
        self.logger = logging.getLogger("TableBacktestMultiAsset")

        # Validar inputs
        if not csv_paths:
            raise ValueError("Se requieren al menos un CSV path")

        self.csv_paths = csv_paths
        self.num_symbols = len(csv_paths)

        # Inferir símbolos y timeframes si no se proporcionan
        if symbols is None or timeframes is None:
            inferred_data = [self._infer_market_from_path(path) for path in csv_paths]
            self.symbols = symbols or [data[0] for data in inferred_data]
            self.timeframes = timeframes or [data[1] for data in inferred_data]
        else:
            self.symbols = symbols
            self.timeframes = timeframes

        # Validar consistencia
        if len(self.symbols) != self.num_symbols or len(self.timeframes) != self.num_symbols:
            raise ValueError("Symbols y timeframes deben tener la misma longitud que csv_paths")

        # Cargar datos de cada símbolo
        self.symbol_data: Dict[str, List[Dict]] = {}
        self.symbol_cursors: Dict[str, int] = {}
        self.symbol_last_index: Dict[str, int] = {}

        for i, (path, symbol, timeframe) in enumerate(zip(csv_paths, self.symbols, self.timeframes)):
            data = self._load_csv(path)
            if not data:
                raise ValueError(f"CSV vacío o inválido: {path}")

            self.symbol_data[symbol] = data
            self.symbol_cursors[symbol] = 0
            self.symbol_last_index[symbol] = -1

            self.logger.info(f"📚 {symbol}@{timeframe}: {len(data)} velas desde {path}")

        # Estado global del backtest
        self._global_cursor = 0  # Cursor temporal global
        self._current_timestamp_ms: Optional[int] = None
        self._active_symbol = self.symbols[0]  # Símbolo activo para next_candle()

        # Componentes core
        starting_balance = getattr(config, "STARTING_BALANCE", 10_000.0)
        max_positions = getattr(config, "MAX_CONCURRENT_POSITIONS", 5)
        self.balance_manager = BalanceManager(starting_balance=starting_balance)
        self.position_tracker = PositionTracker(max_concurrent_positions=max_positions)

        # Parámetros de exchange (comunes para todos los símbolos)
        profile_name = getattr(config, "EXCHANGE_PROFILE", "binance")
        self.exchange_profile = self._load_exchange_profile(profile_name)

        self.maker_fee = float(self.exchange_profile.get("maker_fee", getattr(config, "COMMISSION_RATE", 0.0004)))
        self.taker_fee = float(self.exchange_profile.get("taker_fee", getattr(config, "COMMISSION_RATE", 0.0004)))
        self.entry_fee_rate = float(self.exchange_profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.exchange_profile.get("exit_fee_rate", self.taker_fee))
        self.leverage_limit = float(self.exchange_profile.get("leverage_limit", getattr(config, "MAX_LEVERAGE", 50)))

        # RR por defecto
        self.R = getattr(config, "TAKE_PROFIT", 0.01)
        self.L = getattr(config, "STOP_LOSS", 0.01)

        # Slippage y funding (simplificados para multi-asset)
        self.slippage_model = self.exchange_profile.get("slippage_model", {})
        self.slippage_fallback = float(getattr(config, "SLIPPAGE_DEFAULT", 0.0))

        self.logger.info(
            f"🪙 TableBacktestMultiAsset inicializada: {self.num_symbols} símbolos | "
            f"Balance: ${starting_balance:,.0f} | Max posiciones: {max_positions}"
        )

    def next_candle(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Avanza el cursor global y retorna la siguiente vela sincronizada.

        Args:
            symbol: Símbolo específico (opcional, usa símbolo activo)

        Returns:
            Vela normalizada o None si terminó el backtest
        """
        target_symbol = symbol or self._active_symbol

        if target_symbol not in self.symbol_data:
            self.logger.warning(f"Símbolo no encontrado: {target_symbol}")
            return None

        # Encontrar el próximo timestamp común a todos los símbolos
        next_timestamp_ms = self._find_next_common_timestamp()

        if next_timestamp_ms is None:
            # No hay más timestamps comunes - fin del backtest
            self.logger.info("🏁 Fin del backtest multi-asset - no más timestamps comunes")
            return None

        # Actualizar cursor global
        self._current_timestamp_ms = next_timestamp_ms
        self._global_cursor += 1

        # Obtener vela para el símbolo objetivo en este timestamp
        candle = self._get_candle_at_timestamp(target_symbol, next_timestamp_ms)

        if candle:
            # Actualizar cursor específico del símbolo
            self.symbol_last_index[target_symbol] = self.symbol_cursors[target_symbol] - 1

            # Verificar y cerrar posiciones que tocaron TP/SL
            closed_positions = self.position_tracker.check_and_close_positions(candle)

            # Aplicar resultados al balance
            for result in closed_positions:
                pnl = result.get("pnl", 0.0)
                fee = result.get("fee", 0.0)
                self.balance_manager.apply_pnl(pnl, fee)

                self.logger.info(
                    f"🔒 CLOSED {result['symbol']} {result['side']} | "
                    f"P&L: {pnl:+.2f} | Fee: {fee:.2f} | Reason: {result['exit_reason']}"
                )

            # Retornar vela con estado actual
            state = self.get_state()
            return {
                "timestamp": candle["timestamp"],
                "timestamp_ms": candle.get("timestamp_ms"),
                "symbol": target_symbol,
                "timeframe": self.timeframes[self.symbols.index(target_symbol)],
                "market": f"{target_symbol}@{self.timeframes[self.symbols.index(target_symbol)]}",
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "equity": state.get("equity"),
                "balance": state.get("balance"),
            }

        return None

    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta orden real usando PositionTracker.
        Abre posiciones que persisten hasta TP/SL.

        Args:
            order: Orden en formato estándar

        Returns:
            Resultado de la ejecución
        """
        try:
            # Extraer parámetros
            symbol = order.get("symbol", self._active_symbol)
            side = order.get("side", "").upper()
            size_fraction = float(order.get("size", 0.0))
            leverage = float(order.get("leverage", 1.0))
            trade_id = order.get("trade_id", f"multi_{symbol}_{self._global_cursor}")

            # Validaciones
            if symbol not in self.symbol_data:
                raise ValueError(f"Símbolo no disponible: {symbol}")

            if side not in ["LONG", "SHORT"]:
                raise ValueError(f"Side inválido: {side}")

            if size_fraction <= 0:
                raise ValueError(f"Size fraction inválido: {size_fraction}")

            # Obtener precio de entrada (última vela del símbolo)
            last_index = self.symbol_last_index.get(symbol, -1)
            if last_index < 0:
                raise RuntimeError(f"No hay vela de referencia para {symbol}")

            entry_candle = self.symbol_data[symbol][last_index]
            entry_price = float(entry_candle["close"])
            entry_timestamp = entry_candle.get("timestamp", "")

            # Calcular factores TP/SL
            tp_factor = float(order.get("take_profit", 1.0 + self.R))
            sl_factor = float(order.get("stop_loss", 1.0 - self.L))

            # Calcular niveles objetivos
            if side == "LONG":
                tp_level = entry_price * tp_factor
                sl_level = entry_price * sl_factor
            else:  # SHORT
                tp_level = entry_price * (2.0 - tp_factor)
                sl_level = entry_price * (2.0 - sl_factor)

            # Obtener equity disponible
            total_equity = self.balance_manager.get_state().get("equity", 0.0)
            available_equity = self.position_tracker.get_available_equity(total_equity)

            # Aplicar slippage
            slippage_pct = self._compute_slippage(size_fraction * leverage)
            if slippage_pct > 0:
                if side == "LONG":
                    entry_price *= 1 + slippage_pct
                else:
                    entry_price *= 1 - slippage_pct

            # Crear orden completa para PositionTracker
            full_order = {
                "symbol": symbol,
                "side": side,
                "size": size_fraction,
                "leverage": leverage,
                "take_profit": tp_level,
                "stop_loss": sl_level,
                "trade_id": trade_id,
                "timestamp": entry_timestamp,
            }

            # Intentar abrir posición
            position = self.position_tracker.open_position(
                order=full_order,
                entry_price=entry_price,
                entry_timestamp=entry_timestamp,
                available_equity=available_equity,
            )

            if position:
                # Calcular fees de entrada
                notional = position.notional
                entry_fee = notional * self.entry_fee_rate

                # Aplicar fee de entrada al balance
                self.balance_manager.apply_pnl(0.0, entry_fee)

                self.logger.info(
                    f"📈 OPEN {symbol} {side} | Entry: {entry_price:.2f} | "
                    f"TP: {tp_level:.2f} | SL: {sl_level:.2f} | "
                    f"Notional: {notional:.2f} | Margin: {position.margin_used:.2f}"
                )

                return {
                    "trade_id": trade_id,
                    "result": "OPEN",
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "tp_level": tp_level,
                    "sl_level": sl_level,
                    "margin_used": position.margin_used,
                    "notional": notional,
                    "leverage": leverage,
                    "fee": entry_fee,
                    "balance": self.balance_manager.get_state().get("balance"),
                    "timestamp": entry_timestamp,
                    "market": f"{symbol}@{self.timeframes[self.symbols.index(symbol)]}",
                    "timeframe": self.timeframes[self.symbols.index(symbol)],
                    "action": "OPEN",
                    "ghost": False,
                }
            else:
                return {
                    "trade_id": trade_id,
                    "result": "REJECTED",
                    "symbol": symbol,
                    "reason": "Insufficient capital or position limit reached",
                    "balance": self.balance_manager.get_state().get("balance"),
                    "timestamp": entry_timestamp,
                    "action": "REJECTED",
                    "ghost": False,
                }

        except Exception as e:
            self.logger.error(f"❌ Error ejecutando orden: {e}")
            return {
                "trade_id": order.get("trade_id", "error"),
                "result": "ERROR",
                "error": str(e),
                "symbol": order.get("symbol", ""),
                "balance": self.balance_manager.get_state().get("balance"),
                "action": "ERROR",
                "ghost": False,
            }

    def get_state(self) -> Dict:
        """Retorna estado unificado de la mesa multi-asset."""
        balance_state = self.balance_manager.get_state()
        position_stats = self.position_tracker.get_stats()

        return {
            "balance": float(balance_state.get("balance", 0.0)),
            "equity": float(balance_state.get("equity", balance_state.get("balance", 0.0))),
            "positions": position_stats,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "global_cursor": self._global_cursor,
            "current_timestamp_ms": self._current_timestamp_ms,
            "active_symbol": self._active_symbol,
        }

    def set_active_symbol(self, symbol: str) -> None:
        """Cambia el símbolo activo para next_candle()."""
        if symbol in self.symbols:
            self._active_symbol = symbol
        else:
            raise ValueError(f"Símbolo no disponible: {symbol}")

    def get_available_symbols(self) -> List[str]:
        """Retorna lista de símbolos disponibles."""
        return self.symbols.copy()

    def force_close_all_positions(self) -> List[Dict]:
        """
        Fuerza cierre de todas las posiciones abiertas (fin del backtest).
        Usa precios de cierre actuales.
        """
        closed_results = []

        # Obtener precios de cierre actuales para cada símbolo
        for symbol in self.symbols:
            last_index = self.symbol_last_index.get(symbol, -1)
            if last_index >= 0:
                close_price = float(self.symbol_data[symbol][last_index]["close"])
                timestamp = self.symbol_data[symbol][last_index].get("timestamp", "")

                # Crear vela dummy para cierre
                dummy_candle = {
                    "timestamp": timestamp,
                    "timestamp_ms": self.symbol_data[symbol][last_index].get("timestamp_ms"),
                    "symbol": symbol,
                    "timeframe": self.timeframes[self.symbols.index(symbol)],
                    "market": f"{symbol}@{self.timeframes[self.symbols.index(symbol)]}",
                    "open": close_price,
                    "high": close_price,
                    "low": close_price,
                    "close": close_price,
                    "volume": 0.0,
                }

                # Cerrar posiciones de este símbolo
                symbol_closed = self.position_tracker.force_close_all_positions(dummy_candle)
                closed_results.extend(symbol_closed)

        # Aplicar resultados al balance
        for result in closed_results:
            pnl = result.get("pnl", 0.0)
            fee = result.get("fee", 0.0)
            self.balance_manager.apply_pnl(pnl, fee)

        self.logger.info(f"🔒 Force closed {len(closed_results)} positions at end of backtest")
        return closed_results

    # ========================================
    # Métodos internos de sincronización
    # ========================================

    def _find_next_common_timestamp(self) -> Optional[int]:
        """
        Encuentra el próximo timestamp presente en todos los símbolos.
        Avanza cursores individuales según sea necesario.
        """
        # Encontrar el timestamp más temprano disponible en cada símbolo
        earliest_timestamps = {}

        for symbol in self.symbols:
            cursor = self.symbol_cursors[symbol]
            if cursor < len(self.symbol_data[symbol]):
                candle = self.symbol_data[symbol][cursor]
                ts_ms = candle.get("timestamp_ms")
                if ts_ms is not None:
                    earliest_timestamps[symbol] = ts_ms

        if not earliest_timestamps:
            return None  # No hay más datos en ningún símbolo

        # El timestamp común es el máximo de los timestamps más tempranos
        # Esto asegura que todos los símbolos tengan datos hasta ese punto
        common_timestamp = max(earliest_timestamps.values())

        # Avanzar cursores de símbolos que están detrás del timestamp común
        for symbol in self.symbols:
            cursor = self.symbol_cursors[symbol]
            while cursor < len(self.symbol_data[symbol]):
                candle = self.symbol_data[symbol][cursor]
                ts_ms = candle.get("timestamp_ms")
                if ts_ms is None or ts_ms <= common_timestamp:
                    cursor += 1
                else:
                    break
            self.symbol_cursors[symbol] = cursor

        return common_timestamp

    def _get_candle_at_timestamp(self, symbol: str, target_timestamp_ms: int) -> Optional[Dict]:
        """
        Obtiene la vela más cercana al timestamp objetivo para un símbolo.
        """
        data = self.symbol_data[symbol]
        cursor = self.symbol_cursors[symbol]

        # Buscar hacia atrás desde el cursor actual
        for i in range(cursor - 1, -1, -1):
            candle = data[i]
            ts_ms = candle.get("timestamp_ms")
            if ts_ms is not None and ts_ms <= target_timestamp_ms:
                return candle

        return None

    # ========================================
    # Métodos auxiliares (reutilizados de TableBacktest)
    # ========================================

    def _load_csv(self, path: str) -> List[Dict]:
        """Carga datos CSV para un símbolo."""
        out: List[Dict] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts_raw = row.get("timestamp") or row.get("date") or row.get("time") or ""
                    ts_ms = self._parse_timestamp_to_ms(ts_raw)
                    out.append(
                        {
                            "timestamp": ts_raw,
                            "timestamp_ms": ts_ms,
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                            "volume": float(row.get("volume", 0.0)),
                        }
                    )
                except Exception:
                    continue  # Saltar filas corruptas
        return out

    def _infer_market_from_path(self, path: str) -> Tuple[str, str]:
        """Infiera símbolo y timeframe desde el path del CSV."""
        fname = os.path.basename(path)
        base = fname.split(".")[0]
        parts = base.split("_") if base else []

        symbol = parts[0] if parts else "UNKNOWN"
        timeframe = "UNKNOWN"

        timeframe_pattern = re.compile(r"^\d+(min|m|h|d|wk|mo)$", re.IGNORECASE)
        for part in parts[1:]:
            token = part.lower()
            if timeframe_pattern.match(token):
                timeframe = part
                break

        return symbol or "UNKNOWN", timeframe

    def _parse_timestamp_to_ms(self, ts: str) -> Optional[int]:
        """Convierte timestamp string a milisegundos."""
        if not ts:
            return None
        ts = ts.strip()
        if not ts:
            return None
        try:
            if ts.isdigit():
                value = int(ts)
                return value if value > 10_000_000_000 else value * 1000
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

    def _load_exchange_profile(self, name: str) -> Dict[str, float]:
        """Carga perfil de exchange."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base_dir, "data", "exchange_profiles", f"{name}.json")

        if not os.path.exists(profile_path):
            self.logger.warning("Perfil de exchange '%s' no encontrado. Usando valores por defecto.", name)
            return {}

        try:
            with open(profile_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            self.logger.warning("No se pudo cargar el perfil '%s': %s. Usando defaults.", name, exc)
            return {}

    def _compute_slippage(self, size_fraction: float) -> float:
        """Calcula slippage porcentual."""
        model = self.slippage_model or {}
        model_type = str(model.get("type", "fixed")).lower()
        base = float(model.get("base_spread", self.slippage_fallback))

        if model_type == "linear":
            per_fraction = float(model.get("per_size_fraction", 0.0))
            base += per_fraction * max(size_fraction, 0.0)

        return max(0.0, base)
