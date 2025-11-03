"""
====================================================
🪙 TableBacktest — Mesa sobre CSV para Casino V2
====================================================

Rol:
----
• Proveer velas históricas desde un CSV (backtest “rápido”).
• Ejecutar órdenes del Croupier con lógica de TP/SL sobre velas futuras.
• Aplicar fees y (opcionalmente) slippage al PnL monetario.
• Mantener y reportar el balance a través de BalanceManager.

Importante:
-----------
• El Croupier SIEMPRE opera; el “modo simulado” existe solo aquí (feed),
  a través del flag `order["ghost"]`.
• Si ghost=True: se determina WIN/LOSS, pero NO se altera el balance.
• Si ghost=False: se aplica PnL + fees y se actualiza el balance.

CSV esperado (cabecera):
------------------------
timestamp,open,high,low,close,volume

Configuración leída desde config.py:
------------------------------------
• TAKE_PROFIT (R)         • STOP_LOSS (L)
• COMMISSION_RATE         • SLIPPAGE_DEFAULT (opcional)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import config
except ImportError:
    # Fallback for when config is in core/

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        # Last resort: import from core
        from core import config

from .balance_manager import BalanceManager
from .table_base import BaseTable


class TableBacktest(BaseTable):
    """
    Backtest secuencial vela-por-vela.
    next_candle() avanza un índice interno.
    execute_order() simula TP/SL a partir de la vela actual hacia adelante.
    """

    def __init__(self, csv_path: str, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        self.logger = logging.getLogger("TableBacktest")
        self.csv_path = csv_path
        inferred_symbol, inferred_timeframe = self._infer_market_from_path(csv_path)
        self.symbol = symbol or inferred_symbol
        self.timeframe = timeframe or inferred_timeframe
        self.market_id = f"{self.symbol}@{self.timeframe}" if self.timeframe != "UNKNOWN" else self.symbol
        self.data: List[Dict] = self._load_csv(csv_path)
        self.n = len(self.data)
        self._cursor = 0  # índice de la PROXIMA vela a entregar
        self._last_index = -1  # última vela entregada (para saber desde dónde simular)
        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))

        # Parámetros de costos (cargados desde perfil de exchange)
        profile_name = getattr(config, "EXCHANGE_PROFILE", "binance")
        self.exchange_profile = self._load_exchange_profile(profile_name)

        self.maker_fee = float(self.exchange_profile.get("maker_fee", getattr(config, "COMMISSION_RATE", 0.0004)))
        self.taker_fee = float(self.exchange_profile.get("taker_fee", getattr(config, "COMMISSION_RATE", 0.0004)))
        self.entry_fee_rate = float(self.exchange_profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.exchange_profile.get("exit_fee_rate", self.taker_fee))
        self.leverage_limit = float(self.exchange_profile.get("leverage_limit", getattr(config, "MAX_LEVERAGE", 50)))
        self.maintenance_margin_rate = float(
            self.exchange_profile.get(
                "maintenance_margin_rate",
                getattr(config, "MAINTENANCE_MARGIN_RATE", 0.005),
            )
        )

        self.slippage_model = self.exchange_profile.get("slippage_model", {})
        self.slippage_fallback = float(getattr(config, "SLIPPAGE_DEFAULT", 0.0))
        self.funding_rate_per_hour = float(self.exchange_profile.get("funding_rate_per_hour", 0.0))
        self.funding_events = self._load_funding_schedule(self.symbol)

        # RR por defecto (si la orden no define sus factores)
        self.R = getattr(config, "TAKE_PROFIT", 0.01)
        self.L = getattr(config, "STOP_LOSS", 0.01)

        if self.n == 0:
            raise ValueError(f"Dataset vacío: {csv_path}")

        self.logger.info(
            f"📚 CSV cargado: {csv_path} | velas: {self.n} | símbolo: {self.symbol} | timeframe: {self.timeframe}"
        )

    # ----------------------------------------------------
    # API de consumo de velas
    # ----------------------------------------------------
    def next_candle(self) -> Optional[Dict]:
        """Devuelve la siguiente vela y avanza el cursor."""
        if self._cursor >= self.n:
            return None
        row = self.data[self._cursor]
        self._last_index = self._cursor
        self._cursor += 1

        # Reportar junto con balance actual (estandarizado)
        state = self.get_state()
        return {
            "timestamp": row["timestamp"],
            "timestamp_ms": row.get("timestamp_ms"),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market": self.market_id,
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "equity": state.get("equity"),
            "balance": state.get("balance"),
        }

    # ----------------------------------------------------
    # API de ejecución para el Croupier
    # ----------------------------------------------------
    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta órdenes para GHOST trades (entrenamiento sin riesgo).

        ⚠️  IMPORTANTE: Esta función SOLO se usa para GHOST trades.
           Para posiciones reales, usa PositionTracker.open_position() y check_and_close_positions().

        • Si 'ghost'==True → simula trade completo inmediatamente (entrena sin riesgo)
        • NO modifica balance ni posiciones abiertas

        Retorna resultado normalizado para ghost trades.
        """
        # Validación: solo para ghost trades
        ghost = bool(order.get("ghost", False))
        if not ghost:
            raise ValueError(
                "execute_order() solo debe usarse para ghost trades. Para posiciones reales usa PositionTracker."
            )

        # Lógica completa para ghost trades (simula trade completo inmediatamente)
        side = order.get("side", "").upper()
        size_fraction = float(order.get("size", 0.0))
        trade_id = order.get("trade_id") or f"backtest_{self.symbol}_{self._last_index}"
        symbol = order.get("symbol", self.symbol)

        if self._last_index < 0:
            raise RuntimeError("No hay vela de referencia para ejecutar ghost trade.")

        # Precio de entrada (close de la última vela entregada), con slippage simple
        entry_candle = self.data[self._last_index]
        entry_price = float(entry_candle["close"])
        max_leverage = self.leverage_limit if self.leverage_limit > 0 else 1.0
        requested_leverage = float(order.get("leverage", max_leverage))
        effective_leverage = max(1.0, min(requested_leverage, max_leverage))

        slippage_pct = self._compute_slippage(size_fraction * effective_leverage)
        if slippage_pct > 0:
            if side == "LONG":
                entry_price *= 1 + slippage_pct
            else:
                entry_price *= 1 - slippage_pct

        entry_timestamp_ms = self._resolve_order_timestamp(order, entry_candle)

        # Factores de TP/SL (si no vienen en la orden, usar config)
        tp_factor = float(order.get("take_profit", 1.0 + self.R))
        sl_factor = float(order.get("stop_loss", 1.0 - self.L))

        # Niveles objetivo
        if side == "LONG":
            tp_level = entry_price * tp_factor
            sl_level = entry_price * sl_factor
        elif side == "SHORT":
            tp_level = entry_price * (2 - tp_factor) if tp_factor > 1 else entry_price * tp_factor
            sl_level = entry_price * (2 - sl_factor) if sl_factor < 1 else entry_price * sl_factor
        else:
            raise ValueError(f"Side inválido: {side}")

        state = self.balance_manager.get_state()
        equity = float(state.get("equity", state.get("balance", 0.0)))
        notional = max(0.0, equity * size_fraction * effective_leverage)
        margin_used = notional / effective_leverage if effective_leverage > 0 else notional
        liquidation_level = None
        if notional > 0.0 and effective_leverage > 0:
            risk_ratio = (1.0 / effective_leverage) - max(0.0, self.maintenance_margin_rate)
            risk_ratio = max(risk_ratio, 0.0)
            risk_ratio = min(risk_ratio, 0.95)
            if side == "LONG":
                liquidation_level = entry_price * (1.0 - risk_ratio)
            else:
                liquidation_level = entry_price * (1.0 + risk_ratio)
            if liquidation_level is not None and liquidation_level <= 0:
                liquidation_level = None

        # Simular trade completo inmediatamente (para ghost training)
        outcome, trigger_price, bars_held, exit_reason, liquidated, exit_timestamp_ms = self._walk_to_outcome(
            side,
            start_index=self._last_index + 1,
            tp_level=tp_level,
            sl_level=sl_level,
            liquidation_level=liquidation_level,
        )

        # Determinar precio de salida estimado
        exit_price = trigger_price if trigger_price is not None else entry_price
        pnl_pct_raw = 0.0
        if entry_price and exit_price:
            try:
                if side == "LONG":
                    pnl_pct_raw = (float(exit_price) - float(entry_price)) / float(entry_price)
                else:
                    pnl_pct_raw = (float(entry_price) - float(exit_price)) / float(entry_price)
            except (TypeError, ValueError, ZeroDivisionError):
                pnl_pct_raw = 0.0

        # Cálculo monetario (simulado, no afecta balance)
        fee_total = 0.0
        pnl_value = 0.0
        funding_cost = 0.0

        # Fees: entrada + salida (simulados)
        entry_fee = notional * self.entry_fee_rate
        exit_fee = notional * self.exit_fee_rate
        fee_total = entry_fee + exit_fee

        pnl_value = notional * pnl_pct_raw

        if entry_timestamp_ms is not None and exit_timestamp_ms is not None:
            funding_cost = self._funding_cost_between(entry_timestamp_ms, exit_timestamp_ms, notional, side)
        elif self.funding_rate_per_hour != 0.0:
            hold_hours = self._bars_to_hours(bars_held)
            funding_cost = notional * self.funding_rate_per_hour * hold_hours

        if exit_reason == "LIQUIDATION":
            liquidation_loss = min(equity, margin_used) if margin_used > 0 else 0.0
            pnl_value = -liquidation_loss

        # Resultado normalizado para ghost trade
        result_dict = {
            "trade_id": trade_id,
            "result": outcome,
            "pnl": float(pnl_value),
            "fee": float(fee_total),
            "funding": float(funding_cost),
            "liquidated": bool(liquidated),
            "margin_used": float(margin_used),
            "notional": float(notional),
            "leverage": float(effective_leverage),
            "symbol": symbol,
            "balance": None,  # No afecta balance
            "pnl_pct": float(pnl_pct_raw),
            "entry_price": float(entry_price),
            "trigger_price": float(trigger_price),
            "bars_held": bars_held,
            "exit_reason": exit_reason,
            "exit_timestamp": self._format_timestamp_ms(exit_timestamp_ms),
            "market": self.market_id,
            "timeframe": self.timeframe,
            "timestamp": order.get("timestamp"),
            "side": side,
            "action": "GHOST",
            "ghost": True,
        }

        return result_dict

    # ----------------------------------------------------
    # Estado
    # ----------------------------------------------------
    def get_state(self) -> Dict:
        """
        Devuelve estado estándar para el main/croupier/sensores.
        """
        s = self.balance_manager.get_state()
        # Asegurar claves
        return {"balance": float(s.get("balance", 0.0)), "equity": float(s.get("equity", s.get("balance", 0.0)))}

    def _compute_slippage(self, size_fraction: float) -> float:
        """
        Calcula el slippage porcentual basado en el modelo del perfil.
        """
        model = self.slippage_model or {}
        model_type = str(model.get("type", "fixed")).lower()
        base = float(model.get("base_spread", self.slippage_fallback))

        if model_type == "linear":
            per_fraction = float(model.get("per_size_fraction", 0.0))
            base += per_fraction * max(size_fraction, 0.0)

        volatility_factor = self._volatility_factor()
        if volatility_factor > 0:
            base *= 1 + volatility_factor

        return max(0.0, base)

    def _bars_to_hours(self, bars: int) -> float:
        if bars <= 0:
            return 0.0
        minutes = self._timeframe_to_minutes(self.timeframe)
        return bars * (minutes / 60.0) if minutes > 0 else 0.0

    def _timeframe_to_minutes(self, timeframe: Optional[str]) -> float:
        if not timeframe or timeframe == "UNKNOWN":
            return 0.0
        tf = timeframe.lower()
        pattern = re.compile(r"^(\d+)(min|m|h|d|wk|mo)$")
        match = pattern.match(tf)
        if not match:
            return 0.0
        value = int(match.group(1))
        unit = match.group(2)
        if unit in ("min", "m"):
            return float(value)
        if unit == "h":
            return float(value * 60)
        if unit == "d":
            return float(value * 60 * 24)
        if unit == "wk":
            return float(value * 60 * 24 * 7)
        if unit == "mo":
            return float(value * 60 * 24 * 30)
        return 0.0

    def _volatility_factor(self) -> float:
        window = getattr(config, "SLIPPAGE_VOL_WINDOW", 20)
        multiplier = float(getattr(config, "SLIPPAGE_VOL_MULTIPLIER", 0.0))
        if multiplier == 0.0 or window <= 1:
            return 0.0

        if self._last_index < 0:
            return 0.0

        start = max(0, self._last_index - window + 1)
        closes = [float(self.data[i]["close"]) for i in range(start, self._last_index + 1)]

        if len(closes) < window:
            return 0.0

        mean_price = sum(closes) / len(closes)
        if mean_price == 0:
            return 0.0

        variance = sum((c - mean_price) ** 2 for c in closes) / len(closes)
        std_dev = variance**0.5
        volatility = std_dev / mean_price
        return float(max(0.0, volatility * multiplier))

    def _funding_cost_between(
        self, start_ms: Optional[int], end_ms: Optional[int], notional: float, side: str
    ) -> float:
        if start_ms is None or end_ms is None or start_ms >= end_ms:
            return 0.0

        if self.funding_events:
            total = 0.0
            for event in self.funding_events:
                ts = event["time_ms"]
                if ts <= start_ms:
                    continue
                if ts > end_ms:
                    break
                rate = event["rate"]
                payment = notional * rate
                total += payment if side == "LONG" else -payment
            if total != 0.0:
                return total

        if self.funding_rate_per_hour == 0.0:
            return 0.0

        hours = (end_ms - start_ms) / 3_600_000
        if hours <= 0:
            return 0.0
        rate = self.funding_rate_per_hour * hours
        payment = notional * rate
        return payment if side == "LONG" else -payment

    def _resolve_order_timestamp(self, order: Dict, candle: Dict) -> Optional[int]:
        ts_str = order.get("timestamp")
        if ts_str:
            parsed = self._parse_timestamp_to_ms(ts_str)
            if parsed is not None:
                return parsed
        return candle.get("timestamp_ms")

    def _format_timestamp_ms(self, ts: Optional[int]) -> Optional[str]:
        if ts is None:
            return None
        try:
            return datetime.utcfromtimestamp(ts / 1000).isoformat()
        except Exception:
            return None

    def _load_exchange_profile(self, name: str) -> Dict[str, float]:
        """
        Carga la configuración del exchange desde tables/data/exchange_profiles.
        """
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

    def _load_funding_schedule(self, symbol: str) -> List[Dict[str, float]]:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "data", "funding_rates", f"{symbol}.csv")
        if not os.path.exists(path):
            return []

        events: List[Dict[str, float]] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    try:
                        ts = int(row.get("funding_time_ms") or row.get("funding_time") or 0)
                        rate = float(row.get("funding_rate", 0.0))
                    except Exception:
                        continue
                    events.append({"time_ms": ts, "rate": rate})
        except Exception as exc:
            self.logger.warning("No se pudo cargar funding rates para %s: %s", symbol, exc)
            return []

        events.sort(key=lambda e: e["time_ms"])
        return events

    def _parse_timestamp_to_ms(self, ts: str) -> Optional[int]:
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

    # ----------------------------------------------------
    # Internos
    # ----------------------------------------------------
    def _walk_to_outcome(
        self,
        side: str,
        start_index: int,
        tp_level: float,
        sl_level: float,
        liquidation_level: Optional[float],
    ) -> Tuple[str, float, int, str, bool, Optional[int]]:
        """
        Recorre velas futuras hasta que toque TP o SL. Política conservadora:
        • LONG : si en una vela se tocan ambos, se asume SL primero.
        • SHORT: idem (SL tiene prioridad).
        """
        bars = 0
        trigger_price = self.data[self._last_index]["close"] if self._last_index >= 0 else 0.0

        exit_timestamp_ms: Optional[int] = None

        for i in range(start_index, self.n):
            bars += 1
            c = self.data[i]
            high = float(c["high"])
            low = float(c["low"])
            exit_timestamp_ms = c.get("timestamp_ms")

            if side == "LONG":
                if liquidation_level is not None and low <= liquidation_level:
                    return "LOSS", liquidation_level, bars, "LIQUIDATION", True, exit_timestamp_ms
                # Priorizamos SL si low cruza primero
                if low <= sl_level:
                    return "LOSS", sl_level, bars, "SL", False, exit_timestamp_ms
                if high >= tp_level:
                    return "WIN", tp_level, bars, "TP", False, exit_timestamp_ms
            else:  # SHORT
                if liquidation_level is not None and high >= liquidation_level:
                    return "LOSS", liquidation_level, bars, "LIQUIDATION", True, exit_timestamp_ms
                if high >= sl_level:
                    return "LOSS", sl_level, bars, "SL", False, exit_timestamp_ms
                if low <= tp_level:
                    return "WIN", tp_level, bars, "TP", False, exit_timestamp_ms

        # Si nunca tocó (fin del dataset): cerramos por último precio (conservador = LOSS)
        last_price = float(self.data[self.n - 1]["close"]) if self.n > 0 else trigger_price
        exit_timestamp_ms = self.data[self.n - 1].get("timestamp_ms") if self.n > 0 else None
        return "LOSS", last_price, bars, "NO_EXIT", False, exit_timestamp_ms

    def _load_csv(self, path: str) -> List[Dict]:
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
                    # Saltar filas corruptas
                    continue
        return out

    def _infer_market_from_path(self, path: str) -> Tuple[str, str]:
        """
        Intenta inferir símbolo y timeframe desde el nombre del archivo.
        Ejemplo: 'LTCUSDT_15min_bull.csv' → ('LTCUSDT', '15min')
        """
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
