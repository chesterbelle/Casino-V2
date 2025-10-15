"""
Realtime table that connects to Kraken Futures (demo environment by default).

Provides candles via the charts API and routes real orders through the REST trading API.
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
from utils.kraken_env_loader import load_kraken_credentials
from utils.kraken_futures_client import KrakenFuturesClient, KrakenFuturesAPIError


class TableKrakenPaper(BaseTable):
    """Mesa realtime para Kraken Futures (demo paper trading)."""

    def __init__(
        self,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        *,
        profile: str = "kraken_futures_demo",
        client: Optional[KrakenFuturesClient] = None,
        prefetch_candles: int = 500,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__(exchange_profile=profile)
        self.logger = logging.getLogger("TableKrakenPaper")

        user_symbol = symbol or getattr(config, "KRAKEN_FUTURES_SYMBOL", "PF_XBTUSD")
        self.raw_symbol_input = user_symbol.strip().upper()
        self.interval = self._normalize_interval(interval or getattr(config, "KRAKEN_FUTURES_INTERVAL", "1m"))
        self.prefetch_candles = max(prefetch_candles, 50)
        self.poll_interval = poll_interval or getattr(config, "KRAKEN_POLL_INTERVAL", 2.0)

        if client:
            self.client = client
        else:
            creds = load_kraken_credentials(test_connection=False)
            self.client = KrakenFuturesClient(
                api_key=creds.get("api_key"),
                api_secret=creds.get("api_secret"),
                base_url=creds.get("base_url"),
                charts_url=creds.get("charts_url"),
            )

        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))
        self.position_manager = PositionManager()
        self.instrument = self._resolve_instrument(self.raw_symbol_input)
        self.symbol = self.instrument.get("symbol", self.raw_symbol_input)
        self.contract_size = float(self.instrument.get("contractSize", 1.0) or 1.0)
        self.taker_fee = float(self.profile.get("taker_fee", getattr(config, "COMMISSION_RATE", 0.0005)))
        self.entry_fee_rate = float(self.profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.profile.get("exit_fee_rate", self.taker_fee))

        self._candle_queue: Deque[Dict[str, Any]] = deque()
        self._last_timestamp: Optional[int] = None

        self._sync_balance_from_exchange()
        self._prime_cache()

    # ------------------------------------------------------------------
    # Candle feed
    # ------------------------------------------------------------------
    def next_candle(self) -> Optional[Dict[str, Any]]:
        while not self._candle_queue:
            self._refresh_candles()
            if not self._candle_queue:
                time.sleep(self.poll_interval)

        candle = self._candle_queue.popleft()
        self._last_timestamp = candle["timestamp_ms"]

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

    # ------------------------------------------------------------------
    # Order routing
    # ------------------------------------------------------------------
    def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Abre una nueva posición y la registra en el PositionManager."""
        if self.position_manager.is_position_open():
            self.logger.warning("Se ignoró la orden de apertura porque ya hay una posición abierta.")
            return {"status": "SKIPPED", "reason": "position_already_open"}

        ghost = bool(order.get("ghost", False))
        if ghost:
            return {"status": "SKIPPED", "reason": "ghost_order"}

        if not self.client.api_key or not self.client.api_secret:
            self.logger.warning("Orden real omitida: faltan credenciales de Kraken Futures.")
            return {"status": "SKIPPED", "reason": "missing_credentials"}

        size_fraction = float(order.get("size", 0.0))
        if size_fraction <= 0.0:
            self.logger.warning("Orden con tamaño inválido (size_fraction=%s).", size_fraction)
            return {"status": "SKIPPED", "reason": "invalid_size"}

        equity = float(self.balance_manager.get_state().get("equity", 0.0))
        if equity <= 0:
            self.logger.warning("Equity no disponible para calcular riesgo.")
            return {"status": "SKIPPED", "reason": "no_equity"}

        entry_price = self._fetch_mark_price()
        if entry_price <= 0:
            self.logger.error("No se pudo obtener mark price de Kraken Futures.")
            return {"status": "ERROR", "reason": "fetch_mark_price_failed"}

        notional = equity * size_fraction
        contracts = max(1, int(math.floor(notional / max(entry_price * self.contract_size, 1e-8))))
        if contracts <= 0:
            self.logger.warning("Cantidad de contratos resultó 0.")
            return {"status": "SKIPPED", "reason": "zero_contracts"}

        side = order.get("side", "").upper()
        if side not in {"LONG", "SHORT"}:
            return {"status": "ERROR", "reason": "invalid_side"}

        payload: Dict[str, Any] = {
            "orderType": "mkt",
            "symbol": self.symbol,
            "side": "buy" if side == "LONG" else "sell",
            "size": str(contracts),
        }

        try:
            response = self.client.send_order(payload)
            self.logger.debug("Kraken sendorder payload=%s response=%s", payload, response)
        except KrakenFuturesAPIError as exc:
            self.logger.error("Kraken Futures rechazó la orden: %s", exc)
            return {"status": "ERROR", "reason": "api_error", "details": str(exc)}

        send_status = response.get("sendStatus", {}) if isinstance(response, dict) else {}
        order_id = send_status.get("order_id") or send_status.get("orderId")

        # Calcular precios de TP/SL
        tp_factor = float(order.get("take_profit", 1.0))
        sl_factor = float(order.get("stop_loss", 1.0))
        tp_price = entry_price * tp_factor if side == "LONG" else entry_price * (2 - tp_factor)
        sl_price = entry_price * sl_factor if side == "LONG" else entry_price * (2 - sl_factor)

        # Registrar la posición en el gestor
        self.position_manager.open_position(
            symbol=self.symbol,
            side=side,
            size_contracts=contracts,
            entry_price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            entry_timestamp=datetime.now(timezone.utc).isoformat(),
            trade_id=order.get("trade_id", ""),
            misc={"order_id": order_id}
        )

        self.logger.info(f"POSICIÓN ABIERTA: {side} {contracts} {self.symbol} @ {entry_price:.2f}")
        return {"status": "OPENED", "order_id": order_id, "response": response}

    def close_open_position(self, exit_price: float, reason: str) -> Dict[str, Any]:
        """Cierra la posición abierta y calcula el resultado."""
        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return {"status": "ERROR", "reason": "no_position_to_close"}

        close_side = "sell" if open_pos.side == "LONG" else "buy"
        payload = {
            "orderType": "mkt",
            "symbol": self.symbol,
            "side": close_side,
            "size": str(open_pos.size_contracts),
            "reduceOnly": "true",
        }

        try:
            response = self.client.send_order(payload)
        except KrakenFuturesAPIError as exc:
            self.logger.error("Error al cerrar posición en Kraken: %s", exc)
            return {"status": "ERROR", "reason": "close_api_error", "details": str(exc)}

        # Calcular PnL
        price_diff = exit_price - open_pos.entry_price
        if open_pos.side == "SHORT":
            price_diff = -price_diff

        pnl_per_contract = price_diff * self.contract_size
        gross_pnl = pnl_per_contract * open_pos.size_contracts

        entry_notional = open_pos.entry_price * open_pos.size_contracts * self.contract_size
        exit_notional = exit_price * open_pos.size_contracts * self.contract_size
        fee = (entry_notional * self.entry_fee_rate) + (exit_notional * self.exit_fee_rate)

        net_pnl = gross_pnl - fee

        # Actualizar balance
        self.balance_manager.apply_trade_result(pnl=net_pnl, fee=0) # El fee ya está en el net_pnl

        self.logger.info(
            f"POSICIÓN CERRADA: {open_pos.side} {open_pos.size_contracts} {self.symbol} | PnL Bruto: {gross_pnl:.4f}, Fee: {fee:.4f}, PnL Neto: {net_pnl:.4f}"
        )

        # Limpiar la posición del gestor
        self.position_manager.close_position()

        return {
            "trade_id": open_pos.trade_id,
            "result": "WIN" if net_pnl > 0 else "LOSS",
            "pnl": gross_pnl,
            "pnl_net": net_pnl,
            "fee": fee,
            "exit_reason": reason,
            "entry_price": open_pos.entry_price,
            "exit_price": exit_price,
            "size": open_pos.size_contracts,
            "raw_close_response": response,
        }

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, float]:
        state = self.balance_manager.get_state()
        return {
            "balance": float(state.get("balance", 0.0)),
            "equity": float(state.get("equity", state.get("balance", 0.0))),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _prime_cache(self) -> None:
        try:
            response = self.client.get_candles(self.symbol, self.interval, price_type="trade", limit=self.prefetch_candles)
            candles = response.get("candles", [])
            for candle in candles[-self.prefetch_candles :]:
                normalized = self._normalize_candle(candle)
                self._candle_queue.append(normalized)
                self._last_timestamp = normalized["timestamp_ms"]
        except Exception as exc:
            self.logger.error("No se pudieron precargar velas de Kraken: %s", exc)

    def _refresh_candles(self) -> None:
        params: Dict[str, Any] = {}
        if self._last_timestamp:
            params["from"] = int(self._last_timestamp / 1000)
        try:
            response = self.client.get_candles(self.symbol, self.interval, price_type="trade", **params)
        except Exception as exc:
            self.logger.debug("Error obteniendo velas de Kraken: %s", exc)
            return

        candles = response.get("candles", []) or []
        for candle in candles:
            normalized = self._normalize_candle(candle)
            if self._last_timestamp and normalized["timestamp_ms"] <= self._last_timestamp:
                continue
            self._candle_queue.append(normalized)

    def _normalize_candle(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        ts = int(candle.get("time", 0))
        return {
            "timestamp_ms": ts,
            "timestamp_iso": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
            "symbol": self.symbol,
            "open": float(candle.get("open", 0.0)),
            "high": float(candle.get("high", 0.0)),
            "low": float(candle.get("low", 0.0)),
            "close": float(candle.get("close", 0.0)),
            "volume": float(candle.get("volume", 0.0)),
        }

    def _sync_balance_from_exchange(self) -> None:
        try:
            accounts = self.client.get_accounts()
        except Exception as exc:
            self.logger.debug("No se pudo sincronizar balance con Kraken: %s", exc)
            return

        accounts_map = accounts.get("accounts", {}) if isinstance(accounts, dict) else {}
        balance = None
        equity = None

        for account in accounts_map.values():
            if not isinstance(account, dict):
                continue
            if "portfolioValue" in account:
                equity = float(account.get("portfolioValue", 0.0))
                balance = float(account.get("balanceValue", equity))
                break
            if "auxiliary" in account and isinstance(account["auxiliary"], dict):
                aux = account["auxiliary"]
                equity = float(aux.get("pv", aux.get("af", 0.0)))
                balance = float(aux.get("af", equity))
            if "balances" in account and isinstance(account["balances"], dict):
                first_balance = next(iter(account["balances"].values()), 0.0)
                balance = float(first_balance or 0.0)
                equity = balance

        if balance is None or equity is None:
            return

        try:
            self.balance_manager.balance = balance
            self.balance_manager.equity = equity
        except Exception:
            if hasattr(self.balance_manager, "set_balance"):
                self.balance_manager.set_balance(balance)

    def close_all_positions(self) -> None:
        self.logger.info("Cerrando órdenes y posiciones pendientes en Kraken...")

        try:
            open_orders_resp = self.client.get_open_orders()
            open_orders = open_orders_resp.get("openOrders", []) if isinstance(open_orders_resp, dict) else []
            for order in open_orders:
                oid = order.get("orderId") or order.get("order_id")
                if oid:
                    try:
                        self.client.cancel_order(oid)
                    except Exception as exc:
                        self.logger.debug("No se pudo cancelar orden %s: %s", oid, exc)
        except Exception as exc:
            self.logger.debug("Fallo obteniendo órdenes abiertas: %s", exc)

        try:
            positions_resp = self.client.get_open_positions()
        except Exception as exc:
            self.logger.debug("Fallo obteniendo posiciones abiertas: %s", exc)
            return

        positions = positions_resp.get("openPositions", []) if isinstance(positions_resp, dict) else []
        for pos in positions:
            symbol = pos.get("symbol") or pos.get("tradeable")
            if symbol and symbol != self.symbol:
                continue

            size = abs(self._safe_float(pos, "size", alt_keys=("quantity", "amount")))
            if size <= 0:
                continue

            direction = (pos.get("side") or pos.get("direction") or "").lower()
            close_side = "sell" if direction in {"long", "buy"} else "buy"

            payload = {
                "orderType": "mkt",
                "symbol": self.symbol,
                "side": close_side,
                "size": self._format_size(size),
                "reduceOnly": "true",
            }
            try:
                self.client.send_order(payload)
                self.logger.info("Cerrada posición restante (%s %.4f)", close_side.upper(), size)
            except Exception as exc:
                self.logger.warning("No se pudo cerrar posición residual: %s", exc)

        self._sync_balance_from_exchange()

    def _fetch_mark_price(self) -> float:
        try:
            tickers = self.client.get_tickers()
        except Exception as exc:
            self.logger.error("No se pudo obtener tickers de Kraken Futures: %s", exc)
            return 0.0

        ticker_list = tickers.get("tickers", []) if isinstance(tickers, dict) else []
        for ticker in ticker_list:
            if ticker.get("symbol") == self.symbol:
                return float(ticker.get("markPrice") or ticker.get("last", 0.0) or 0.0)
        return 0.0

    def _collect_order_financials(self, order_id: Optional[str], order_events: list[dict]) -> Dict[str, float]:
        executed_qty = 0.0
        total_value = 0.0
        fee_total = 0.0
        funding_total = 0.0

        if order_id:
            try:
                fills_resp = self.client.get_fills()
            except Exception as exc:
                self.logger.debug("No se pudieron obtener fills de Kraken: %s", exc)
            else:
                fills = fills_resp.get("fills", []) if isinstance(fills_resp, dict) else []
                for fill in fills:
                    oid = fill.get("order_id") or fill.get("orderId")
                    if not oid or oid != order_id:
                        continue
                    fill_type = str(fill.get("fillType", "")).lower()
                    fee_total += abs(self._safe_float(fill, "fee"))

                    if fill_type == "funding":
                        funding_total += self._safe_float(fill, "funding", alt_keys=("usdValue",))
                        continue

                    size = self._safe_float(fill, "size", alt_keys=("quantity", "amount"))
                    price = self._safe_float(fill, "price")
                    if size and price:
                        executed_qty += size
                        total_value += size * price

        if executed_qty == 0.0:
            for event in order_events:
                if str(event.get("type", "")).upper() != "EXECUTION":
                    continue
                amount = self._safe_float(event, "amount")
                price = self._safe_float(event, "price")
                if amount and price:
                    executed_qty += amount
                    total_value += amount * price

        avg_price = (total_value / executed_qty) if executed_qty else 0.0
        return {
            "executed_qty": executed_qty,
            "avg_price": avg_price,
            "fee": fee_total,
            "funding": funding_total,
        }

    @staticmethod
    def _safe_float(payload: Dict[str, Any], key: str, *, alt_keys: tuple[str, ...] = ()) -> float:
        keys = (key,) + alt_keys
        for k in keys:
            if k in payload and payload[k] is not None:
                try:
                    return float(payload[k])
                except (TypeError, ValueError):
                    continue
        return 0.0

    def _format_size(self, size: float) -> str:
        if size.is_integer():
            return str(int(size))
        return f"{size:.6f}".rstrip("0").rstrip(".")

    def _await_order_completion(self, order_id: str, *, timeout: float = 10.0, poll_interval: float = 0.5) -> tuple[Optional[str], list[Dict[str, Any]]]:
        """
        Bloquea brevemente esperando que Kraken marque la orden como completada/cancelada.
        Devuelve (status_final, eventos_extra).
        Si expira el timeout, se devuelve el último estado conocido (o None) y lista vacía.
        """
        deadline = time.monotonic() + max(timeout, 0.0)
        last_status: Optional[str] = None
        while time.monotonic() < deadline:
            is_open, open_status = self._is_order_still_open(order_id)
            if open_status:
                last_status = open_status
            if not is_open:
                order_snapshot = self._fetch_recent_order(order_id)
                if order_snapshot:
                    status = str(order_snapshot.get("status", last_status or "UNKNOWN")).upper()
                    events = order_snapshot.get("orderEvents", []) or order_snapshot.get("order_events", []) or []
                    return status, events
                break
            time.sleep(max(poll_interval, 0.1))
        return last_status, []

    def _is_order_still_open(self, order_id: str) -> tuple[bool, Optional[str]]:
        try:
            open_resp = self.client.get_open_orders()
        except Exception as exc:
            self.logger.debug("No se pudo obtener open orders para seguimiento (%s)", exc)
            return True, None

        orders = open_resp.get("openOrders", []) if isinstance(open_resp, dict) else []
        for order in orders:
            oid = order.get("orderId") or order.get("order_id")
            if not oid or oid != order_id:
                continue
            status = str(order.get("status", "OPEN")).upper()
            return True, status
        return False, None

    def _fetch_recent_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        try:
            recent_resp = self.client.get_recent_orders()
        except Exception as exc:
            self.logger.debug("No se pudieron obtener recent orders (%s)", exc)
            return None

        orders = recent_resp.get("recentOrders") or recent_resp.get("orders") or recent_resp.get("recent_orders")
        if not isinstance(orders, list):
            return None
        for order in orders:
            oid = order.get("orderId") or order.get("order_id")
            if oid == order_id:
                return order
        return None

    def _resolve_instrument(self, user_symbol: str) -> Dict[str, Any]:
        """
        Encuentra el instrumento real tomando el símbolo ingresado por el usuario.
        Permite abreviaturas como BTC o BTCUSD, mapeando al primer instrumento compatible.
        """
        try:
            data = self.client.get_instruments()
        except Exception as exc:
            self.logger.error("No se pudieron obtener instrumentos de Kraken: %s", exc)
            return {"symbol": user_symbol}

        instruments = data.get("instruments", []) if isinstance(data, dict) else []
        user = user_symbol.upper()

        # Coincidencia exacta
        for inst in instruments:
            if inst.get("symbol", "").upper() == user:
                return inst

        # Coincidencia por par sin separadores (BTCUSD)
        normalized_pair = user.replace("_", "").replace("-", "")
        for inst in instruments:
            pair = (inst.get("pair") or "").replace(":", "").upper()
            if pair == normalized_pair:
                return inst

        # Coincidencia por base asset (BTC / XBT)
        for inst in instruments:
            base = (inst.get("base") or "").upper()
            if base == user or (base in {"XBT"} and user in {"BTC", "XBT"}):
                return inst

        # Fallback a símbolos por defecto reconocidos
        if user in {"BTC", "BTCUSD"}:
            return next((inst for inst in instruments if inst.get("symbol") == "PF_XBTUSD"), {"symbol": "PF_XBTUSD"})

        self.logger.warning("No se encontró instrumento coincidente para %s. Usando valor literal.", user_symbol)
        return {"symbol": user_symbol}

    @staticmethod
    def _normalize_interval(interval: str) -> str:
        if not interval:
            return "1m"
        interval = interval.strip().lower()
        if interval.isdigit():
            return f"{interval}m"
        return interval
