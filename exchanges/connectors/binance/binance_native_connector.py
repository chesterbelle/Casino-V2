"""
Binance Native Connector.

This module implements the BaseConnector interface using the official
binance-futures-connector-python SDK. It replaces the CCXT-based implementation
to provide robust WebSocket handling and native OCO support.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import websockets
from binance.error import ClientError
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

from exchanges.connectors.connector_base import BaseConnector
from exchanges.rate_limiter import BinanceRateLimiter


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

        # Initialize REST client
        self.client = UMFutures(key=api_key, secret=secret, base_url=self._base_url)

        # Initialize rate limiter
        self.rate_limiter = BinanceRateLimiter()
        self.logger.info("🕒 Rate limiter initialized for Binance")

        # WebSocket client (initialized in connect())
        self.ws_client = None
        self._connected = False
        self._markets = {}
        self._positions = []
        self._orders = []
        self._ticker_queues = {}  # symbol -> asyncio.Queue
        self._time_offset = 0

        # User Data Stream for order updates
        self._listen_key = None
        self._user_data_ws = None
        self._order_update_callback = None
        self._keepalive_task = None

    @property
    def exchange_name(self) -> str:
        return "binance_native"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        """Return the current mode (live/demo/testing)."""
        return self._mode

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

            # 3. Force One-Way Mode
            try:
                # Check current mode
                position_mode = self.client.get_position_mode()
                if position_mode["dualSidePosition"]:
                    self.logger.info("⚠️ Account is in Hedge Mode. Switching to One-Way Mode...")
                    self.client.change_position_mode(dualSidePosition="false")
                    self.logger.info("✅ Switched to One-Way Mode")
                else:
                    self.logger.info("✅ Account is in One-Way Mode")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to check/switch position mode: {e}")

            # 4. Start WebSocket if enabled
            if self._enable_websocket:
                self._start_websocket()

            # 5. Start User Data Stream for order updates
            if self._api_key and self._secret:
                await self._start_user_data_stream()

            self._connected = True

        except ClientError as e:
            self.logger.error(f"❌ Connection failed (ClientError): {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            raise

    async def close(self) -> None:
        """Close connections."""
        self.logger.info("🔌 BinanceNativeConnector.close() called")

        # Stop User Data Stream keepalive task
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None

        # Close User Data Stream WebSocket
        if self._user_data_ws:
            try:
                await self._user_data_ws.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Error closing user data stream: {e}")
            self._user_data_ws = None

        # Close market data WebSocket
        if self.ws_client:
            self.ws_client.stop()

        self._connected = False

    # ========================
    # User Data Stream Methods
    # ========================

    async def _create_listen_key(self) -> str:
        """Create a listen key for User Data Stream."""
        try:
            response = self.client.new_listen_key()
            listen_key = response.get("listenKey")
            self.logger.info(f"✅ Listen key created: {listen_key[:20]}...")
            return listen_key
        except Exception as e:
            self.logger.error(f"❌ Failed to create listen key: {e}")
            raise

    async def _keepalive_listen_key(self):
        """Keep listen key alive by refreshing every 30 minutes."""
        self.logger.info("🔄 Keepalive task started")
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                if self._listen_key:
                    self.client.renew_listen_key(listenKey=self._listen_key)
                    self.logger.debug("🔄 Listen key renewed")
            except asyncio.CancelledError:
                self.logger.info("🛑 Keepalive task cancelled")
                break
            except Exception as e:
                self.logger.error(f"❌ Error renewing listen key: {e}")

    async def _start_user_data_stream(self):
        """Start User Data Stream WebSocket for order updates."""
        try:
            # Create listen key
            self._listen_key = await self._create_listen_key()

            # Build WebSocket URL
            ws_url = f"wss://fstream.binance.com/ws/{self._listen_key}"
            if self._mode == "demo":
                ws_url = f"wss://stream.binancefuture.com/ws/{self._listen_key}"

            self.logger.info("🔌 Connecting to User Data Stream...")

            # Start WebSocket connection
            self._user_data_ws = await websockets.connect(ws_url)

            # Start keepalive task
            self._keepalive_task = asyncio.create_task(self._keepalive_listen_key())

            # Start listening task
            asyncio.create_task(self._listen_user_data_stream())

            self.logger.info("✅ User Data Stream connected")

        except Exception as e:
            self.logger.error(f"❌ Failed to start User Data Stream: {e}")
            raise

    async def _listen_user_data_stream(self):
        """Listen to User Data Stream and process events with auto-reconnection."""
        reconnect_attempts = 0
        max_reconnect_attempts = 20  # ~10 minutes with backoff
        base_delay = 5  # 5 seconds initial delay
        max_delay = 60  # Max 60 seconds between retries

        while reconnect_attempts < max_reconnect_attempts:
            try:
                async for message in self._user_data_ws:
                    # Reset reconnect counter on successful message
                    reconnect_attempts = 0

                    try:
                        data = json.loads(message)
                        event_type = data.get("e")

                        if event_type == "ORDER_TRADE_UPDATE":
                            self._handle_order_update(data)
                        elif event_type == "ACCOUNT_UPDATE":
                            # Could handle balance/position updates here
                            pass

                    except json.JSONDecodeError:
                        self.logger.warning(f"⚠️ Invalid JSON from User Data Stream: {message}")
                    except Exception as e:
                        self.logger.error(f"❌ Error processing User Data Stream message: {e}")

            except websockets.exceptions.ConnectionClosed:
                reconnect_attempts += 1
                delay = min(base_delay * (2 ** (reconnect_attempts - 1)), max_delay)
                self.logger.warning(
                    f"⚠️ User Data Stream disconnected. "
                    f"Reconnecting in {delay}s (attempt {reconnect_attempts}/{max_reconnect_attempts})..."
                )
                await asyncio.sleep(delay)

                # Attempt reconnection
                try:
                    await self._reconnect_user_data_stream()
                    self.logger.info("✅ User Data Stream reconnected successfully")
                except Exception as e:
                    self.logger.error(f"❌ Reconnection failed: {e}")

            except Exception as e:
                self.logger.error(f"❌ Error in User Data Stream listener: {e}")
                reconnect_attempts += 1
                if reconnect_attempts < max_reconnect_attempts:
                    delay = min(base_delay * (2 ** (reconnect_attempts - 1)), max_delay)
                    self.logger.info(f"🔄 Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    try:
                        await self._reconnect_user_data_stream()
                    except Exception:
                        pass

        self.logger.error("❌ Max reconnection attempts reached. User Data Stream stopped.")

    async def _reconnect_user_data_stream(self):
        """Reconnect the User Data Stream WebSocket."""
        # Close existing connection if any
        if self._user_data_ws:
            try:
                await self._user_data_ws.close()
            except Exception:
                pass

        # Get new listen key (old one may have expired)
        self._listen_key = await self._create_listen_key()

        # Build WebSocket URL
        ws_url = f"wss://fstream.binance.com/ws/{self._listen_key}"
        if self._mode == "demo":
            ws_url = f"wss://stream.binancefuture.com/ws/{self._listen_key}"

        # Reconnect
        self._user_data_ws = await websockets.connect(ws_url)

    def _normalize_order_status(self, binance_status: str) -> str:
        """Convert Binance order status to CCXT-like status."""
        status_map = {
            "NEW": "open",
            "PARTIALLY_FILLED": "open",
            "FILLED": "closed",
            "CANCELED": "canceled",
            "EXPIRED": "expired",
            "REJECTED": "rejected",
        }
        return status_map.get(binance_status, binance_status.lower())

    def set_order_update_callback(self, callback):
        """Register a callback for order updates."""
        self._order_update_callback = callback
        self.logger.info("✅ Order update callback registered")

    def _get_timestamp(self) -> int:
        """Get current timestamp with offset."""
        return int(time.time() * 1000) + self._time_offset

    def _process_markets(self, exchange_info: Dict):
        """Process exchange info into internal market map."""
        for symbol_data in exchange_info["symbols"]:
            symbol = symbol_data["symbol"]

            # Extract tick size and step size from filters
            tick_size = None
            step_size = None
            for f in symbol_data.get("filters", []):
                if f["filterType"] == "PRICE_FILTER":
                    tick_size = float(f["tickSize"])
                elif f["filterType"] == "LOT_SIZE":
                    step_size = float(f["stepSize"])

            self._markets[symbol] = {
                "symbol": symbol,
                "base": symbol_data["baseAsset"],
                "quote": symbol_data["quoteAsset"],
                "precision": {"amount": symbol_data["quantityPrecision"], "price": symbol_data["pricePrecision"]},
                "tick_size": tick_size or 0.01,  # Default fallback
                "step_size": step_size or 0.001,  # Default fallback
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

    def price_to_precision(self, symbol: str, price: float) -> str:
        """
        Format price to symbol precision using tick size.
        """
        native_symbol = self.normalize_symbol(symbol)
        if native_symbol not in self._markets:
            return str(price)

        tick_size = self._markets[native_symbol].get("tick_size", 0.01)
        # Round price to nearest tick size
        rounded = round(price / tick_size) * tick_size
        # Determine decimal places from tick size
        decimals = len(str(tick_size).rstrip("0").split(".")[-1]) if "." in str(tick_size) else 0
        return f"{rounded:.{decimals}f}"

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """
        Format amount to symbol precision using step size.
        """
        native_symbol = self.normalize_symbol(symbol)
        if native_symbol not in self._markets:
            return str(amount)

        step_size = self._markets[native_symbol].get("step_size", 0.001)
        # Round amount to nearest step size
        rounded = round(amount / step_size) * step_size
        # Determine decimal places from step size
        decimals = len(str(step_size).rstrip("0").split(".")[-1]) if "." in str(step_size) else 0
        return f"{rounded:.{decimals}f}"

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

            # Handle combined stream format
            if "data" in message:
                message = message["data"]

            event_type = message.get("e")

            if event_type == "ORDER_TRADE_UPDATE":
                self._handle_order_update(message)
            elif event_type == "ACCOUNT_UPDATE":
                self._handle_account_update(message)
            elif event_type == "24hrTicker":
                self.logger.debug(f"📊 Ticker received for {message.get('s')}")
                self._handle_ticker_update(message)
            elif event_type == "aggTrade":
                # self.logger.debug(f"⚡ Trade received for {message.get('s')}")
                self._handle_trade_update(message)
            elif "id" in message and "result" in message:
                # Response to subscription/request
                self.logger.info(f"✅ WS Subscription Response: {message}")
        except Exception as e:
            self.logger.error(f"❌ WS Message Error: {e}")

    def _on_ws_close(self, *args):
        self.logger.warning("⚠️ WebSocket Closed")

    def _on_ws_error(self, _, error):
        self.logger.error(f"❌ WebSocket Error: {error}")

    def _handle_order_update(self, msg):
        """Process ORDER_TRADE_UPDATE event from WebSocket."""
        try:
            order_data = msg.get("o", {})
            if not order_data:
                self.logger.warning("⚠️ ORDER_TRADE_UPDATE without order data")
                return

            order_id = str(order_data.get("i"))
            symbol = order_data.get("s")
            status = order_data.get("X")  # NEW, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED, EXPIRED
            side = order_data.get("S", "").lower()
            order_type = order_data.get("o", "").lower()
            price = float(order_data.get("p", 0) or 0)
            avg_price = float(order_data.get("ap", 0) or 0)
            quantity = float(order_data.get("q", 0))
            filled_qty = float(order_data.get("z", 0))

            # Update internal orders cache
            normalized_order = {
                "id": order_id,
                "symbol": symbol,
                "status": status.lower(),
                "side": side,
                "type": order_type,
                "price": avg_price if avg_price > 0 else price,
                "amount": quantity,
                "filled": filled_qty,
                "timestamp": msg.get("E", int(time.time() * 1000)),
                "info": order_data,
            }

            # Store in orders cache
            if not hasattr(self, "_orders_cache"):
                self._orders_cache = {}
            self._orders_cache[order_id] = normalized_order

            self.logger.debug(
                f"📬 Order Update: {order_id} | {symbol} | {status} | " f"{side} {quantity} @ {avg_price or price}"
            )

            # Invoke callback if registered
            if hasattr(self, "_order_update_callback") and self._order_update_callback:
                if asyncio.iscoroutinefunction(self._order_update_callback):
                    asyncio.create_task(self._order_update_callback(normalized_order))
                else:
                    self._order_update_callback(normalized_order)
                self.logger.debug(f"📞 Invoked order update callback for {order_id}")

        except Exception as e:
            self.logger.error(f"❌ Error handling order update: {e}")

    def _handle_account_update(self, msg):
        """Process ACCOUNT_UPDATE event from WebSocket."""
        try:
            account_data = msg.get("a", {})
            if not account_data:
                self.logger.warning("⚠️ ACCOUNT_UPDATE without account data")
                return

            # Update balances
            balances = account_data.get("B", [])
            if balances:
                if not hasattr(self, "_balance_cache"):
                    self._balance_cache = {"total": {}, "free": {}, "used": {}}

                for balance in balances:
                    asset = balance.get("a")
                    wallet_balance = float(balance.get("wb", 0))
                    available_balance = float(balance.get("cw", 0))

                    self._balance_cache["total"][asset] = wallet_balance
                    self._balance_cache["free"][asset] = available_balance
                    self._balance_cache["used"][asset] = wallet_balance - available_balance

                self.logger.debug(f"💰 Balance Updated: {len(balances)} assets")

            # Update positions
            positions = account_data.get("P", [])
            if positions:
                if not hasattr(self, "_positions_cache"):
                    self._positions_cache = []

                self._positions_cache = []
                for pos in positions:
                    amt = float(pos.get("pa", 0))
                    if amt == 0:
                        continue

                    self._positions_cache.append(
                        {
                            "symbol": pos.get("s"),
                            "side": "LONG" if amt > 0 else "SHORT",
                            "size": abs(amt),
                            "entry_price": float(pos.get("ep", 0)),
                            "mark_price": float(pos.get("mp", 0) or 0),
                            "unrealized_pnl": float(pos.get("up", 0)),
                            "timestamp": msg.get("E", int(time.time() * 1000)),
                            "info": pos,
                        }
                    )

                self.logger.debug(f"📊 Positions Updated: {len(self._positions_cache)} open")

        except Exception as e:
            self.logger.error(f"❌ Error handling account update: {e}")

    def _handle_ticker_update(self, msg):
        """Process ticker update event."""
        symbol = msg.get("s")
        # Normalize symbol if needed, but msg has native symbol
        # We need to map native symbol back to our symbol if possible,
        # or just store by native symbol and watch_ticker uses native symbol.

        # Queue dispatch
        if symbol in self._ticker_queues:
            # Extract volume (v for 24hr ticker, V for miniTicker)
            volume = float(msg.get("v", 0.0))
            ticker = {
                "symbol": symbol,
                "last": float(msg.get("c")),
                "timestamp": int(msg.get("E")),
                "volume": volume,
                "info": msg,
            }
            try:
                # Use put_nowait to avoid blocking callback
                self._ticker_queues[symbol].put_nowait(ticker)
            except asyncio.QueueFull:
                # Should not happen with infinite queue, but good practice
                pass

    def _handle_trade_update(self, msg):
        """Process trade update (aggTrade) event."""
        symbol = msg.get("s")

        if hasattr(self, "_trade_queues") and symbol in self._trade_queues:
            # aggTrade format:
            # "p": "Price",
            # "q": "Quantity",
            # "m": true/false (Is the buyer the market maker? -> True = Sell, False = Buy)

            is_buyer_maker = msg.get("m")
            side = "BID" if is_buyer_maker else "ASK"

            trade = {
                "symbol": symbol,
                "price": float(msg.get("p")),
                "amount": float(msg.get("q")),
                "side": side,
                "timestamp": int(msg.get("T")),
                "info": msg,
            }

            try:
                self._trade_queues[symbol].put_nowait(trade)
            except asyncio.QueueFull:
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
            self.ws_client.ticker(symbol=native_symbol.lower(), id=1)

        # Wait for next update
        return await self._ticker_queues[native_symbol].get()

    async def watch_trades(self, symbol: str) -> Dict[str, Any]:
        """Watch trades (WebSocket) - aggTrade stream."""
        native_symbol = self.normalize_symbol(symbol)

        if not hasattr(self, "_trade_queues"):
            self._trade_queues = {}

        if native_symbol not in self._trade_queues:
            self.logger.info(f"📡 Subscribing to trades (aggTrade) for {native_symbol}")
            self._trade_queues[native_symbol] = asyncio.Queue(maxsize=1000)
            # Subscribe via SDK to aggTrade stream
            self.ws_client.agg_trade(symbol=native_symbol.lower(), id=1)

        # Wait for next update
        return await self._trade_queues[native_symbol].get()

    # =========================================================
    # 💰 ACCOUNT DATA
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        try:
            async with self.rate_limiter.limit("account"):
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
                        "entry_price": float(p.get("entryPrice", 0)),
                        "mark_price": float(p.get("markPrice", 0)),
                        "liquidation_price": float(p.get("liquidationPrice", 0)),
                        "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                        "leverage": float(p.get("leverage", 1)),  # Default to 1x if not present
                        "timestamp": int(p.get("updateTime", 0)),
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
                # LIMIT orders require timeInForce
                if native_type == "LIMIT" and "timeInForce" not in args:
                    args["timeInForce"] = "GTC"

            if params:
                args.update(params)

            # Binance Futures One-Way Mode:
            # - No positionSide needed (default is BOTH, but usually omitted)
            # - reduceOnly=True for closing orders
            # - We do NOT automatically infer positionSide anymore
            if params and params.get("reduceOnly"):
                args["reduceOnly"] = "true"

            # Add timestamp and recvWindow
            args["timestamp"] = self._get_timestamp()
            args["recvWindow"] = 20000

            self.logger.info(f"📋 Sending Order: {args}")

            # Apply rate limiting for order creation
            async with self.rate_limiter.limit("orders"):
                response = self.client.new_order(**args)

            return self._normalize_order(response)

        except ClientError as e:
            self.logger.error(f"❌ Order Failed: {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Order Failed: {e}")
            raise

    async def create_market_order(
        self, symbol: str, side: str, amount: float, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a market order."""
        return await self.create_order(symbol, side, amount, order_type="MARKET", params=params)

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch order by ID."""
        try:
            native_symbol = self.normalize_symbol(symbol)

            # Apply rate limiting
            async with self.rate_limiter.limit("orders"):
                response = self.client.query_order(
                    symbol=native_symbol, orderId=int(order_id), timestamp=self._get_timestamp(), recvWindow=20000
                )

            return self._normalize_order(response)

        except ClientError as e:
            self.logger.error(f"❌ fetch_order failed: {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ fetch_order failed: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            native_symbol = self.normalize_symbol(symbol)

            # Apply rate limiting for order cancellation
            async with self.rate_limiter.limit("orders"):
                response = self.client.cancel_order(
                    symbol=native_symbol,
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
        price = float(response.get("avgPrice", 0) or 0)

        # Calculate fill price from cumQuote/executedQty if avgPrice is 0 (Market Order fix)
        if price == 0:
            cum_quote = float(response.get("cumQuote", 0) or 0)
            executed_qty = float(response.get("executedQty", 0) or 0)

            # DEBUG LOGGING
            if cum_quote > 0 or executed_qty > 0:
                self.logger.info(f"🔍 DEBUG Connector: avgPrice=0, cumQuote={cum_quote}, executedQty={executed_qty}")

            if cum_quote > 0 and executed_qty > 0:
                price = cum_quote / executed_qty
                self.logger.info(f"🔍 DEBUG Connector: Calculated price = {price}")

        return {
            "id": str(response["orderId"]),
            "order_id": str(response["orderId"]),  # Alias for internal consistency
            "symbol": response["symbol"],
            "status": self._normalize_order_status(response["status"]),
            "price": price,
            "amount": float(response["origQty"]),
            "filled": float(response["executedQty"]),
            "type": response["type"].lower(),
            "side": response["side"].lower(),
            "timestamp": response["updateTime"],
            "info": response,
        }

    async def fetch_my_trades(self, symbol: str = None, since: int = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch user's trade history.

        Args:
            symbol: Trading pair symbol (optional)
            since: Timestamp in ms to fetch trades from (optional)
            limit: Maximum number of trades to fetch (default: 100)

        Returns:
            List of normalized trade dictionaries
        """
        try:
            kwargs = {}
            if symbol:
                kwargs["symbol"] = self.normalize_symbol(symbol)
            if since:
                kwargs["startTime"] = since
            if limit:
                kwargs["limit"] = min(limit, 1000)  # Binance max is 1000

            kwargs["timestamp"] = self._get_timestamp()
            kwargs["recvWindow"] = 20000

            trades = self.client.get_account_trades(**kwargs)

            return [self._normalize_trade(t) for t in trades]
        except ClientError as e:
            self.logger.error(f"❌ fetch_my_trades failed: {e.error_message}")
            raise
        except Exception as e:
            self.logger.error(f"❌ fetch_my_trades failed: {e}")
            raise

    def _normalize_trade(self, raw_trade: Dict) -> Dict:
        """Normalize trade response to standard format."""
        return {
            "id": str(raw_trade["id"]),
            "order": str(raw_trade["orderId"]),
            "symbol": raw_trade["symbol"],
            "side": raw_trade["side"].lower(),
            "price": float(raw_trade["price"]),
            "amount": float(raw_trade["qty"]),
            "cost": float(raw_trade["quoteQty"]),
            "fee": {"cost": float(raw_trade["commission"]), "currency": raw_trade["commissionAsset"]},
            "timestamp": raw_trade["time"],
            "datetime": None,  # Can be calculated from timestamp if needed
            "info": raw_trade,
        }

    def normalize_trade(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a trade to standard format and detect closes.
        """
        info = raw_trade.get("info", {})
        # Binance Futures API returns 'realizedPnl' in trade/order update events
        realized_pnl = float(info.get("realizedPnl", 0) or 0)

        return {
            **raw_trade,
            "is_close": realized_pnl != 0,
            "realized_pnl": realized_pnl,
            "close_reason": "MANUAL" if realized_pnl != 0 else None,  # Simplified logic
        }
