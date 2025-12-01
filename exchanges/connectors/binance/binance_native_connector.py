"""
Binance Native Connector.

This module implements the BaseConnector interface using the official
binance-futures-connector-python SDK. It replaces the CCXT-based implementation
to provide robust WebSocket handling and native OCO support.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from binance.error import ClientError
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

from exchanges.connectors.connector_base import BaseConnector


class BinanceNativeConnector(BaseConnector):
    """
    Native connector for Binance Futures using the official SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: str = "demo",
        enable_websocket: bool = True,
    ):
        """
        Initialize the native connector.

        Args:
            api_key: Binance API Key
            secret: Binance API Secret
            mode: "demo" (Testnet) or "live" (Production)
            enable_websocket: Whether to start WebSocket client
        """
        self.logger = logging.getLogger("BinanceNativeConnector")
        self._mode = mode
        self._enable_websocket = enable_websocket

        # Determine Base URL
        if self._mode == "demo":
            self._base_url = "https://testnet.binancefuture.com"
            self._ws_base_url = "wss://stream.binancefuture.com"
            # Fallback to Testnet keys if not provided
            self._api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY")
            self._secret = secret or os.getenv("BINANCE_TESTNET_SECRET")
        else:
            self._base_url = "https://fapi.binance.com"
            self._ws_base_url = "wss://fstream.binance.com"
            self._api_key = api_key or os.getenv("BINANCE_API_KEY")
            self._secret = secret or os.getenv("BINANCE_API_SECRET")

        if not self._api_key or not self._secret:
            self.logger.warning(f"⚠️ Missing API Keys for mode {self._mode}. Operations requiring auth will fail.")

        # Initialize SDK Client
        self.client = UMFutures(key=self._api_key, secret=self._secret, base_url=self._base_url)

        # WebSocket Client (Initialized in connect)
        self.ws_client = None
        self._connected = False
        self._markets = {}
        self._positions = []
        self._orders = []
        self._ticker_queues = {}  # symbol -> asyncio.Queue
        self._time_offset = 0

    @property
    def exchange_name(self) -> str:
        return "binance_native"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to Binance Futures."""
        try:
            self.logger.info(f"🔌 Connecting to Binance Native ({self._mode})...")

            # 1. Validate connection by fetching time and calculating offset
            server_time = self.client.time()["serverTime"]
            local_time = int(time.time() * 1000)
            self._time_offset = server_time - local_time
            self.logger.info(f"✅ Server Time: {server_time} | Offset: {self._time_offset}ms")

            # 2. Load Markets (Exchange Info)
            exchange_info = self.client.exchange_info()
            self._process_markets(exchange_info)
            self.logger.info(f"✅ Markets loaded: {len(self._markets)}")

            # 3. Start WebSocket if enabled
            if self._enable_websocket:
                self._start_websocket()

            self._connected = True

        except ClientError as e:
            self.logger.error(f"❌ Connection failed (ClientError): {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            raise

    async def close(self) -> None:
        """Close connections."""
        if self.ws_client:
            self.ws_client.stop()
        self._connected = False

    def _get_timestamp(self) -> int:
        """Get current timestamp with offset."""
        return int(time.time() * 1000) + self._time_offset

    def _process_markets(self, exchange_info: Dict):
        """Process exchange info into internal market map."""
        for symbol_data in exchange_info["symbols"]:
            symbol = symbol_data["symbol"]
            self._markets[symbol] = {
                "symbol": symbol,
                "base": symbol_data["baseAsset"],
                "quote": symbol_data["quoteAsset"],
                "precision": {"amount": symbol_data["quantityPrecision"], "price": symbol_data["pricePrecision"]},
                "contractSize": 1.0,  # Default for USDT perps
                "info": symbol_data,
            }

    def _start_websocket(self):
        """Start the native WebSocket client."""
        self.logger.info("🔌 Starting Native WebSocket...")
        self.ws_client = UMFuturesWebsocketClient(
            stream_url=self._ws_base_url,
            on_message=self._on_ws_message,
            on_close=self._on_ws_close,
            on_error=self._on_ws_error,
            is_combined=True,
        )

        # Subscribe to User Data Stream (ListenKey)
        # The SDK handles ListenKey keep-alive automatically!
        try:
            listen_key = self.client.new_listen_key()["listenKey"]
            self.logger.info(f"🔑 ListenKey generated: {listen_key[:10]}...")
            self.ws_client.user_data(listen_key=listen_key, id=1)
            self.logger.info("✅ Subscribed to User Data Stream")
        except Exception as e:
            self.logger.error(f"❌ Failed to start User Data Stream: {e}")

    def _on_ws_message(self, _, message):
        """Handle WebSocket messages."""
        try:
            # Parse string message if needed
            if isinstance(message, str):
                import json

                message = json.loads(message)

            # SDK passes (client, message), so we ignore client (_)
            event_type = message.get("e")
            if event_type == "ORDER_TRADE_UPDATE":
                self._handle_order_update(message)
            elif event_type == "ACCOUNT_UPDATE":
                self._handle_account_update(message)
            elif event_type == "24hrTicker":
                self._handle_ticker_update(message)
            elif "id" in message and "result" in message:
                # Response to subscription/request
                self.logger.debug(f"WS Response: {message}")
        except Exception as e:
            self.logger.error(f"❌ WS Message Error: {e}")

    def _on_ws_close(self, *args):
        self.logger.warning("⚠️ WebSocket Closed")

    def _on_ws_error(self, _, error):
        self.logger.error(f"❌ WebSocket Error: {error}")

    # ... (skipping unchanged parts) ...

    def _handle_ticker_update(self, msg):
        """Process ticker update event."""
        symbol = msg.get("s")
        # Normalize symbol if needed, but msg has native symbol
        # We need to map native symbol back to our symbol if possible,
        # or just store by native symbol and watch_ticker uses native symbol.

        # Queue dispatch
        if symbol in self._ticker_queues:
            ticker = {"symbol": symbol, "last": float(msg.get("c")), "timestamp": int(msg.get("E")), "info": msg}
            try:
                # Use put_nowait to avoid blocking callback
                self._ticker_queues[symbol].put_nowait(ticker)
            except asyncio.QueueFull:
                # Should not happen with infinite queue, but good practice
                pass

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        # ... (unchanged) ...
        # Map timeframe (1m -> 1m, same format)
        try:
            # SDK is synchronous, wrap in thread if needed, but for now direct call
            # as it's fast enough for low freq.
            klines = self.client.klines(symbol=self.normalize_symbol(symbol), interval=timeframe, limit=limit)

            return [
                {
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "symbol": symbol,
                    "timeframe": timeframe,
                }
                for k in klines
            ]
        except ClientError as e:
            self.logger.error(f"❌ fetch_ohlcv failed: {e.error_message}")
            return []

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker (REST)."""
        try:
            ticker = self.client.ticker_price(symbol=self.normalize_symbol(symbol))
            return {"symbol": symbol, "last": float(ticker["price"]), "timestamp": int(time.time() * 1000)}
        except Exception as e:
            self.logger.error(f"❌ fetch_ticker failed: {e}")
            raise

    async def watch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Watch ticker (WebSocket)."""
        native_symbol = self.normalize_symbol(symbol)

        if native_symbol not in self._ticker_queues:
            self.logger.info(f"📡 Subscribing to ticker for {native_symbol}")
            self._ticker_queues[native_symbol] = asyncio.Queue(maxsize=100)
            # Subscribe via SDK
            self.ws_client.ticker(symbol=native_symbol, id=1)

        # Wait for next update
        return await self._ticker_queues[native_symbol].get()

    # =========================================================
    # 💰 ACCOUNT DATA
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        try:
            account = self.client.account(timestamp=self._get_timestamp(), recvWindow=20000)
            # Normalize to CCXT format for compatibility
            total = {}
            free = {}
            used = {}

            for asset in account["assets"]:
                code = asset["asset"]
                total[code] = float(asset["walletBalance"])
                free[code] = float(asset["availableBalance"])
                used[code] = total[code] - free[code]

            return {"total": total, "free": free, "used": used, "timestamp": int(time.time() * 1000), "info": account}
        except Exception as e:
            self.logger.error(f"❌ fetch_balance failed: {e}")
            raise

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch open positions."""
        try:
            # Use v2 risk endpoint
            positions = self.client.get_position_risk(timestamp=self._get_timestamp(), recvWindow=20000)
            normalized = []

            for p in positions:
                amt = float(p["positionAmt"])
                if amt == 0:
                    continue

                symbol = p["symbol"]
                # Filter if specific symbols requested
                if symbols and symbol not in [self.normalize_symbol(s) for s in symbols]:
                    continue

                normalized.append(
                    {
                        "symbol": symbol,  # Keep native symbol for now, adapter handles denorm?
                        # Actually BaseConnector says normalize response.
                        # We should denormalize symbol here if possible, but we might not have the map.
                        # For Binance, BTCUSDT -> BTC/USDT usually.
                        # Let's keep it simple: return native symbol, adapter can handle or we add helper.
                        "side": "LONG" if amt > 0 else "SHORT",
                        "size": abs(amt),
                        "entry_price": float(p["entryPrice"]),
                        "mark_price": float(p["markPrice"]),
                        "liquidation_price": float(p["liquidationPrice"]),
                        "unrealized_pnl": float(p["unRealizedProfit"]),
                        "leverage": float(p["leverage"]),
                        "timestamp": int(p["updateTime"]),
                        "info": p,
                    }
                )
            return normalized
        except Exception as e:
            self.logger.error(f"❌ fetch_positions failed: {e}")
            raise

    async def fetch_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Fetch open orders."""
        try:
            kwargs = {}
            if symbol:
                kwargs["symbol"] = self.normalize_symbol(symbol)

            # Add timestamp and recvWindow
            kwargs["timestamp"] = self._get_timestamp()
            kwargs["recvWindow"] = 20000

            # Use get_orders (all orders) and filter, as get_open_orders requires orderId in this SDK version
            orders = self.client.get_orders(**kwargs)
            orders = [o for o in orders if o["status"] in ["NEW", "PARTIALLY_FILLED"]]

            return [self._normalize_order(o) for o in orders]
        except Exception as e:
            self.logger.error(f"❌ fetch_open_orders failed: {e}")
            raise

    # =========================================================
    # 📝 ORDER EXECUTION
    # =========================================================

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create an order."""
        try:
            native_symbol = self.normalize_symbol(symbol)
            native_side = side.upper()  # BUY or SELL
            native_type = order_type.upper()  # MARKET, LIMIT, STOP_MARKET, etc.

            args = {
                "symbol": native_symbol,
                "side": native_side,
                "type": native_type,
                "quantity": amount,
            }

            if price:
                args["price"] = price

            if params:
                args.update(params)

            # Add timestamp and recvWindow
            args["timestamp"] = self._get_timestamp()
            args["recvWindow"] = 20000

            self.logger.info(f"📋 Sending Order: {args}")
            response = self.client.new_order(**args)

            return self._normalize_order(response)

        except ClientError as e:
            self.logger.error(f"❌ Order Failed: {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Order Failed: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            response = self.client.cancel_order(
                symbol=self.normalize_symbol(symbol),
                orderId=order_id,
                timestamp=self._get_timestamp(),
                recvWindow=20000,
            )
            return self._normalize_order(response)
        except Exception as e:
            self.logger.error(f"❌ Cancel Failed: {e}")
            raise

    # =========================================================
    # 🔧 UTILS
    # =========================================================

    def normalize_symbol(self, symbol: str) -> str:
        """BTC/USDT -> BTCUSDT"""
        return symbol.replace("/", "").replace(":USDT", "")

    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """BTCUSDT -> BTC/USDT:USDT (Simplified)"""
        # This is tricky without a map. For now assume USDT pairs.
        if exchange_symbol.endswith("USDT"):
            base = exchange_symbol[:-4]
            return f"{base}/USDT:USDT"
        return exchange_symbol

    def _normalize_order(self, response: Dict) -> Dict:
        """Normalize order response."""
        return {
            "id": str(response["orderId"]),
            "symbol": response["symbol"],
            "status": response["status"].lower(),
            "price": float(response.get("avgPrice", 0) or 0),
            "amount": float(response["origQty"]),
            "filled": float(response["executedQty"]),
            "type": response["type"].lower(),
            "side": response["side"].lower(),
            "timestamp": response["updateTime"],
            "info": response,
        }
