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
        ghost = bool(order.get("ghost", False))
        trade_id = order.get("trade_id")

        result_base = {
            "trade_id": trade_id,
            "symbol": self.symbol,
            "ghost": ghost,
            "balance": self.balance_manager.get_state().get("balance"),
        }

        if ghost:
            return {**result_base, "result": "GHOST", "pnl": 0.0, "fee": 0.0}

        if not self.client.api_key or not self.client.api_secret:
            self.logger.warning("Orden real omitida: faltan credenciales de Kraken Futures.")
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        size_fraction = float(order.get("size", 0.0))
        if size_fraction <= 0.0:
            self.logger.warning("Orden con tamaño inválido (sizeFraction=%s).", size_fraction)
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        equity = float(self.balance_manager.get_state().get("equity", 0.0))
        if equity <= 0:
            self.logger.warning("Equity indisponible para calcular riesgo.")
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        mark_price = self._fetch_mark_price()
        if mark_price <= 0:
            self.logger.error("No se pudo obtener mark price de Kraken Futures.")
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0}

        notional = equity * size_fraction
        contracts = max(1, int(math.floor(notional / max(mark_price * self.contract_size, 1e-8))))
        if contracts <= 0:
            self.logger.warning("Cantidad de contratos resultó 0. Aumenta el tamaño o revisa el balance.")
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        side = order.get("side", "").lower()
        if side not in {"long", "short", "buy", "sell"}:
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0, "error": "invalid_side"}

        payload: Dict[str, Any] = {
            "orderType": "mkt",
            "symbol": self.symbol,
            "side": "buy" if side in {"long", "buy"} else "sell",
            "size": str(contracts),
        }
        if order.get("reduce_only"):
            payload["reduceOnly"] = "true"
        if order.get("cliOrdId"):
            payload["cliOrdId"] = order["cliOrdId"]

        try:
            response = self.client.send_order(payload)
        except KrakenFuturesAPIError as exc:
            self.logger.error("Kraken Futures rechazó la orden: %s", exc)
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0, "error": str(exc)}
        except Exception as exc:  # pragma: no cover
            self.logger.exception("Error inesperado enviando orden a Kraken Futures.")
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0, "error": str(exc)}

        send_status = response.get("sendStatus", {}) if isinstance(response, dict) else {}
        status = str(send_status.get("status", "unknown")).upper()
        order_events = send_status.get("orderEvents", []) or []

        executed_qty = 0.0
        avg_price = 0.0
        total_value = 0.0
        for event in order_events:
            event_type = str(event.get("type", "")).upper()
            amount = float(event.get("amount", 0.0) or 0.0)
            price = float(event.get("price", 0.0) or 0.0)
            if event_type == "EXECUTION" and amount:
                executed_qty += amount
                total_value += amount * price

        if executed_qty > 0 and total_value > 0:
            avg_price = total_value / executed_qty

        fee_estimate = executed_qty * avg_price * self.contract_size * (self.entry_fee_rate + self.exit_fee_rate)

        result_payload = {
            **result_base,
            "result": status,
            "status": status,
            "executed_qty": executed_qty,
            "avg_price": avg_price,
            "pnl": 0.0,
            "fee": fee_estimate,
            "order_id": send_status.get("order_id"),
            "raw": response,
        }

        self._sync_balance_from_exchange()
        return result_payload

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
