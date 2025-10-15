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
        
        # Fetch exchange info to validate symbol and get properties
        self.exchange_info = self.client.get_exchange_info()
        self.instrument = self._resolve_instrument(self.raw_symbol_input)
        self.symbol = self.instrument.get("symbol", self.raw_symbol_input)
        self.taker_fee = float(self.profile.get("taker_fee", 0.0004))
        self.entry_fee_rate = float(self.profile.get("entry_fee_rate", self.taker_fee))
        self.exit_fee_rate = float(self.profile.get("exit_fee_rate", self.taker_fee))

        self._candle_queue: Deque[Dict[str, Any]] = deque()
        self._last_timestamp: Optional[int] = None

        self._sync_balance_from_exchange()
        self._prime_cache()

    def _resolve_instrument(self, symbol: str) -> Dict[str, Any]:
        for inst in self.exchange_info.get("symbols", []):
            if inst["symbol"] == symbol:
                return inst
        raise ValueError(f"Symbol {symbol} not found in Binance Futures exchange info.")

    # ------------------------------------------------------------------
    # Candle feed
    # ------------------------------------------------------------------
    def next_candle(self) -> Optional[Dict[str, Any]]:
        if not self._candle_queue:
            self.logger.info("Cache de velas procesado. Esperando nueva vela de %s...", self.interval)

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
            # For now, we don't simulate ghost trades on live tables
            return {"status": "SKIPPED", "reason": "ghost_order"}

        size_fraction = float(order.get("size", 0.0))
        if size_fraction <= 0.0:
            return {"status": "SKIPPED", "reason": "invalid_size"}

        equity = float(self.balance_manager.get_state().get("equity", 0.0))
        if equity <= 0:
            return {"status": "SKIPPED", "reason": "no_equity"}

        side = order.get("side", "").upper()
        if side not in {"LONG", "SHORT"}:
            return {"status": "ERROR", "reason": "invalid_side"}

        # Fetch current price to calculate quantity
        try:
            price_info = self.client.get_ticker_price(self.symbol)
            entry_price = float(price_info["price"])
        except (BinanceFuturesAPIError, KeyError, ValueError) as exc:
            self.logger.error("No se pudo obtener el precio actual de Binance: %s", exc)
            return {"status": "ERROR", "reason": "fetch_price_failed"}

        notional_value = equity * size_fraction
        quantity = notional_value / entry_price

        # Adjust quantity to match symbol's precision rules
        quantity = self._adjust_quantity_to_precision(quantity)
        if quantity <= 0:
            self.logger.warning("La cantidad calculada es 0 después de ajustar la precisión.")
            return {"status": "SKIPPED", "reason": "quantity_too_low"}

        payload = {
            "symbol": self.symbol,
            "side": "BUY" if side == "LONG" else "SELL",
            "type": "MARKET",
            "quantity": str(quantity),
        }

        try:
            response = self.client.create_order(payload)
            self.logger.debug("Binance create_order payload=%s response=%s", payload, response)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Binance Futures rechazó la orden: %s", exc)
            return {"status": "ERROR", "reason": "api_error", "details": str(exc)}

        # Assume immediate execution for market orders and use the ticker price as entry price
        # A more robust implementation would use the fill price from the order response
        order_id = response.get("orderId")
        tp_factor = float(order.get("take_profit", 1.0))
        sl_factor = float(order.get("stop_loss", 1.0))
        tp_price = entry_price * tp_factor if side == "LONG" else entry_price * (2 - tp_factor)
        sl_price = entry_price * sl_factor if side == "LONG" else entry_price * (2 - sl_factor)

        self.position_manager.open_position(
            symbol=self.symbol,
            side=side,
            size_contracts=quantity, # Using contracts to mean quantity here
            entry_price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            entry_timestamp=datetime.now(timezone.utc).isoformat(),
            trade_id=order.get("trade_id", ""),
            misc={"order_id": order_id}
        )

        self.logger.info(f"POSICIÓN ABIERTA: {side} {quantity} {self.symbol} @ {entry_price:.4f}")
        return {"status": "OPENED", "order_id": order_id, "response": response}

    def close_open_position(self, exit_price: float, reason: str) -> Dict[str, Any]:
        """Cierra la posición abierta y calcula el resultado."""
        open_pos = self.position_manager.get_open_position()
        if not open_pos:
            return {"status": "ERROR", "reason": "no_position_to_close"}

        close_side = "SELL" if open_pos.side == "LONG" else "BUY"
        quantity = self._adjust_quantity_to_precision(open_pos.size_contracts)

        payload = {
            "symbol": self.symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": str(quantity),
        }

        try:
            response = self.client.create_order(payload)
        except BinanceFuturesAPIError as exc:
            self.logger.error("Error al cerrar posición en Binance: %s", exc)
            return {"status": "ERROR", "reason": "close_api_error", "details": str(exc)}

        # Calculate PnL
        price_diff = exit_price - open_pos.entry_price
        if open_pos.side == "SHORT":
            price_diff = -price_diff

        gross_pnl = price_diff * open_pos.size_contracts

        entry_notional = open_pos.entry_price * open_pos.size_contracts
        exit_notional = exit_price * open_pos.size_contracts
        fee = (entry_notional * self.entry_fee_rate) + (exit_notional * self.exit_fee_rate)

        net_pnl = gross_pnl - fee

        # Update balance
        self.balance_manager.apply_trade_result(pnl=net_pnl, fee=0) # Fee is already in net_pnl

        self.logger.info(
            f"POSICIÓN CERRADA: {open_pos.side} {open_pos.size_contracts} {self.symbol} | PnL Bruto: {gross_pnl:.4f}, Fee: {fee:.4f}, PnL Neto: {net_pnl:.4f}"
        )

        # Clear position from manager
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
    def _adjust_quantity_to_precision(self, quantity: float) -> float:
        """Adjusts the quantity based on the symbol's quantityPrecision."""
        precision = self.instrument.get("quantityPrecision")
        if precision is None:
            return quantity
        
        factor = 10 ** int(precision)
        return math.floor(quantity * factor) / factor

    def _prime_cache(self) -> None:
        try:
            klines = self.client.get_klines(self.symbol, self.interval, limit=self.prefetch_candles)
            for kline in klines:
                normalized = self._normalize_candle(kline)
                self._candle_queue.append(normalized)
                self._last_timestamp = normalized["timestamp_ms"]
        except Exception as exc:
            self.logger.error("Could not prefetch candles from Binance: %s", exc)

    def _refresh_candles(self) -> None:
        params: Dict[str, Any] = {}
        if self._last_timestamp:
            params["startTime"] = self._last_timestamp + 1
        try:
            klines = self.client.get_klines(self.symbol, self.interval, **params)
        except Exception as exc:
            self.logger.debug("Error fetching candles from Binance: %s", exc)
            return

        for kline in klines:
            normalized = self._normalize_candle(kline)
            if self._last_timestamp and normalized["timestamp_ms"] <= self._last_timestamp:
                continue
            self._candle_queue.append(normalized)

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
            balances = self.client.get_account_balance()
            for asset in balances:
                if asset.get("asset") == "USDT":  # Assuming USDT balance
                    balance = float(asset.get("balance", 0.0))
                    self.balance_manager.balance = balance
                    self.balance_manager.equity = balance # Simplified for now
                    break
        except Exception as exc:
            self.logger.error("Could not sync balance with Binance: %s", exc)

    def close_all_positions(self) -> None:
        self.logger.info("Closing all open orders on Binance...")
        try:
            open_orders = self.client.get_open_orders(self.symbol)
            for order in open_orders:
                order_id = order.get("orderId")
                if order_id:
                    try:
                        self.client.cancel_order(symbol=self.symbol, order_id=order_id)
                        self.logger.info(f"Cancelled open order {order_id}.")
                    except BinanceFuturesAPIError as exc:
                        self.logger.error(f"Failed to cancel order {order_id}: {exc}")
        except BinanceFuturesAPIError as exc:
            self.logger.error("Failed to fetch open orders for cleanup: %s", exc)
