"""
Minimal REST client for Binance Futures (USDⓈ-M Testnet).

Implements the necessary functionality for the Casino V2 live loop:
    - Public endpoints: klines (candles), ticker/price, exchangeInfo.
    - Private endpoints: new order, account balance, open orders.
Signature logic follows the official Binance documentation (HMAC-SHA256).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

# Testnet URL
DEFAULT_BASE_URL = "https://testnet.binancefuture.com"


class BinanceFuturesAPIError(RuntimeError):
    """Error raised when Binance Futures returns an error payload."""

    def __init__(self, message: str, payload: Any | None = None):
        super().__init__(message)
        self.payload = payload


class BinanceFuturesClient:
    """Lightweight REST client for Binance Futures USDⓈ-M Testnet."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.logger = logging.getLogger("BinanceFuturesClient")
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()

    # ---------------------------------------------------------------------
    # Public endpoints
    # ---------------------------------------------------------------------
    def get_exchange_info(self) -> Dict[str, Any]:
        """Retrieves exchange information, including symbols, rate limits, etc."""
        return self._request_public("/fapi/v1/exchangeInfo")

    def get_klines(self, symbol: str, interval: str, limit: int = 500, **params: Any) -> Dict[str, Any]:
        """Retrieves candle data."""
        query = {"symbol": symbol, "interval": interval, "limit": limit}
        query.update(params)
        return self._request_public("/fapi/v1/klines", params=query)

    def get_ticker_price(self, symbol: str) -> Dict[str, Any]:
        """Retrieves the latest price for a symbol."""
        return self._request_public("/fapi/v2/ticker/price", params={"symbol": symbol})

    # ---------------------------------------------------------------------
    # Private endpoints
    # ---------------------------------------------------------------------
    def get_account_balance(self) -> Dict[str, Any]:
        """Retrieves account balance."""
        return self._request_private("/fapi/v2/balance", method="GET")

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves open orders for a specific symbol or all symbols."""
        params = {"symbol": symbol} if symbol else {}
        return self._request_private("/fapi/v1/openOrders", method="GET", params=params)

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new order."""
        return self._request_private("/fapi/v1/order", method="POST", params=payload)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancels an existing order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request_private("/fapi/v1/order", method="DELETE", params=params)

    def set_margin_type(self, symbol: str, margin_type: str) -> Dict[str, Any]:
        """Sets the margin type for a symbol (ISOLATED or CROSSED)."""
        params = {
            "symbol": symbol,
            "marginType": margin_type.upper(),
        }
        return self._request_private("/fapi/v1/marginType", method="POST", params=params)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Sets the leverage for a given symbol."""
        params = {
            "symbol": symbol,
            "leverage": int(max(1, leverage)),
        }
        return self._request_private("/fapi/v1/leverage", method="POST", params=params)

    # ---------------------------------------------------------------------
    # Internal request machinery
    # ---------------------------------------------------------------------
    def _request_public(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_url + path
        response = self.session.get(url, params=params, timeout=10)
        return self._parse_response(response)

    def _request_private(self, path: str, method: str = "POST", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key or not self.api_secret:
            raise BinanceFuturesAPIError("API key/secret not configured for private request.")

        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000  # Default receive window

        query_string = urlencode(params)
        signature = self._sign(query_string)
        query_string += f"&signature={signature}"

        url = f"{self.base_url}{path}?{query_string}"

        headers = {"X-MBX-APIKEY": self.api_key}
        response = self.session.request(method.upper(), url, headers=headers, timeout=10)
        return self._parse_response(response)

    def _sign(self, payload: str) -> str:
        """Signs the payload using HMAC-SHA256."""
        return hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        text = response.text or ""
        try:
            data = response.json() if text else {}
        except ValueError as exc:
            raise BinanceFuturesAPIError(f"Invalid JSON response from Binance: {text}") from exc

        if response.status_code >= 400:
            raise BinanceFuturesAPIError(f"HTTP {response.status_code}: {data.get('msg', text)}", payload=data)

        return data
