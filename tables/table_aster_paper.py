"""
====================================================
TableAsterPaper — mesa paper trading ASTERDEx
====================================================

Objetivos:
----------
- Consumir velas recientes desde la API REST de ASTERDEx.
- Enrutar órdenes reales a la API (paper mode) respetando filtros del símbolo.
- Mantener el contrato estándar para el Croupier (next_candle / execute_order).

Nota:
-----
Esta implementación trabaja en modo "pull" (REST) para simplificar el prototipo.
Para producción se recomienda migrar a WebSocket (`kline` stream) y manejar
reconexiones (la sesión oficial expira cada 24h).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Deque, Dict, Optional

import config
from tables.balance_manager import BalanceManager
from tables.table_base import BaseTable
from utils.aster_env_loader import load_aster_credentials
from utils.asterdex_client import AsterDexClient, AsterDexAPIError


class TableAsterPaper(BaseTable):
    """Mesa realtime que opera contra ASTERDEx (paper trading)."""

    def __init__(
        self,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        *,
        profile: str = "asterdex_paper",
        client: Optional[AsterDexClient] = None,
        prefetch_limit: int = 500,
        poll_interval: float = 2.0,
        order_query_delay: float = 0.35,
    ) -> None:
        super().__init__(exchange_profile=profile)
        self.logger = logging.getLogger("TableAsterPaper")

        self.symbol = (symbol or getattr(config, "ASTER_DEFAULT_SYMBOL", "BTCUSDT")).upper()
        self.interval = interval or getattr(config, "ASTER_DEFAULT_INTERVAL", "1m")
        self.prefetch_limit = max(1, prefetch_limit)
        self.poll_interval = poll_interval or getattr(config, "ASTER_POLL_INTERVAL", 2.0)
        self.order_query_delay = order_query_delay

        if client:
            self.client = client
        else:
            creds = load_aster_credentials(test_connection=False)
            self.client = AsterDexClient(
                api_key=creds.get("api_key"),
                api_secret=creds.get("api_secret"),
                base_url=creds.get("base_url"),
            )
        self.balance_manager = BalanceManager(starting_balance=getattr(config, "STARTING_BALANCE", 10_000.0))
        self._sync_balance_from_exchange()

        self.taker_fee = float(self.profile.get("taker_fee", getattr(config, "COMMISSION_RATE", 0.0004)))
        self.entry_fee_rate = float(self.profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.profile.get("exit_fee_rate", self.taker_fee))

        self._candle_queue: Deque[Dict[str, Any]] = deque()
        self._last_open_time: Optional[int] = None

        self.symbol_filters = self._load_symbol_filters()

    # ============================================================
    # Public API
    # ============================================================
    def next_candle(self) -> Optional[Dict[str, Any]]:
        """
        Devuelve la próxima vela disponible.
        Si no hay nuevas velas, espera `poll_interval` antes de reintentar.
        """
        attempt = 0
        while not self._candle_queue:
            attempt += 1
            self._refresh_cache()
            if self._candle_queue:
                break
            time.sleep(self.poll_interval)
            if attempt > 20:
                self.logger.debug("Sin nuevas velas tras varios intentos (symbol=%s interval=%s)", self.symbol, self.interval)

        if not self._candle_queue:
            return None

        candle = self._candle_queue.popleft()
        self._last_open_time = candle["open_time"]

        state = self.balance_manager.get_state()
        return {
            "timestamp": candle["open_time_iso"],
            "timestamp_ms": candle["open_time"],
            "symbol": self.symbol,
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

    def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Envía una orden a la API de ASTER (paper)."""
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
            self.logger.warning("Orden real omitida: credenciales ASTER faltantes.")
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        size_fraction = float(order.get("size", 0.0))
        if size_fraction <= 0.0:
            self.logger.warning("Orden sin tamaño válido (size_fraction=%s).", size_fraction)
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        state = self.balance_manager.get_state()
        equity = float(state.get("equity", state.get("balance", 0.0)))
        if equity <= 0:
            self.logger.warning("Equity no disponible para calcular tamaño de orden.")
            return {**result_base, "result": "SKIPPED", "pnl": 0.0, "fee": 0.0}

        try:
            mark_info = self.client.get_mark_price(self.symbol)
            mark_price = float(mark_info[0]["markPrice"] if isinstance(mark_info, list) else mark_info["markPrice"])
        except Exception as exc:
            self.logger.error("No se pudo obtener mark price de ASTER: %s", exc)
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0}

        try:
            quantity = self._determine_quantity(equity * size_fraction, mark_price)
        except ValueError as exc:
            self.logger.error("Cantidad inválida para la orden: %s", exc)
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0}

        aster_side = self._map_side(order.get("side", "LONG"))
        payload = {
            "symbol": self.symbol,
            "side": aster_side["order"],
            "type": "MARKET",
            "quantity": self._format_decimal(quantity),
            "positionSide": aster_side["position"],
        }

        if order.get("reduce_only") is True:
            payload["reduceOnly"] = "true"

        if order.get("take_profit"):
            payload["takeProfitPrice"] = order["take_profit"]
        if order.get("stop_loss"):
            payload["stopLossPrice"] = order["stop_loss"]

        try:
            response = self.client.place_order(**payload)
            order_id = response.get("orderId")
            time.sleep(self.order_query_delay)
            order_status = self.client.get_order(symbol=self.symbol, orderId=order_id) if order_id else response
        except AsterDexAPIError as exc:
            self.logger.error("API ASTER devolvió error al enviar orden: %s", exc)
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0, "error": str(exc)}
        except Exception as exc:
            self.logger.exception("Fallo inesperado al procesar orden ASTER.")
            return {**result_base, "result": "ERROR", "pnl": 0.0, "fee": 0.0, "error": str(exc)}

        filled_qty = float(order_status.get("executedQty", response.get("executedQty", 0.0)) or 0.0)
        cum_quote = float(order_status.get("cumQuote", response.get("cumQuote", 0.0)) or 0.0)
        avg_price = float(order_status.get("avgPrice", response.get("avgPrice", 0.0)) or 0.0)
        status = order_status.get("status", response.get("status", "NEW"))

        fee_estimate = cum_quote * (self.entry_fee_rate + self.exit_fee_rate) if cum_quote else 0.0

        result_payload = {
            **result_base,
            "result": "FILLED" if status == "FILLED" else status or "PENDING",
            "status": status,
            "executed_qty": filled_qty,
            "avg_price": avg_price,
            "pnl": 0.0,
            "fee": fee_estimate,
            "order_id": order_status.get("orderId", response.get("orderId")),
            "update_time": order_status.get("updateTime"),
            "message": order_status.get("clientOrderId"),
        }
        self._sync_balance_from_exchange()
        return result_payload

    def get_state(self) -> Dict[str, float]:
        """Expose current balance/equity similar to other tables."""
        state = self.balance_manager.get_state()
        return {
            "balance": float(state.get("balance", 0.0)),
            "equity": float(state.get("equity", state.get("balance", 0.0))),
        }

    # ============================================================
    # Helpers internos
    # ============================================================
    def _refresh_cache(self) -> None:
        try:
            raw = self.client.get_klines(self.symbol, self.interval, limit=self.prefetch_limit)
        except AsterDexAPIError as exc:
            self.logger.error("Error recuperando klines ASTER: %s", exc)
            return
        except Exception as exc:
            self.logger.exception("Error inesperado consultando klines ASTER.")
            return

        new_candles = []
        for row in raw:
            if len(row) < 6:
                continue
            open_time = int(row[0])
            if self._last_open_time and open_time <= self._last_open_time:
                continue
            new_candles.append(self._normalize_kline(row))

        new_candles.sort(key=lambda item: item["open_time"])
        for candle in new_candles:
            self._candle_queue.append(candle)

    def _sync_balance_from_exchange(self) -> None:
        """Actualiza balance/equity con la info que devuelve ASTERDEx."""
        margin_asset = getattr(config, "ASTER_MARGIN_ASSET", None) or self._infer_quote_asset(self.symbol)
        try:
            balances = self.client.get_account_balance()
        except Exception as exc:
            self.logger.debug("No se pudo sincronizar balance ASTER: %s", exc)
            return

        asset_entry = None
        if isinstance(balances, list):
            asset_entry = next((item for item in balances if item.get("asset") == margin_asset), None)
        elif isinstance(balances, dict):
            # Algunas variantes podrían devolver un dict con clave 'balances'
            items = balances.get("balances") if isinstance(balances.get("balances"), list) else []
            asset_entry = next((item for item in items if item.get("asset") == margin_asset), None)

        if not asset_entry:
            self.logger.debug("No se encontró asset %s en la respuesta de balance.", margin_asset)
            return

        balance = float(asset_entry.get("balance", 0.0) or asset_entry.get("walletBalance", 0.0))
        equity = float(
            asset_entry.get("crossWalletBalance", asset_entry.get("availableBalance", balance) or balance)
        )

        try:
            self.balance_manager.balance = balance
            self.balance_manager.equity = equity
        except Exception:
            # fallback si el BalanceManager no expone propiedades directas
            if hasattr(self.balance_manager, "set_balance"):
                self.balance_manager.set_balance(balance)

    @staticmethod
    def _infer_quote_asset(symbol: str) -> str:
        if not symbol:
            return "USDT"
        for quote in ("USDT", "BUSD", "USDC", "USD", "VUSDT", "CUSDT"):
            if symbol.endswith(quote):
                return quote
        return "USDT"

    @staticmethod
    def _normalize_kline(row: Any) -> Dict[str, Any]:
        open_time = int(row[0])
        close_time = int(row[6])
        open_dt = datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)
        return {
            "open_time": open_time,
            "close_time": close_time,
            "open_time_iso": open_dt.isoformat().replace("+00:00", "Z"),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }

    def _load_symbol_filters(self) -> Dict[str, float]:
        try:
            info = self.client.get_exchange_info(self.symbol)
        except Exception as exc:
            self.logger.error("No se pudo obtener exchangeInfo para %s: %s", self.symbol, exc)
            return {
                "min_qty": 0.001,
                "step_size": 0.001,
                "min_notional": 0.0,
            }

        if isinstance(info, dict):
            symbols = info.get("symbols") or []
            symbol_entry = next((item for item in symbols if item.get("symbol") == self.symbol), None)
        else:
            symbol_entry = None

        if not symbol_entry:
            return {
                "min_qty": 0.001,
                "step_size": 0.001,
                "min_notional": 0.0,
            }

        filters = symbol_entry.get("filters", [])
        lot_size = next((flt for flt in filters if flt.get("filterType") == "LOT_SIZE"), {})
        min_notional = next((flt for flt in filters if flt.get("filterType") == "MIN_NOTIONAL"), {})

        min_qty = float(lot_size.get("minQty", 0.001))
        step_size = float(lot_size.get("stepSize", 0.001))
        min_notional_value = float(min_notional.get("notional", 0.0) or min_notional.get("minNotional", 0.0))

        return {
            "min_qty": min_qty,
            "step_size": step_size,
            "min_notional": min_notional_value,
        }

    def _determine_quantity(self, notional: float, mark_price: float) -> float:
        if mark_price <= 0 or notional <= 0:
            raise ValueError("mark_price y notional deben ser positivos.")

        raw_qty = notional / mark_price
        qty = max(self.symbol_filters["min_qty"], self._quantize(raw_qty, self.symbol_filters["step_size"]))
        notional_value = qty * mark_price

        min_notional = self.symbol_filters["min_notional"]
        if min_notional and notional_value < min_notional:
            qty = self._quantize((min_notional / mark_price) * 1.01, self.symbol_filters["step_size"])
            notional_value = qty * mark_price

        if qty <= 0 or notional_value <= 0:
            raise ValueError("Cantidad final inválida tras aplicar filtros.")

        return qty

    @staticmethod
    def _format_decimal(value: float, precision: int = 8) -> str:
        return f"{value:.{precision}f}".rstrip("0").rstrip(".")

    @staticmethod
    def _quantize(value: float, step: float) -> float:
        if step <= 0:
            return value
        value_dec = Decimal(str(value))
        step_dec = Decimal(str(step))
        quantized = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN) * step_dec
        return float(quantized)

    @staticmethod
    def _map_side(side: str) -> Dict[str, str]:
        side_upper = (side or "").upper()
        if side_upper == "SHORT":
            return {"order": "SELL", "position": "SHORT"}
        return {"order": "BUY", "position": "LONG"}
