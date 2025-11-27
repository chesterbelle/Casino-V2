"""Hyperliquid Connector - Exchange-Specific Implementation.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este conector maneja TODAS las particularidades específicas de Hyperliquid.
NO mover lógica específica de Hyperliquid al adaptador (CCXTAdapter).

Particularidades de Hyperliquid:
    - Base Currency: USDC
    - Symbols: "BTC/USDC:USDC" (Linear Swaps)
    - API: High performance, low latency
    - WebSocket: ccxt.pro support
    - Testnet: app.hyperliquid-testnet.xyz (API url different)

📚 Referencias:
    - Interface: exchanges/connectors/connector_base.py
    - CCXT Hyperliquid: https://docs.ccxt.com/#/exchanges/hyperliquid
================================================================================
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional, Union

import ccxt.async_support as ccxt_async
import ccxt.pro as ccxtpro

from ..connector_base import BaseConnector
from .hyperliquid_constants import BASE_CURRENCY, HYPERLIQUID_DEFAULT_CONFIG
from .hyperliquid_constants import denormalize_symbol as denormalize_hl_symbol
from .hyperliquid_constants import normalize_symbol as normalize_hl_symbol


class HyperliquidConnector(BaseConnector):
    """
    Connector for Hyperliquid exchange (USDC Perpetual).

    This connector handles all communication with Hyperliquid API,
    including REST and WebSocket connections.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: Literal["testing", "live"] = "testing",  # "testing" maps to testnet if needed, or just demo logic
        enable_websocket: bool = True,
    ):
        """
        Initialize Hyperliquid connector.

        Args:
            api_key: Wallet address (optional)
            secret: Private key (optional)
            mode: "testing" or "live"
            enable_websocket: Enable WebSocket monitoring
        """
        self.logger = logging.getLogger("HyperliquidConnector")
        self._mode = mode
        self.enable_websocket = enable_websocket

        # Load credentials from environment if not provided
        self._user_address = None
        if api_key is None or secret is None:
            self.logger.info("📝 Loading Hyperliquid credentials from environment...")
            loaded_creds = self._load_credentials()
            api_key = api_key or loaded_creds.get("walletAddress")
            secret = secret or loaded_creds.get("privateKey")
            self._user_address = loaded_creds.get("userAddress")

        if not secret:
            # Hyperliquid needs private key for trading. Wallet address can be derived or passed.
            # If no secret, we can only do read-only if supported, but for trading we need it.
            # We'll allow init without it but connect might fail or be read-only.
            self.logger.warning("⚠️ No private key provided. Trading will not be possible.")

        # Store credentials (normalize wallet address to lowercase as recommended by Hyperliquid docs)
        if api_key:
            api_key = api_key.lower()
        self._api_key = api_key
        self._secret = secret

        # Initialize CCXT exchange
        self.logger.info(f"🌐 Initializing Hyperliquid connection ({mode})...")
        config = HYPERLIQUID_DEFAULT_CONFIG.copy()

        # Configure credentials per CCXT Hyperliquid documentation:
        #  - walletAddress: MAIN WALLET (Master Account / EOA)
        #  - privateKey: AGENT WALLET private key (for signing)
        if self._secret:
            config["privateKey"] = self._secret
            self.logger.info("🔑 Using Agent Wallet private key for signing")
        else:
            self.logger.warning("⚠️ No private key provided - read-only mode")

        # Set walletAddress to Main Wallet (Master Account)
        if self._user_address:
            config["walletAddress"] = self._user_address
            self.logger.info(f"📬 Main Wallet configured: {self._user_address}")
        elif self._api_key:
            # Fallback: if no user_address, use api_key as wallet address
            config["walletAddress"] = self._api_key
            self.logger.info(f"📬 Wallet configured: {self._api_key}")

        # Initialize locks
        self._ccxt_lock = asyncio.Lock()
        self._markets_lock = asyncio.Lock()

        # Create exchange instance
        self.exchange = ccxt_async.hyperliquid(config)

        # Configure testnet if in testing mode
        if self._mode == "testing":
            self.logger.info("🧪 Configuring Hyperliquid TESTNET URLs...")
            # Override hostname to use testnet
            self.exchange.hostname = "hyperliquid-testnet.xyz"
            # Set testnet flag in options
            self.exchange.options["sandboxMode"] = True
            self.logger.info("✅ Testnet configured: https://api.hyperliquid-testnet.xyz")

        # CRITICAL: Set agentAddress in options to use the configured Agent Wallet
        # Without this, CCXT generates a "phantom agent" for each signature
        if self._api_key:
            self.exchange.options["agentAddress"] = self._api_key
            self.logger.info(f"🔐 Agent Wallet address configured in options: {self._api_key}")
        else:
            self.logger.info("🌐 Using Hyperliquid MAINNET")

        # Log what wallet address CCXT is actually using
        if hasattr(self.exchange, "walletAddress") and self.exchange.walletAddress:
            self.logger.info(f"📍 CCXT walletAddress: {self.exchange.walletAddress}")
        else:
            self.logger.warning("⚠️ CCXT walletAddress not set")

        self._connected = False
        self._ready = False

        # WebSocket state
        self.ws_exchange = None
        self._ws_connected = False
        self._order_monitor_task = None

    # =========================================================
    # 🔒 CCXT CONCURRENCY PROTECTION
    # =========================================================

    async def _safe_ccxt_call(self, method_name: str, *args, **kwargs):
        """Safely execute a method with concurrency protection."""
        async with self._ccxt_lock:
            method = getattr(self.exchange, method_name, None)
            if method is None:
                method = getattr(self, method_name)
            return await method(*args, **kwargs)

    # =========================================================
    # 📊 PROPERTIES
    # =========================================================

    @property
    def exchange_name(self) -> str:
        return "hyperliquid"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def ready(self) -> bool:
        return self._ready

    # =========================================================
    # 🔐 CREDENTIALS
    # =========================================================

    def _load_credentials(self) -> Dict[str, str]:
        """Load credentials from environment."""
        return {
            "walletAddress": os.getenv("HYPERLIQUID_WALLET_ADDRESS")
            or os.getenv("HYPERLIQUID_API_KEY")
            or os.getenv("HYPERLIQUID_API_WALLET"),
            "privateKey": os.getenv("HYPERLIQUID_PRIVATE_KEY")
            or os.getenv("HYPERLIQUID_SECRET")
            or os.getenv("HYPERLIQUID_API_SECRET"),
            "userAddress": os.getenv("HYPERLIQUID_MAIN_WALLET"),  # The vault/main wallet address
        }

    # =========================================================
    # 🔌 CONNECTION
    # =========================================================

    async def connect(self) -> None:
        """Connect to Hyperliquid exchange."""
        try:
            self.logger.info("🔌 Connecting to Hyperliquid...")

            # Load markets
            await self._safe_ccxt_call("load_markets")
            self.logger.info(f"✅ Markets loaded | Count: {len(self.exchange.markets)}")

            # Validate connection by fetching balance
            try:
                balance = await self._safe_ccxt_call("fetch_balance")
                usdc_balance = balance.get("total", {}).get(BASE_CURRENCY, 0)
                self.logger.info(f"✅ Balance fetched | {BASE_CURRENCY}: {usdc_balance}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not fetch balance (check credentials): {e}")

            self._connected = True
            self._ready = True

            # Initialize WebSocket
            if self.enable_websocket:
                await self._init_websocket()

            self.logger.info(f"✅ Hyperliquid connector ready | Mode: {self._mode}")

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Hyperliquid: {e}")
            # Allow partial connection
            self._connected = True
            self._ready = True

    async def close(self) -> None:
        """Close connection."""
        try:
            if self.ws_exchange:
                await self._close_websocket()

            if self.exchange:
                await self.exchange.close()

            self._connected = False
            self._ready = False
            self.logger.info("🔌 Connection to Hyperliquid closed")
        except Exception as e:
            self.logger.warning(f"⚠️ Error closing connection: {e}")

    # =========================================================
    # 🔄 SYMBOL NORMALIZATION
    # =========================================================

    def normalize_symbol(self, symbol: str) -> str:
        return normalize_hl_symbol(symbol)

    def denormalize_symbol(self, hl_symbol: str) -> str:
        return denormalize_hl_symbol(hl_symbol)

    # =========================================================
    # 💰 BALANCE & POSITIONS
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        try:
            # Hyperliquid Agent Wallet:
            # - Agent Wallet (API Wallet) signs transactions
            # - Main Wallet (user address) owns the funds
            # - We must query balance using Main Wallet address
            params = {}
            if self._user_address:
                # Use Main Wallet for balance queries
                params["user"] = self._user_address
                self.logger.debug(f"Querying balance for Main Wallet: {self._user_address}")
            elif self._api_key:
                # Fallback to api_key if no user_address (single wallet mode)
                params["user"] = self._api_key

            balance = await self._safe_ccxt_call("fetch_balance", params)
            return balance
        except Exception as e:
            self.logger.error(f"❌ Error fetching balance: {e}")
            raise

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        try:
            # Hyperliquid Agent Wallet: Query positions from Main Wallet
            params: Dict[str, Any] = {}
            if self._user_address:
                params["user"] = self._user_address
                self.logger.debug(f"Querying positions for Main Wallet: {self._user_address}")
            elif self._api_key:
                params["user"] = self._api_key

            # Hyperliquid fetch_positions usually returns all positions
            positions = await self._safe_ccxt_call("fetch_positions", symbols, params)

            # Filter active positions (size != 0)
            active_positions = [p for p in positions if abs(float(p.get("contracts", 0))) > 0]

            # Normalize if needed (CCXT usually does a good job)
            # Ensure leverage is present
            for p in active_positions:
                if p.get("leverage") is None:
                    p["leverage"] = 1.0  # Default fallback

            self.logger.debug(f"📊 Positions fetched: {len(active_positions)} active")
            return active_positions
        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
            raise

    # =========================================================
    # 🔍 VALIDATION HELPERS
    # =========================================================

    async def _validate_and_adjust_amount(self, symbol: str, amount: float) -> float:
        """
        Validate order amount according to exchange limits.

        This method validates that the order complies with:
        - Minimum amount
        - Maximum amount
        - Amount precision/step size

        Args:
            symbol: Symbol in exchange format (e.g., "BTC/USDT:USDT")
            amount: Requested amount

        Returns:
            Amount rounded to correct precision

        Raises:
            ValueError: If amount doesn't meet exchange requirements
        """
        try:
            # Get market info
            if not self.exchange.markets:
                await self._safe_ccxt_call("load_markets")

            market = self.exchange.markets.get(symbol)
            if not market:
                self.logger.warning(f"⚠️ Market info not found for {symbol}, skipping validation")
                return round(amount, 8)

            # Get limits
            limits = market.get("limits", {})
            amount_limits = limits.get("amount", {})

            # Convert to float to handle string values from exchange
            min_amount = float(amount_limits.get("min", 0)) if amount_limits.get("min") else 0
            max_amount = float(amount_limits.get("max", float("inf"))) if amount_limits.get("max") else float("inf")

            # Get precision (can be decimals or step size)
            precision = market.get("precision", {})
            amount_precision = precision.get("amount")

            # Handle precision: if it's a float < 1, it's a step size
            if amount_precision is None:
                amount_rounded = round(amount, 8)  # Default to 8 decimals
            elif isinstance(amount_precision, float) and amount_precision < 1:
                # It's a step size (e.g., 0.001) - round to nearest step
                import math

                amount_rounded = math.floor(amount / amount_precision) * amount_precision
                amount_rounded = round(amount_rounded, 8)  # Clean up floating point errors
            elif isinstance(amount_precision, int):
                # It's number of decimals
                amount_rounded = round(amount, amount_precision)
            else:
                # Fallback
                amount_rounded = round(amount, 8)

            # Validate minimum
            if min_amount and amount_rounded < min_amount:
                raise ValueError(
                    f"Order amount {amount} (rounded to {amount_rounded}) is below minimum {min_amount} for {symbol}. "
                    f"Please increase order size to at least {min_amount}."
                )

            # Validate maximum
            if max_amount and amount_rounded > max_amount:
                raise ValueError(
                    f"Order amount {amount_rounded} exceeds maximum {max_amount} for {symbol}. "
                    f"Please reduce order size."
                )

            self.logger.debug(
                f"✅ Amount validated: {amount_rounded} (min: {min_amount}, max: {max_amount}, precision: {amount_precision})"
            )

            return amount_rounded

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.warning(f"⚠️ Error during validation: {e}, skipping validation")
            return round(amount, 8)

    # =========================================================
    # 📝 ORDER CREATION
    # =========================================================

    def _format_number_for_hyperliquid(self, value: Union[int, float, str]) -> Union[float, str]:
        """
        Format number to remove trailing zeros as required by Hyperliquid API.

        Hyperliquid API doesn't accept trailing zeros in price and amount fields:
        - 12345.0 should be 12345
        - 0.123450 should be 0.12345
        - 135.7800000 should be 135.78

        Args:
            value: Number to format

        Returns:
            Formatted number without trailing zeros
        """
        if value is None:
            return None

        # Convert to float first to normalize
        try:
            float_val = float(value)
        except (ValueError, TypeError):
            return value

        # Convert to string to remove trailing zeros
        # Use format to avoid scientific notation for large numbers
        if float_val.is_integer():
            # For integers, return as int to remove .0
            return int(float_val)
        else:
            # For decimals, format to remove trailing zeros
            # Using g format removes trailing zeros and unnecessary decimal points
            formatted = f"{float_val:g}"
            return formatted if "." in formatted else float(formatted)

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
        confirm_with_ws: bool = False,
        ws_timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            hl_symbol = self.normalize_symbol(symbol)

            # Convert amount to float if it's a string
            if isinstance(amount, str):
                amount = float(amount)

            # Validate amount
            if amount is None or amount <= 0:
                raise ValueError(f"Invalid order amount: {amount}")

            # Validate and adjust amount according to exchange limits
            amount = await self._validate_and_adjust_amount(hl_symbol, amount)

            # Log order
            self.logger.info(
                f"📋 Creating order: symbol={hl_symbol}, side={side}, "
                f"amount={amount}, price={price}, type={order_type}"
            )

            clean_params = (params or {}).copy()

            # Hyperliquid requires price for market orders to calculate slippage
            # If it's a market order and no price provided, fetch current price
            if order_type.lower() == "market" and price is None:
                ticker = await self.fetch_ticker(symbol)
                price = float(ticker.get("last") or ticker.get("close"))
                self.logger.info(f"📊 Market order: using current price {price}")

            # Format price and amount to remove trailing zeros
            # Hyperliquid API requires numbers without trailing zeros (e.g., 135.78, not 135.7800000)
            if price is not None:
                original_price = price
                price = self._format_number_for_hyperliquid(price)
                self.logger.info(f"💰 Price formatted: {original_price} → {price}")
            original_amount = amount
            amount = self._format_number_for_hyperliquid(amount)
            self.logger.info(f"📊 Amount formatted: {original_amount} → {amount}")

            # Create order
            order_create_ts = time.time()
            order = await self._safe_ccxt_call(
                "create_order", hl_symbol, order_type, side.lower(), amount, price, clean_params
            )

            # Normalize response
            # Calculate price for market orders if needed
            order_price = float(order.get("price") or 0)
            if order_price == 0 and order_type.lower() == "market":
                filled = float(order.get("filled") or 0)
                cost = float(order.get("cost") or 0)
                if filled > 0 and cost > 0:
                    order_price = cost / filled

            avg_price = float(order.get("average") or order.get("avgPrice") or order_price)

            normalized = {
                "id": order.get("id"),
                "symbol": symbol,
                "side": side.lower(),
                "type": order_type,
                "status": order.get("status"),
                "price": order_price,
                "avgPrice": avg_price,
                "amount": float(order.get("amount") or 0),
                "filled": float(order.get("filled") or 0),
                "remaining": float(order.get("remaining") or 0),
                "cost": float(order.get("cost") or 0),
                "fee": order.get("fee", {}),
                "timestamp": order.get("timestamp"),
                "trades": order.get("trades", []),
                "order_create_ts": int(order_create_ts * 1000),
                "ws_confirm_ts": None,
                "used_ws_confirm": False,
                "used_rest_fallback": False,
            }

            self.logger.info(f"✅ Order created | {symbol} {side.upper()} {amount} @ {price or 'market'}")

            # WS Confirmation Logic (similar to Binance)
            if confirm_with_ws and (avg_price == 0.0 or normalized.get("filled", 0) == 0):
                await self._confirm_order_with_ws(normalized, ws_timeout_ms)

            return normalized

        except ccxt_async.InsufficientFunds as e:
            self.logger.error(f"❌ Insufficient funds: {e}")
            raise
        except ccxt_async.InvalidOrder as e:
            self.logger.error(f"❌ Invalid order: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error creating order: {e}")
            raise

    async def _confirm_order_with_ws(self, normalized_order: Dict[str, Any], timeout_ms: Optional[int] = None):
        """Wait for WS confirmation of order fill."""
        if not self._ws_connected or not self.ws_exchange:
            return

        timeout = (timeout_ms or 2000) / 1000.0
        deadline = time.time() + timeout

        try:
            # We need to watch orders for this symbol
            # Note: CCXT Pro watch_orders usually watches all user orders
            while time.time() < deadline:
                remaining = max(0.1, deadline - time.time())
                try:
                    orders = await asyncio.wait_for(
                        self.ws_exchange.watch_orders(None, None, None, {"type": "swap"}), timeout=remaining
                    )
                except asyncio.TimeoutError:
                    break

                if not isinstance(orders, list):
                    continue

                for o in orders:
                    if o.get("id") == normalized_order.get("id"):
                        # Found it
                        avg = o.get("average") or o.get("price")
                        if avg:
                            normalized_order["avgPrice"] = float(avg)
                        if o.get("filled") is not None:
                            normalized_order["filled"] = float(o.get("filled"))
                        normalized_order["used_ws_confirm"] = True
                        normalized_order["ws_confirm_ts"] = int(time.time() * 1000)
                        return

        except Exception as e:
            self.logger.debug(f"⚠️ WS confirmation failed: {e}")

        # Fallback to REST if WS failed
        if not normalized_order.get("used_ws_confirm"):
            try:
                fetched = await self._safe_ccxt_call(
                    "fetch_order", normalized_order["id"], self.normalize_symbol(normalized_order["symbol"])
                )
                avg = fetched.get("average") or fetched.get("price")
                if avg:
                    normalized_order["avgPrice"] = float(avg)
                    normalized_order["used_rest_fallback"] = True
            except Exception:
                pass

    # =========================================================
    # 📈 MARKET DATA
    # =========================================================

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1m", limit: int = 100, since: Optional[int] = None
    ) -> List[List]:
        try:
            hl_symbol = self.normalize_symbol(symbol)
            ohlcv = await self._safe_ccxt_call("fetch_ohlcv", hl_symbol, timeframe, since, limit)
            return ohlcv
        except Exception as e:
            self.logger.error(f"❌ Error fetching OHLCV: {e}")
            raise

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            hl_symbol = self.normalize_symbol(symbol)
            ticker = await self._safe_ccxt_call("fetch_ticker", hl_symbol)
            return ticker
        except Exception as e:
            self.logger.error(f"❌ Error fetching ticker: {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        try:
            hl_symbol = self.normalize_symbol(symbol)
            book = await self._safe_ccxt_call("fetch_order_book", hl_symbol, limit)
            return book
        except Exception as e:
            self.logger.error(f"❌ Error fetching order book: {e}")
            raise

    # =========================================================
    # 📝 ORDER MANAGEMENT
    # =========================================================

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open orders."""
        try:
            hl_symbol = self.normalize_symbol(symbol) if symbol else None

            # Hyperliquid requires wallet address in params
            params = {}
            if self._user_address:
                params["user"] = self._user_address
            elif hasattr(self.exchange, "walletAddress") and self.exchange.walletAddress:
                params["user"] = self.exchange.walletAddress

            orders = await self._safe_ccxt_call("fetch_open_orders", hl_symbol, params=params)
            return orders
        except Exception as e:
            self.logger.error(f"❌ Error fetching open orders: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            hl_symbol = self.normalize_symbol(symbol)
            clean_params = (params or {}).copy()

            # Hyperliquid requires wallet address in params
            if self._user_address:
                clean_params["user"] = self._user_address
            elif hasattr(self.exchange, "walletAddress") and self.exchange.walletAddress:
                clean_params["user"] = self.exchange.walletAddress

            result = await self._safe_ccxt_call("cancel_order", order_id, hl_symbol, clean_params)
            self.logger.info(f"✅ Order cancelled: {order_id}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error cancelling order: {e}")
            raise

    # =========================================================
    # 📜 TRADE HISTORY
    # =========================================================

    async def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            hl_symbol = self.normalize_symbol(symbol) if symbol else None
            trades = await self._safe_ccxt_call("fetch_my_trades", hl_symbol, since, limit)
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades: {e}")
            return []

    def normalize_trade(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Hyperliquid trade.

        Hyperliquid specific logic for detecting closes:
        - Check 'reduceOnly' or 'side' vs 'positionSide' if available.
        - Hyperliquid usually sends realizedPnl in fills if it's a close.
        """
        info = raw_trade.get("info", {})

        # Hyperliquid specific fields might vary, but CCXT often standardizes 'reduceOnly'
        is_reduce = raw_trade.get("reduceOnly", False)

        # Check for realized PnL in info (might be 'closedPnl' or similar)
        realized_pnl = 0.0
        if "closedPnl" in info:
            realized_pnl = float(info["closedPnl"])

        is_close = is_reduce or (realized_pnl != 0)

        close_reason = None
        if is_close:
            # Try to guess reason
            if "liquidation" in str(info).lower():
                close_reason = "LIQUIDATION"
            else:
                close_reason = "MANUAL"  # Default

        return {
            **raw_trade,
            "is_close": is_close,
            "realized_pnl": realized_pnl,
            "close_reason": close_reason,
        }

    # =========================================================
    # 🔌 WEBSOCKET METHODS
    # =========================================================

    async def _init_websocket(self) -> None:
        try:
            self.logger.info("🔌 Initializing WebSocket connection...")

            config = HYPERLIQUID_DEFAULT_CONFIG.copy()
            if self._secret:
                config["privateKey"] = self._secret
            # Propagate walletAddress to WS client so watch_orders has a user context
            if self._api_key:
                config["walletAddress"] = self._api_key

            self.ws_exchange = ccxtpro.hyperliquid(config)

            # Configure testnet if in testing mode
            if self._mode == "testing":
                self.ws_exchange.hostname = "hyperliquid-testnet.xyz"
                self.ws_exchange.options["testnet"] = True
                self.logger.info("✅ WebSocket testnet configured")

            # Mirror markets
            if getattr(self.exchange, "markets", None):
                self.ws_exchange.markets = self.exchange.markets

            self._ws_connected = True

            # Start monitoring orders via WebSocket
            # The _monitor_orders task is responsible for keeping the watch_orders loop running
            self._order_monitor_task = asyncio.create_task(self._monitor_orders())
            self.logger.info("✅ WebSocket connection initialized")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize WebSocket: {e}")
            self.ws_exchange = None
            self._ws_connected = False

    async def _close_websocket(self) -> None:
        try:
            if self._order_monitor_task:
                self._order_monitor_task.cancel()

            if self.ws_exchange:
                await self.ws_exchange.close()

            self._ws_connected = False
        except Exception as e:
            self.logger.warning(f"⚠️ Error closing WebSocket: {e}")

    async def _monitor_orders(self) -> None:
        """Monitor orders via WebSocket."""
        while self._ws_connected and self.ws_exchange:
            try:
                # Watch all orders - consume to keep connection alive and cache updated
                # The actual processing happens in PositionTracker or via confirm_with_ws
                await self.ws_exchange.watch_orders(None, None, None, {"type": "swap"})
            except Exception as e:
                self.logger.error(f"❌ WebSocket order monitoring error: {e}")
                await asyncio.sleep(1)
