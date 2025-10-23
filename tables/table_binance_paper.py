"""
Realtime table that connects to Binance Futures USDⓈ-M Testnet.

Provides candles and routes real orders through the REST API.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional

import config
from tables.balance_manager import BalanceManager
from tables.position_manager import PositionManager
from tables.table_base import BaseTable
from utils.binance_env_loader import load_binance_credentials
from utils.binance_futures_client import BinanceFuturesClient, BinanceFuturesAPIError
from requests import exceptions as requests_exceptions
import socket


class TableBinancePaper(BaseTable):
    """Realtime table for Binance Futures paper trading."""

    def __init__(
        self,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        *,
        profile: str = "binance_futures_testnet",
        client: Optional[BinanceFuturesClient] = None,
        prefetch_candles: int = 500,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__(exchange_profile=profile)
        self.logger = logging.getLogger("TableBinancePaper")

        user_symbol = symbol or getattr(config, "BINANCE_DEFAULT_SYMBOL", "BTCUSDT")
        self.raw_symbol_input = user_symbol.strip().upper()
        self.interval = interval or getattr(config, "BINANCE_DEFAULT_INTERVAL", "15m")
        self.prefetch_candles = max(prefetch_candles, 50)
        self.poll_interval = poll_interval or getattr(config, "BINANCE_POLL_INTERVAL", 2.0)

        if client:
            self.client = client
        else:
            creds = load_binance_credentials(test_connection=False)
            self.client = BinanceFuturesClient(
                api_key=creds.get("api_key"),
                api_secret=creds.get("api_secret"),
                base_url=creds.get("base_url"),
            )

        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))
        self.position_manager = PositionManager()
        self._ghost_positions: Deque[Dict[str, Any]] = deque()
        self._last_activity = time.time()
        self._last_heartbeat = 0.0
        self.max_idle_seconds = getattr(config, "BINANCE_MAX_IDLE_SECONDS", 120)
        self.heartbeat_interval = getattr(config, "BINANCE_HEARTBEAT_INTERVAL", 60)
        self.max_retries = getattr(config, "BINANCE_MAX_RETRIES", 3)
        self.retry_backoff = getattr(config, "BINANCE_RETRY_BACKOFF", 2.0)
        self.retry_initial_delay = getattr(config, "BINANCE_RETRY_DELAY", 1.0)
        self._connection_state = "ONLINE"
        self._last_recovery = 0.0
        self.recovery_cooldown = getattr(config, "BINANCE_RECOVERY_COOLDOWN", 30.0)
        
        # Fetch exchange info to validate symbol and get properties
        self.exchange_info = self._call_with_retries(self.client.get_exchange_info)
        self.instrument = self._resolve_instrument(self.raw_symbol_input)
        self.symbol = self.instrument.get("symbol", self.raw_symbol_input)
        self.quantity_precision = int(self.instrument.get("quantityPrecision", 0))
        self.price_precision = int(self.instrument.get("pricePrecision", 6))
        self.quote_asset = self.instrument.get("quoteAsset", "USDT")
        self.balance_source = "Binance get_account_balance (futures wallet)"
        starting_balance = float(getattr(config, "STARTING_BALANCE", 0.0))
        self._balance_snapshot: Dict[str, float] = {
            "wallet_balance": starting_balance,
            "available_balance": starting_balance,
            "unrealized_pnl": 0.0,
            "equity": starting_balance,
        }

        lot_size_filter = next(
            (f for f in self.instrument.get("filters", []) if f.get("filterType") == "LOT_SIZE"),
            {},
        )
        self.min_qty = float(lot_size_filter.get("minQty", 0.0) or 0.0)
        self.step_size = float(lot_size_filter.get("stepSize", 0.0) or 0.0)
        self.taker_fee = float(self.profile.get("taker_fee", 0.0004))
        self.entry_fee_rate = float(self.profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.profile.get("exit_fee_rate", self.taker_fee))

        self._candle_queue: Deque[Dict[str, Any]] = deque()
        self._last_timestamp: Optional[int] = None
        self._pending_results: Deque[Dict[str, Any]] = deque()
        self.R = getattr(config, "TAKE_PROFIT", 0.01)
        self.L = getattr(config, "STOP_LOSS", 0.01)

        self._sync_balance_from_exchange()
        self._prime_cache(reset=True)

    def set_margin_type(self, symbol: str, margin_type: str) -> None:
        """Passes the set_margin_type call to the underlying client."""
        self.logger.info(f"Setting margin type for {symbol} to {margin_type}...")
        try:
            self._call_with_retries(self.client.set_margin_type, symbol, margin_type)
        except Exception as exc:
            self.logger.error("No se pudo configurar el margin type en Binance: %s", exc)

    def _resolve_instrument(self, symbol: str) -> Dict[str, Any]:
        for inst in self.exchange_info.get("symbols", []):
            if inst["symbol"] == symbol:
                return inst
        raise ValueError(f"Symbol {symbol} not found in Binance Futures exchange info.")

    # ------------------------------------------------------------------
    # Candle feed
    # ------------------------------------------------------------------
    def next_candle(self) -> Optional[Dict[str, Any]]:
        # Revisar si alguna orden reduce-only se ejecutó antes de procesar nueva vela
        self._check_reduce_orders()
        if not self._candle_queue:
            self.logger.info("Cache de velas procesado. Esperando nueva vela de %s...", self.interval)

        wait_marker = time.time()
        while not self._candle_queue:
            self._maybe_heartbeat()
            self._refresh_candles()
            if self._candle_queue:
                break
            idle_duration = time.time() - self._last_activity
            if idle_duration >= self.max_idle_seconds:
                self.logger.warning(
                    "Sin velas nuevas por %.1fs (umbral %.1fs). Forzando resincronización.",
                    idle_duration,
                    self.max_idle_seconds,
                )
                self._recover_feed()
            time.sleep(self.poll_interval)
            if time.time() - wait_marker > max(5.0, self.poll_interval * 2):
                self.logger.debug("Continuamos esperando vela de %s...", self.interval)
                wait_marker = time.time()

        candle = self._candle_queue.popleft()
        self._last_timestamp = candle["timestamp_ms"]
        self._last_activity = time.time()

        self._evaluate_open_position(candle)
        self._evaluate_ghost_positions(candle)

        state = self.balance_manager.get_state()
        return {
            "timestamp": candle["timestamp_iso"],
            "timestamp_ms": candle["timestamp_ms"],
            "symbol": candle["symbol"],
            "timeframe": self.interval,
            "market": f"{self.symbol}@{self.interval}",
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
            "equity": state.get("equity"),
            "balance": state.get("balance"),
        }

    def consume_completed_trades(self) -> list:
        """Devuelve y limpia los trades completados desde la última lectura."""
        results = list(self._pending_results)
        self._pending_results.clear()
        return results

    def _evaluate_open_position(self, candle: Dict[str, Any]) -> None:
        """Revisa si la vela actual cierra una posición abierta."""
        if not self.position_manager.is_position_open():
            return

        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return

        # Incrementar barras sostenidas
        bars_held = int(open_pos.misc.get("bars_held", 0)) + 1
        open_pos.misc["bars_held"] = bars_held

        manual_exit = bool(open_pos.misc.get("manual_exit"))

        if manual_exit:
            entry_candle_ts = open_pos.misc.get("entry_candle_timestamp")
            current_candle_ts = candle.get("timestamp")
            if entry_candle_ts and current_candle_ts and entry_candle_ts == current_candle_ts:
                self.logger.debug(
                    "Skip exit check on entry candle | ts=%s",
                    current_candle_ts,
                )
                return

            exit_signal = self.position_manager.check_exit(candle["high"], candle["low"])
            if not exit_signal:
                return

            exit_price = open_pos.take_profit_price if exit_signal == "TP" else open_pos.stop_loss_price
            reason = "take_profit" if exit_signal == "TP" else "stop_loss"

            self.logger.debug(
                "CHECK EXIT | %s | candle_high=%.4f candle_low=%.4f | TP=%.4f SL=%.4f",
                reason,
                candle["high"],
                candle["low"],
                open_pos.take_profit_price,
                open_pos.stop_loss_price,
            )

            result = self.close_open_position(exit_price, reason, bars_held=bars_held, candle_snapshot=candle)
            if result.get("status") == "ERROR":
                return

            result.setdefault("timestamp", candle.get("timestamp_iso"))
            result.setdefault("timeframe", self.interval)
            result.setdefault("market", f"{self.symbol}@{self.interval}")
            self._pending_results.append(result)
        else:
            self._check_reduce_orders()

    def _evaluate_ghost_positions(self, candle: Dict[str, Any]) -> None:
        """Simula el resultado de posiciones ghost para entrenamiento."""
        if not self._ghost_positions:
            return

        remaining: Deque[Dict[str, Any]] = deque()
        high_price = candle["high"]
        low_price = candle["low"]

        for ghost in list(self._ghost_positions):
            ghost["bars_held"] = int(ghost.get("bars_held", 0)) + 1
            exit_signal = None

            if ghost["side"] == "LONG":
                if low_price <= ghost["sl_price"]:
                    exit_signal = ("LOSS", ghost["sl_price"], "stop_loss")
                elif high_price >= ghost["tp_price"]:
                    exit_signal = ("WIN", ghost["tp_price"], "take_profit")
            else:
                if high_price >= ghost["sl_price"]:
                    exit_signal = ("LOSS", ghost["sl_price"], "stop_loss")
                elif low_price <= ghost["tp_price"]:
                    exit_signal = ("WIN", ghost["tp_price"], "take_profit")

            if exit_signal:
                outcome, exit_price, reason = exit_signal
                pnl_pct = self.R if outcome == "WIN" else (-self.L if outcome == "LOSS" else 0.0)

                result = {
                    "status": "CLOSED",
                    "trade_id": ghost.get("trade_id"),
                    "result": outcome,
                    "pnl": 0.0,
                    "pnl_net": 0.0,
                    "fee": 0.0,
                    "funding": 0.0,
                    "liquidated": False,
                    "exit_reason": reason,
                    "entry_price": ghost["entry_price"],
                    "exit_price": exit_price,
                    "size": 0.0,
                    "executed_qty": 0.0,
                    "size_fraction": ghost.get("size_fraction", 0.0),
                    "balance": float(self.balance_manager.get_state().get("balance", 0.0)),
                    "notional": float(ghost.get("notional", 0.0)),
                    "margin_used": 0.0,
                    "leverage": 0.0,
                    "pnl_pct": pnl_pct,
                    "bars_held": ghost.get("bars_held", 0),
                    "action": "GHOST",
                    "ghost": True,
                    "timestamp": candle.get("timestamp_iso"),
                    "timeframe": self.interval,
                    "market": f"{self.symbol}@{self.interval}",
                }
                self._pending_results.append(result)
            else:
                remaining.append(ghost)

        self._ghost_positions = remaining

    # ------------------------------------------------------------------
    # Order routing
    # ------------------------------------------------------------------
    def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Abre una nueva posición y la registra en el PositionManager."""
        if self.position_manager.is_position_open():
            self.logger.warning("Se ignoró la orden de apertura porque ya hay una posición abierta.")
            return {"status": "SKIPPED", "reason": "position_already_open", "result": "SKIPPED"}

        ghost = bool(order.get("ghost", False))
        if ghost:
            side = order.get("side", "").upper()
            if side not in {"LONG", "SHORT"}:
                return {"status": "ERROR", "reason": "invalid_side", "result": "ERROR"}

            try:
                price_info = self._call_with_retries(self.client.get_ticker_price, self.symbol)
                entry_price = float(price_info["price"])
            except (BinanceFuturesAPIError, KeyError, ValueError, Exception) as exc:
                self.logger.error("No se pudo obtener el precio actual de Binance para ghost: %s", exc)
                return {"status": "ERROR", "reason": "ghost_fetch_price_failed", "result": "ERROR"}

            tp_factor = float(order.get("take_profit", 1.0 + self.R))
            sl_factor = float(order.get("stop_loss", 1.0 - self.L))
            if side == "LONG":
                tp_price = entry_price * tp_factor
                sl_price = entry_price * sl_factor
            else:
                tp_price = entry_price * (2 - tp_factor) if tp_factor > 1 else entry_price * tp_factor
                sl_price = entry_price * (2 - sl_factor) if sl_factor < 1 else entry_price * sl_factor

            equity_state = self.balance_manager.get_state()
            equity = float(equity_state.get("equity", equity_state.get("balance", 0.0)))
            size_fraction = float(order.get("size", 0.0))
            notional = max(0.0, equity * size_fraction)

            ghost_state = {
                "trade_id": order.get("trade_id", ""),
                "side": side,
                "entry_price": entry_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "entry_timestamp": datetime.now(timezone.utc).isoformat(),
                "bars_held": 0,
                "size_fraction": size_fraction,
                "notional": notional,
                "timestamp": order.get("timestamp"),
            }
            self._ghost_positions.append(ghost_state)

            return {
                "status": "OPENED",
                "result": "OPENED",
                "trade_id": ghost_state["trade_id"],
                "ghost": True,
                "entry_price": entry_price,
                "size_fraction": size_fraction,
            }

        size_fraction = float(order.get("size", 0.0))
        if size_fraction <= 0.0:
            return {"status": "SKIPPED", "reason": "invalid_size", "result": "SKIPPED"}

        max_fraction = float(getattr(config, "MAX_POSITION_SIZE", 0.02))
        size_fraction = min(size_fraction, max_fraction)

        equity = float(self.balance_manager.get_state().get("equity", 0.0))
        if equity <= 0:
            return {"status": "SKIPPED", "reason": "no_equity", "result": "SKIPPED"}

        side = order.get("side", "").upper()
        if side not in {"LONG", "SHORT"}:
            return {"status": "ERROR", "reason": "invalid_side", "result": "ERROR"}

        # Fetch current price to calculate quantity
        try:
            price_info = self._call_with_retries(self.client.get_ticker_price, self.symbol)
            entry_price = float(price_info["price"])
        except (BinanceFuturesAPIError, KeyError, ValueError, Exception) as exc:
            self.logger.error("No se pudo obtener el precio actual de Binance: %s", exc)
            return {"status": "ERROR", "reason": "fetch_price_failed", "result": "ERROR"}

        desired_notional = equity * size_fraction
        max_notional = equity * max_fraction
        if desired_notional <= 0 or max_notional <= 0 or entry_price <= 0:
            return {"status": "SKIPPED", "reason": "invalid_notional", "result": "SKIPPED"}

        max_notional = min(desired_notional, max_notional)
        raw_quantity = max_notional / entry_price

        quantity = self._adjust_quantity_to_precision(raw_quantity)
        max_qty_allowed = self._adjust_quantity_to_precision((equity * max_fraction) / entry_price)
        if max_qty_allowed > 0:
            quantity = min(quantity, max_qty_allowed)
            quantity = self._adjust_quantity_to_precision(quantity)

        if max_qty_allowed <= 0 or (self.min_qty and max_qty_allowed < self.min_qty):
            self.logger.warning("Max quantity permitido insuficiente para cumplir minQty del exchange.")
            return {"status": "SKIPPED", "reason": "quantity_below_min", "result": "SKIPPED"}

        if quantity <= 0:
            self.logger.warning("La cantidad calculada es 0 después de ajustar precisión y límites.")
            return {"status": "SKIPPED", "reason": "quantity_too_low", "result": "SKIPPED"}

        if self.min_qty and quantity < self.min_qty:
            self.logger.warning(
                "Cantidad ajustada %.8f menor al mínimo permitido %.8f. Trade omitido.",
                quantity,
                self.min_qty,
            )
            return {"status": "SKIPPED", "reason": "quantity_below_min", "result": "SKIPPED"}

        actual_notional = quantity * entry_price
        actual_fraction = actual_notional / equity if equity > 0 else 0.0
        if actual_fraction > max_fraction + 1e-9:
            self.logger.warning(
                "Cantidad ajustada %.8f excede MAX_POSITION_SIZE (%.4f). Trade omitido.",
                quantity,
                max_fraction,
            )
            return {"status": "SKIPPED", "reason": "quantity_above_max", "result": "SKIPPED"}

        payload = {
            "symbol": self.symbol,
            "side": "BUY" if side == "LONG" else "SELL",
            "type": "MARKET",
            "quantity": str(quantity),
        }

        leverage_override = order.get("leverage") or getattr(config, "MAX_LEVERAGE", 10)
        try:
            leverage_override = int(leverage_override)
        except (TypeError, ValueError):
            leverage_override = int(getattr(config, "MAX_LEVERAGE", 10))
        leverage_override = max(1, min(leverage_override, int(getattr(config, "MAX_LEVERAGE", 10))))

        try:
            self.logger.debug("Setting leverage for %s to %s", self.symbol, leverage_override)
            self._call_with_retries(self.client.set_leverage, self.symbol, leverage_override)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Binance Futures rechazó set_leverage: %s", exc)
            return {"status": "ERROR", "reason": "set_leverage_failed", "details": str(exc), "result": "ERROR"}
        except Exception as exc:
            self.logger.error("Error estableciendo leverage en Binance: %s", exc)
            return {"status": "ERROR", "reason": "set_leverage_failed", "details": str(exc), "result": "ERROR"}

        try:
            response = self._call_with_retries(self.client.create_order, payload)
            self.logger.debug("Binance create_order payload=%s response=%s", payload, response)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Binance Futures rechazó la orden: %s", exc)
            return {"status": "ERROR", "reason": "api_error", "details": str(exc), "result": "ERROR"}
        except Exception as exc:
            self.logger.error("Error al crear la orden en Binance: %s", exc)
            return {"status": "ERROR", "reason": "api_error", "details": str(exc), "result": "ERROR"}

        order_id = response.get("orderId")
        fill_info = self._fetch_order_fill(order_id)

        try:
            executed_qty = float(fill_info.get("executed_qty", 0.0))
        except (TypeError, ValueError):
            executed_qty = 0.0
        if executed_qty <= 0:
            executed_qty = quantity
        executed_qty = self._adjust_quantity_to_precision(executed_qty)
        if executed_qty <= 0:
            self.logger.error("La orden en Binance no devolvió cantidad ejecutada válida. fill=%s", fill_info)
            return {"status": "ERROR", "reason": "execution_qty_zero", "result": "ERROR"}

        try:
            fill_avg_price = float(fill_info.get("avg_price", 0.0))
        except (TypeError, ValueError):
            fill_avg_price = 0.0
        if fill_avg_price > 0:
            entry_price = fill_avg_price

        try:
            fill_cum_quote = float(fill_info.get("cum_quote", 0.0))
        except (TypeError, ValueError):
            fill_cum_quote = 0.0
        if fill_cum_quote > 0:
            actual_notional = fill_cum_quote
        else:
            actual_notional = entry_price * executed_qty

        actual_fraction = actual_notional / equity if equity > 0 else 0.0

        tp_factor = float(order.get("take_profit", 1.0))
        sl_factor = float(order.get("stop_loss", 1.0))
        tp_price = entry_price * tp_factor if side == "LONG" else (
            entry_price * (2 - tp_factor) if tp_factor > 1 else entry_price * tp_factor
        )
        sl_price = entry_price * sl_factor if side == "LONG" else (
            entry_price * (2 - sl_factor) if sl_factor < 1 else entry_price * sl_factor
        )

        leverage = float(order.get("leverage") or getattr(config, "MAX_LEVERAGE", 10))
        leverage = max(1.0, min(leverage, getattr(config, "MAX_LEVERAGE", 10)))
        margin_used = actual_notional / leverage if leverage > 0 else actual_notional

        self.position_manager.open_position(
            symbol=self.symbol,
            side=side,
            size_contracts=executed_qty,
            entry_price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            entry_timestamp=datetime.now(timezone.utc).isoformat(),
            trade_id=order.get("trade_id", ""),
            misc={
                "order_id": order_id,
                "executed_qty": executed_qty,
                "size_fraction": actual_fraction,
                "notional": actual_notional,
                "margin_used": margin_used,
                "leverage": leverage,
                "bars_held": 0,
                "ghost": ghost,
                "entry_candle_timestamp": order.get("timestamp"),
            },
        )

        self.logger.info(
            "POSICIÓN ABIERTA: %s %.8f %s @ %.4f | TP=%.4f | SL=%.4f | size_frac=%.6f",
            side,
            executed_qty,
            self.symbol,
            entry_price,
            tp_price,
            sl_price,
            actual_fraction,
        )

        reduce_orders = self._place_reduce_orders(
            entry_side=side,
            executed_qty=executed_qty,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
        )
        open_pos_ref = self.position_manager.get_open_position()
        if open_pos_ref:
            if reduce_orders:
                open_pos_ref.misc.setdefault("reduce_orders", {}).update(reduce_orders)
                open_pos_ref.misc["manual_exit"] = not any(reduce_orders.values())
            else:
                open_pos_ref.misc["manual_exit"] = True
        
        return {
            "status": "OPENED",
            "result": "OPENED",
            "order_id": order_id,
            "response": response,
            "executed_qty": executed_qty,
            "entry_price": entry_price,
            "size_fraction": actual_fraction,
            "notional": actual_notional,
        }

    def close_open_position(
        self,
        exit_price: float,
        reason: str,
        bars_held: Optional[int] = None,
        candle_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Cierra la posición abierta y calcula el resultado."""
        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return {"status": "ERROR", "reason": "no_position_to_close"}

        # Cancelar órdenes reduce-only existentes
        self._cancel_reduce_orders(open_pos)

        close_side = "SELL" if open_pos.side == "LONG" else "BUY"
        quantity = self._adjust_quantity_to_precision(open_pos.size_contracts)

        payload = {
            "symbol": self.symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": str(quantity),
        }

        try:
            response = self._call_with_retries(self.client.create_order, payload)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Error al cerrar posición en Binance: %s", exc)
            return {"status": "ERROR", "reason": "close_api_error", "details": str(exc)}
        except Exception as exc:
            self.logger.error("Error inesperado al cerrar posición en Binance: %s", exc)
            return {"status": "ERROR", "reason": "close_api_error", "details": str(exc)}

        fill_info = self._fetch_order_fill(response.get("orderId"))
        try:
            executed_qty = float(fill_info.get("executed_qty", 0.0))
        except (TypeError, ValueError):
            executed_qty = 0.0
        if executed_qty <= 0:
            executed_qty = open_pos.size_contracts

        executed_qty = self._adjust_quantity_to_precision(executed_qty)

        try:
            exit_price_actual = float(fill_info.get("avg_price", 0.0))
        except (TypeError, ValueError):
            exit_price_actual = 0.0
        if exit_price_actual <= 0:
            exit_price_actual = exit_price

        try:
            exit_cum_quote = float(fill_info.get("cum_quote", 0.0))
        except (TypeError, ValueError):
            exit_cum_quote = 0.0
        result = self._finalize_trade(
            open_pos,
            exit_price_actual,
            executed_qty,
            exit_cum_quote,
            reason,
            candle_snapshot=candle_snapshot,
            bars_held=bars_held,
            order_info=fill_info,
        )
        return result

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, float]:
        state = self.balance_manager.get_state()
        return {
            "balance": float(state.get("balance", 0.0)),
            "equity": float(state.get("equity", state.get("balance", 0.0))),
            "currency": self.quote_asset,
            "available_balance": float(self._balance_snapshot.get("available_balance", state.get("balance", 0.0))),
            "unrealized_pnl": float(self._balance_snapshot.get("unrealized_pnl", 0.0)),
            "wallet_balance": float(self._balance_snapshot.get("wallet_balance", state.get("balance", 0.0))),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _adjust_quantity_to_precision(self, quantity: float) -> float:
        """Adjust quantity to comply with Binance Futures precision and lot size."""
        if quantity <= 0:
            return 0.0

        adjusted = quantity

        if self.step_size:
            steps = math.floor(adjusted / self.step_size)
            adjusted = steps * self.step_size

        if self.quantity_precision is not None:
            factor = 10 ** int(self.quantity_precision)
            adjusted = math.floor(adjusted * factor) / factor

        return max(adjusted, 0.0)

    def _format_price(self, price: float) -> str:
        precision = getattr(self, "price_precision", 6)
        fmt = "{:." + str(precision) + "f}"
        return fmt.format(price)

    def _format_quantity(self, quantity: float) -> str:
        precision = max(int(getattr(self, "quantity_precision", 0)), 0)
        fmt = "{:." + str(precision) + "f}"
        return fmt.format(quantity)

    def _place_reduce_orders(
        self,
        *,
        entry_side: str,
        executed_qty: float,
        take_profit_price: float,
        stop_loss_price: float,
    ) -> Dict[str, Optional[int]]:
        """Intenta colocar órdenes reduce-only para TP y SL."""
        orders: Dict[str, Optional[int]] = {}
        if executed_qty <= 0:
            return orders

        exit_side = "SELL" if entry_side == "LONG" else "BUY"
        qty_str = self._format_quantity(executed_qty)

        # Take Profit order
        if take_profit_price and take_profit_price > 0:
            tp_payload = {
                "symbol": self.symbol,
                "side": exit_side,
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": self._format_price(take_profit_price),
                "quantity": qty_str,
                "reduceOnly": "true",
                "timeInForce": "GTC",
                "workingType": "CONTRACT_PRICE",
            }
            try:
                tp_response = self._call_with_retries(
                    self.client.create_order,
                    tp_payload,
                    max_attempts=1,
                    allow_reset=False,
                )
                orders["tp_order_id"] = tp_response.get("orderId")
            except Exception as exc:  # pragma: no cover - logging
                self.logger.warning("No se pudo colocar TP reduce-only: %s", exc)

        # Stop Loss order
        if stop_loss_price and stop_loss_price > 0:
            sl_payload = {
                "symbol": self.symbol,
                "side": exit_side,
                "type": "STOP_MARKET",
                "stopPrice": self._format_price(stop_loss_price),
                "quantity": qty_str,
                "reduceOnly": "true",
                "timeInForce": "GTC",
                "workingType": "CONTRACT_PRICE",
            }
            try:
                sl_response = self._call_with_retries(
                    self.client.create_order,
                    sl_payload,
                    max_attempts=1,
                    allow_reset=False,
                )
                orders["sl_order_id"] = sl_response.get("orderId")
            except Exception as exc:  # pragma: no cover - logging
                self.logger.warning("No se pudo colocar SL reduce-only: %s", exc)

        return orders

    def _check_reduce_orders(self) -> None:
        if not self.position_manager.is_position_open():
            return

        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return

        reduce_orders = dict(open_pos.misc.get("reduce_orders") or {})
        if not reduce_orders:
            return

        for kind in ("tp_order_id", "sl_order_id"):
            order_id = reduce_orders.get(kind)
            if not order_id:
                continue
            try:
                order_info = self._call_with_retries(
                    self.client.get_order,
                    self.symbol,
                    int(order_id),
                    max_attempts=1,
                    allow_reset=False,
                )
            except Exception as exc:  # pragma: no cover - logging
                self.logger.debug("No se pudo consultar reduce order %s: %s", order_id, exc)
                continue

            status = (order_info.get("status") or "").upper()
            if status == "FILLED":
                exit_reason = "take_profit" if kind == "tp_order_id" else "stop_loss"
                result = self._finalize_reduce_order(order_info, exit_reason)
                if result:
                    self._pending_results.append(result)
                return
            elif status in {"CANCELED", "REJECTED", "EXPIRED"}:
                reduce_orders[kind] = None
        open_pos.misc["reduce_orders"] = reduce_orders

    def _cancel_reduce_orders(self, open_pos, exclude: Optional[str] = None) -> None:
        reduce_orders = dict(open_pos.misc.get("reduce_orders") or {})
        for kind_key in ("tp_order_id", "sl_order_id"):
            if exclude and kind_key == exclude:
                continue
            order_id = reduce_orders.get(kind_key)
            if not order_id:
                continue
            try:
                self._call_with_retries(
                    self.client.cancel_order,
                    self.symbol,
                    order_id=int(order_id),
                    max_attempts=1,
                    allow_reset=False,
                )
            except Exception as exc:  # pragma: no cover - logging
                self.logger.debug("No se pudo cancelar reduce order %s: %s", order_id, exc)
        reduce_orders.clear()
        open_pos.misc["reduce_orders"] = reduce_orders

    def _finalize_reduce_order(self, order_info: Dict[str, Any], reason: str) -> Optional[Dict[str, Any]]:
        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return None

        reduce_orders = open_pos.misc.get("reduce_orders") or {}
        filled_kind = None
        for key, value in reduce_orders.items():
            if value and str(value) == str(order_info.get("orderId")):
                filled_kind = key
                break

        # Cancel la otra orden pendiente
        if filled_kind == "tp_order_id":
            self._cancel_reduce_orders(open_pos, exclude="tp_order_id")
        elif filled_kind == "sl_order_id":
            self._cancel_reduce_orders(open_pos, exclude="sl_order_id")
        else:
            self._cancel_reduce_orders(open_pos)

        try:
            executed_qty = float(order_info.get("executedQty", 0.0))
        except (TypeError, ValueError):
            executed_qty = 0.0
        if executed_qty <= 0:
            executed_qty = float(open_pos.size_contracts)

        try:
            exit_price_actual = float(order_info.get("avgPrice", 0.0))
        except (TypeError, ValueError):
            exit_price_actual = 0.0
        if exit_price_actual <= 0:
            try:
                exit_price_actual = float(order_info.get("stopPrice", 0.0))
            except (TypeError, ValueError):
                exit_price_actual = float(open_pos.take_profit_price if reason == "take_profit" else open_pos.stop_loss_price)

        try:
            exit_notional = float(order_info.get("cumQuote", 0.0))
        except (TypeError, ValueError):
            exit_notional = 0.0

        return self._finalize_trade(open_pos, exit_price_actual, executed_qty, exit_notional, reason, candle_snapshot=None, order_info=order_info)

    def _finalize_trade(
        self,
        open_pos,
        exit_price_actual: float,
        executed_qty: float,
        exit_notional: float,
        reason: str,
        candle_snapshot: Optional[Dict[str, Any]] = None,
        bars_held: Optional[int] = None,
        order_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry_price_actual = float(open_pos.entry_price)
        executed_qty = self._adjust_quantity_to_precision(executed_qty)
        if executed_qty <= 0:
            executed_qty = float(open_pos.size_contracts)

        entry_notional = float(open_pos.misc.get("notional", entry_price_actual * open_pos.size_contracts))
        exit_notional = exit_notional if exit_notional and exit_notional > 0 else exit_price_actual * executed_qty

        entry_fee = entry_notional * self.entry_fee_rate
        exit_fee = exit_notional * self.exit_fee_rate
        fee = entry_fee + exit_fee

        if open_pos.side == "LONG":
            gross_pnl = (exit_price_actual - entry_price_actual) * executed_qty
        else:
            gross_pnl = (entry_price_actual - exit_price_actual) * executed_qty

        net_pnl = gross_pnl - fee

        self.balance_manager.apply_trade_result(pnl=net_pnl, fee=0)
        self._sync_balance_from_exchange()

        balance_state = self.balance_manager.get_state()
        balance_after = float(balance_state.get("balance", 0.0))

        pnl_pct = 0.0
        if entry_price_actual:
            if open_pos.side == "LONG":
                pnl_pct = (exit_price_actual - entry_price_actual) / entry_price_actual
            else:
                pnl_pct = (entry_price_actual - exit_price_actual) / entry_price_actual

        bar_count = bars_held if bars_held is not None else int(open_pos.misc.get("bars_held", 0))

        self.logger.debug(
            "CLOSE DETAILS | side=%s | entry=%.4f | exit=%.4f | qty=%.8f | candle_high=%s | candle_low=%s",
            open_pos.side,
            entry_price_actual,
            exit_price_actual,
            executed_qty,
            candle_snapshot.get("high") if isinstance(candle_snapshot, dict) else None,
            candle_snapshot.get("low") if isinstance(candle_snapshot, dict) else None,
        )

        self.logger.info(
            "POSICIÓN CERRADA: %s %.3f %s | PnL Bruto: %.4f, Fee: %.4f, PnL Neto: %.4f",
            open_pos.side,
            executed_qty,
            self.symbol,
            gross_pnl,
            fee,
            net_pnl,
        )

        result = {
            "status": "CLOSED",
            "trade_id": open_pos.trade_id,
            "result": "WIN" if net_pnl > 0 else "LOSS",
            "pnl": gross_pnl,
            "pnl_net": net_pnl,
            "fee": fee,
            "funding": 0.0,
            "liquidated": False,
            "exit_reason": reason,
            "entry_price": entry_price_actual,
            "exit_price": exit_price_actual,
            "size": executed_qty,
            "executed_qty": executed_qty,
            "size_fraction": float(open_pos.misc.get("size_fraction", 0.0)),
            "balance": balance_after,
            "notional": float(open_pos.misc.get("notional", exit_notional)),
            "exit_notional": exit_notional,
            "margin_used": float(open_pos.misc.get("margin_used", 0.0)),
            "leverage": float(open_pos.misc.get("leverage", 1.0)),
            "pnl_pct": pnl_pct,
            "bars_held": bar_count,
            "action": "BET",
            "ghost": bool(open_pos.misc.get("ghost", False)),
            "raw_close_response": order_info,
        }

        # Limpiar y cerrar posición
        open_pos.misc["reduce_orders"] = {}
        self.position_manager.close_position()

        result.setdefault("timestamp", candle_snapshot.get("timestamp") if candle_snapshot else None)
        result.setdefault("timeframe", self.interval)
        result.setdefault("market", f"{self.symbol}@{self.interval}")

        if not result.get("timestamp") and order_info:
            try:
                update_ms = int(order_info.get("updateTime") or order_info.get("time") or 0)
            except (TypeError, ValueError):
                update_ms = 0
            if update_ms:
                result["timestamp"] = datetime.fromtimestamp(update_ms / 1000, tz=timezone.utc).isoformat()

        return result

    def _call_with_retries(
        self,
        func,
        *args,
        max_attempts: Optional[int] = None,
        allow_reset: bool = True,
        **kwargs,
    ):
        """Wraps Binance client calls with retries and backoff."""
        attempts = max_attempts or max(1, int(self.max_retries))
        delay = max(0.1, float(self.retry_initial_delay))
        last_exc: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                return func(*args, **kwargs)
            except (
                BinanceFuturesAPIError,
                requests_exceptions.RequestException,
                ConnectionError,
                TimeoutError,
                socket.timeout,
                OSError,
            ) as exc:
                last_exc = exc
                self.logger.warning(
                    "Error llamando a Binance (%s/%s intentos): %s",
                    attempt,
                    attempts,
                    exc,
                )
                if attempt >= attempts:
                    if allow_reset:
                        self._handle_connection_issue(exc)
                    raise
                time.sleep(delay)
                delay *= float(self.retry_backoff)

        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected estado en _call_with_retries sin excepción previa.")

    def _fetch_order_fill(
        self,
        order_id: Optional[int],
        *,
        timeout: float = 2.0,
        poll_interval: float = 0.05,
    ) -> Dict[str, float]:
        """Obtiene información de llenado (avgPrice, executedQty) para un orderId."""
        info: Dict[str, float] = {
            "avg_price": 0.0,
            "executed_qty": 0.0,
            "cum_quote": 0.0,
        }
        if not order_id:
            return info

        deadline = time.time() + max(timeout, 0.1)
        last_payload: Dict[str, Any] = {}
        while time.time() < deadline:
            try:
                order_payload = self._call_with_retries(
                    self.client.get_order,
                    self.symbol,
                    order_id=int(order_id),
                    max_attempts=1,
                    allow_reset=False,
                )
            except Exception as exc:  # pragma: no cover - defensivo
                self.logger.debug("No se pudo obtener fill del order %s: %s", order_id, exc)
                break

            if not isinstance(order_payload, dict):
                time.sleep(poll_interval)
                continue

            last_payload = order_payload
            try:
                executed_qty = float(order_payload.get("executedQty", 0.0))
            except (TypeError, ValueError):
                executed_qty = 0.0
            try:
                avg_price = float(order_payload.get("avgPrice", 0.0))
            except (TypeError, ValueError):
                avg_price = 0.0
            try:
                cum_quote = float(
                    order_payload.get("cumQuote")
                    or order_payload.get("cumExecValue")
                    or 0.0
                )
            except (TypeError, ValueError):
                cum_quote = 0.0

            status = (order_payload.get("status") or "").upper()
            if executed_qty > 0 and avg_price <= 0 and cum_quote > 0:
                avg_price = cum_quote / executed_qty
            info.update({
                "avg_price": avg_price,
                "executed_qty": executed_qty,
                "cum_quote": cum_quote,
                "status": status,
            })

            if executed_qty > 0 and (avg_price > 0 or status in {"FILLED", "PARTIALLY_FILLED"}):
                return info

            time.sleep(poll_interval)

        if last_payload:
            try:
                executed_qty = float(last_payload.get("executedQty", 0.0))
            except (TypeError, ValueError):
                executed_qty = info.get("executed_qty", 0.0)
            try:
                avg_price = float(last_payload.get("avgPrice", 0.0))
            except (TypeError, ValueError):
                avg_price = info.get("avg_price", 0.0)
            try:
                cum_quote = float(
                    last_payload.get("cumQuote")
                    or last_payload.get("cumExecValue")
                    or 0.0
                )
            except (TypeError, ValueError):
                cum_quote = info.get("cum_quote", 0.0)
            if executed_qty > 0 and avg_price <= 0 and cum_quote > 0:
                avg_price = cum_quote / executed_qty
            info.update({
                "avg_price": avg_price,
                "executed_qty": executed_qty,
                "cum_quote": cum_quote,
            })
        return info

    def _maybe_heartbeat(self) -> None:
        if self.heartbeat_interval <= 0:
            return
        now = time.time()
        if now - self._last_heartbeat < self.heartbeat_interval:
            return

        self._last_heartbeat = now
        try:
            self._call_with_retries(
                self.client.get_exchange_info,
                max_attempts=1,
                allow_reset=False,
            )
            self._connection_state = "ONLINE"
        except Exception as exc:
            self.logger.debug("Heartbeat Binance falló: %s", exc)
            self._connection_state = "DEGRADED"

    def _recover_feed(self) -> None:
        now = time.time()
        if now - self._last_recovery < self.recovery_cooldown:
            return

        self._last_recovery = now
        self.logger.info("Intentando resincronizar feed de velas con Binance…")
        self._prime_cache(reset=True, allow_reset=False)

    def _handle_connection_issue(self, exc: Exception) -> None:
        self.logger.error("Max reintentos alcanzados para llamada Binance: %s", exc)
        self._connection_state = "DEGRADED"
        now = time.time()
        if now - self._last_recovery < self.recovery_cooldown:
            self.logger.debug("Saltando recreación de cliente por cooldown activo.")
            return
        self._last_recovery = now
        try:
            self._recreate_client()
        except Exception as recreate_exc:
            self.logger.error("Fallo al recrear cliente de Binance: %s", recreate_exc)

    def _recreate_client(self) -> None:
        self.logger.info("Recreando cliente de Binance y resincronizando estado…")
        creds = load_binance_credentials(test_connection=False)
        self.client = BinanceFuturesClient(
            api_key=creds.get("api_key"),
            api_secret=creds.get("api_secret"),
            base_url=creds.get("base_url"),
        )

        # Re-descargar metadatos del instrumento para garantizar consistencia
        try:
            self.exchange_info = self.client.get_exchange_info()
        except Exception as exc:
            self.logger.error("No se pudo obtener exchangeInfo al recrear cliente: %s", exc)
            raise
        self.instrument = self._resolve_instrument(self.raw_symbol_input)
        self.symbol = self.instrument.get("symbol", self.raw_symbol_input)
        self.quantity_precision = int(self.instrument.get("quantityPrecision", 0))
        self.quote_asset = self.instrument.get("quoteAsset", self.quote_asset)

        lot_size_filter = next(
            (f for f in self.instrument.get("filters", []) if f.get("filterType") == "LOT_SIZE"),
            {},
        )
        self.min_qty = float(lot_size_filter.get("minQty", 0.0) or 0.0)
        self.step_size = float(lot_size_filter.get("stepSize", 0.0) or 0.0)
        self.taker_fee = float(self.profile.get("taker_fee", 0.0004))
        self.entry_fee_rate = float(self.profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.profile.get("exit_fee_rate", self.taker_fee))

        self._candle_queue.clear()
        self._last_timestamp = None
        self._last_activity = time.time()
        self._connection_state = "RECOVERING"
        self._sync_balance_from_exchange()
        self._prime_cache(reset=True, allow_reset=False)

    def _prime_cache(self, reset: bool = False, allow_reset: bool = True) -> None:
        if reset:
            self._candle_queue.clear()
            self._last_timestamp = None

        try:
            klines = self._call_with_retries(
                self.client.get_klines,
                self.symbol,
                self.interval,
                limit=self.prefetch_candles,
                allow_reset=allow_reset,
            )
        except Exception as exc:
            self.logger.error("Could not prefetch candles from Binance: %s", exc)
            self._connection_state = "DEGRADED"
            return

        for kline in klines:
            normalized = self._normalize_candle(kline)
            self._candle_queue.append(normalized)
            self._last_timestamp = normalized["timestamp_ms"]

        if self._candle_queue:
            self._last_activity = time.time()
            self._connection_state = "ONLINE"

    def _refresh_candles(self) -> None:
        params: Dict[str, Any] = {}
        if self._last_timestamp:
            params["startTime"] = self._last_timestamp + 1

        try:
            klines = self._call_with_retries(
                self.client.get_klines,
                self.symbol,
                self.interval,
                limit=500,
                **params,
            )
        except Exception as exc:
            self.logger.error("Error fetching candles from Binance tras reintentos: %s", exc)
            self._connection_state = "DEGRADED"
            return

        new_count = 0
        for kline in klines:
            normalized = self._normalize_candle(kline)
            if self._last_timestamp and normalized["timestamp_ms"] <= self._last_timestamp:
                continue
            self._candle_queue.append(normalized)
            self._last_timestamp = normalized["timestamp_ms"]
            new_count += 1

        if new_count:
            self._last_activity = time.time()
            self._connection_state = "ONLINE"

    def _normalize_candle(self, kline: list) -> Dict[str, Any]:
        ts_ms = int(kline[0])
        return {
            "timestamp_ms": ts_ms,
            "timestamp_iso": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat(),
            "symbol": self.symbol,
            "open": float(kline[1]),
            "high": float(kline[2]),
            "low": float(kline[3]),
            "close": float(kline[4]),
            "volume": float(kline[5]),
        }

    def _sync_balance_from_exchange(self) -> None:
        try:
            balances = self._call_with_retries(self.client.get_account_balance)
        except Exception as exc:
            self.logger.error("Could not sync balance with Binance: %s", exc)
            return

        for asset in balances:
            if asset.get("asset") != self.quote_asset:
                continue

            wallet_balance = float(
                asset.get("walletBalance")
                or asset.get("balance")
                or asset.get("crossWalletBalance")
                or 0.0
            )
            available_balance = float(
                asset.get("availableBalance")
                or asset.get("maxWithdrawAmount")
                or wallet_balance
            )
            unrealized_pnl = float(
                asset.get("crossUnPnl")
                or asset.get("unrealizedProfit")
                or 0.0
            )
            equity = wallet_balance + unrealized_pnl

            self.balance_manager.balance = wallet_balance
            self.balance_manager.equity = equity
            self._balance_snapshot.update(
                {
                    "wallet_balance": wallet_balance,
                    "available_balance": available_balance,
                    "unrealized_pnl": unrealized_pnl,
                    "equity": equity,
                }
            )
            break

    def close_all_positions(self) -> None:
        self.logger.info("Closing all open orders on Binance...")
        if self.position_manager.is_position_open():
            try:
                price_info = self._call_with_retries(self.client.get_ticker_price, self.symbol)
                last_price = float(price_info["price"])
            except Exception as exc:  # pragma: no cover - defensivo
                self.logger.error("Failed to fetch price while closing position: %s", exc)
                last_price = float(self.position_manager.get_open_position().entry_price)

            result = self.close_open_position(last_price, "session_shutdown")
            if result.get("status") != "ERROR":
                result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                result.setdefault("timeframe", self.interval)
                result.setdefault("market", f"{self.symbol}@{self.interval}")
                self._pending_results.append(result)

        try:
            open_orders = self._call_with_retries(self.client.get_open_orders, self.symbol)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Failed to fetch open orders for cleanup: %s", exc)
            open_orders = []
        except Exception as exc:
            self.logger.error("Unexpected error fetching open orders: %s", exc)
            open_orders = []

        for order in open_orders:
            order_id = order.get("orderId")
            if order_id:
                try:
                    self._call_with_retries(self.client.cancel_order, symbol=self.symbol, order_id=order_id)
                    self.logger.info(f"Cancelled open order {order_id}.")
                except BinanceFuturesAPIError as exc:
                    self.logger.error(f"Failed to cancel order {order_id}: {exc}")
                except Exception as exc:
                    self.logger.error(f"Unexpected error cancelling order {order_id}: {exc}")

        # Actualizar snapshot después de asegurarnos que no quedan posiciones abiertas
        self._sync_balance_from_exchange()
