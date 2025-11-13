"""Bybit Futures Connector - Exchange-Specific Implementation.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este conector maneja TODAS las particularidades específicas de Bybit Futures.
NO mover lógica específica de Bybit al adaptador (CCXTAdapter).

Particularidades de Bybit Futures:
    - TP/SL NATIVO: Soporta TP/SL en la misma orden (ventaja sobre Kraken)
    - API V5: Moderna y bien documentada
    - Categoría: "linear" para USDT Perpetual
    - Símbolos: "BTC/USD:USD" → "BTCUSDT"
    - Testnet: api-testnet.bybit.com
    - Live: api.bybit.com

Implementación de TP/SL (Bybit-specific):
    - create_order_with_tpsl() crea 1 orden con TP/SL integrado:
      {
          "takeProfit": tp_price,
          "stopLoss": sl_price,
          "tpOrderType": "Market",
          "slOrderType": "Market"
      }
    - NO necesita OCO Monitor (ventaja sobre Kraken)

🔄 DUAL CONNECTION (Demo Trading Only):
================================================================================
PROBLEMA: Bybit Demo Trading tiene APIs limitadas. No soporta endpoints públicos
como fetch_ticker(), fetch_order_book(), etc. Solo soporta endpoints de trading.

SOLUCIÓN: En modo "demo", este connector usa DOS conexiones:
    1. exchange_public  → Mainnet (sin auth) para datos públicos (ticker, orderbook)
    2. exchange_private → Demo Trading (con auth) para trading (orders, balance)

ROUTING DE MÉTODOS:
    - fetch_ticker()      → exchange_public  (precios reales de mainnet)
    - fetch_order_book()  → exchange_public  (datos públicos de mainnet)
    - fetch_balance()     → exchange_private (balance de demo)
    - create_order()      → exchange_private (órdenes en demo)
    - fetch_positions()   → exchange_private (posiciones de demo)

Modo "live": Solo usa una conexión (exchange = exchange_private = mainnet con auth)

IMPORTANTE: El adaptador (CCXTAdapter) NO necesita saber de esto. Es una
particularidad del exchange que se maneja internamente en el connector.
================================================================================

📚 Referencias:
    - Interface: exchanges/connectors/connector_base.py
    - Adaptador agnóstico: exchanges/adapters/ccxt_adapter.py
    - Bybit API: https://bybit-exchange.github.io/docs/v5/intro
    - Demo Trading: https://bybit-exchange.github.io/docs/v5/demo

================================================================================
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional

import aiohttp
import ccxt.async_support as ccxt_async
from dotenv import load_dotenv

from ..connector_base import BaseConnector
from .bybit_constants import (
    BASE_CURRENCY,
    BYBIT_DEFAULT_CONFIG,
    ORDER_TYPE_MARKET,
    POSITION_MODE_ONE_WAY,
    TPSL_MODE_FULL,
    TRIGGER_BY_LAST_PRICE,
)
from .bybit_constants import denormalize_symbol as denormalize_bybit_symbol
from .bybit_constants import normalize_symbol as normalize_bybit_symbol

# Load environment variables
load_dotenv()


class BybitConnector(BaseConnector):
    """
    Connector for Bybit Futures exchange (USDT Perpetual).

    This connector handles all communication with Bybit Futures API,
    including REST connections.

    Dual Connection (Demo Mode Only):
    - exchange_public: Mainnet for public data (ticker, orderbook) - real prices
    - exchange_private: Demo Trading for private data (orders, balance) - simulated
    - exchange: Alias to exchange_private for backward compatibility

    Live Mode:
    - exchange = exchange_private = exchange_public (single mainnet connection)

    Advantages over Kraken:
    - Native TP/SL support (no need for OCO Monitor)
    - Modern V5 API
    - More stable testnet
    - Better documentation
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: Literal["demo", "live"] = "demo",
        enable_websocket: bool = False,
        testnet: Optional[bool] = None,
    ):
        """
        Initialize Bybit connector.

        Args:
            api_key: Bybit API key (optional, loaded from env if not provided)
            secret: Bybit API secret (optional, loaded from env if not provided)
            mode: "demo" (Bybit Demo Trading) or "live" (Bybit Production)
            enable_websocket: Enable WebSocket (not implemented yet)
            testnet: Legacy parameter; if provided, overrides `mode`
        """
        self.logger = logging.getLogger("BybitConnector")

        # Handle legacy testnet parameter
        if testnet is not None:
            mode = "demo" if testnet else "live"

        if mode not in {"demo", "live"}:
            raise ValueError(f"Invalid mode for BybitConnector: {mode}")

        self._mode = mode
        self._demo = mode == "demo"
        self.enable_websocket = enable_websocket

        if mode == "live":
            self.logger.warning("=" * 60)
            self.logger.warning("🚨 BYBIT LIVE MODE ACTIVATED — REAL MONEY 🚨")
            self.logger.warning("=" * 60)

        # Load credentials from environment if not provided
        if api_key is None or secret is None:
            self.logger.info("📝 Loading Bybit credentials from environment...")
            loaded_creds = self._load_credentials()
            api_key = api_key or loaded_creds.get("apiKey")
            secret = secret or loaded_creds.get("secret")

        if not api_key or not secret:
            raise ValueError(
                "Bybit API credentials not provided and not found in environment. "
                "Set BYBIT_API_KEY and BYBIT_API_SECRET in your environment."
            )

        # Store credentials for direct API calls (demo mode)
        self._api_key = api_key
        self._secret = secret

        # Get URLs based on mode (commented out as not currently used)
        # urls = get_urls(mode)

        # Initialize CCXT exchange(s)
        if mode == "demo":
            # DUAL CONNECTION for Demo Trading
            # Problem: Demo Trading API has limited endpoints (no public data)
            # Solution: Use mainnet for public data + demo for private data

            self.logger.info("🔄 Initializing DUAL connection for Demo Trading...")

            # 1. Public connection (mainnet, no auth) - for ticker, orderbook, etc.
            config_public = BYBIT_DEFAULT_CONFIG.copy()
            # No API keys for public data
            self.exchange_public = ccxt_async.bybit(config_public)
            self.logger.info("  ✅ Public connection: Mainnet (real market prices)")

            # 2. Private connection (demo, with auth) - for orders, balance, positions
            config_private = BYBIT_DEFAULT_CONFIG.copy()
            config_private["apiKey"] = api_key
            config_private["secret"] = secret
            config_private["hostname"] = "bybit.com"
            config_private["urls"] = {
                "api": {
                    "spot": "https://api-demo.bybit.com",
                    "futures": "https://api-demo.bybit.com",
                    "v2": "https://api-demo.bybit.com",
                    "public": "https://api-demo.bybit.com",
                    "private": "https://api-demo.bybit.com",
                }
            }
            # CRITICAL: Disable fetchCurrencies to avoid unsupported endpoint
            config_private["options"]["fetchCurrencies"] = False
            self.exchange_private = ccxt_async.bybit(config_private)
            self.logger.info("  ✅ Private connection: Demo Trading (simulated orders)")

            # Backward compatibility: exchange points to private
            self.exchange = self.exchange_private

        else:
            # SINGLE CONNECTION for Live Trading
            self.logger.info("🌐 Initializing SINGLE connection for Live Trading...")
            config = BYBIT_DEFAULT_CONFIG.copy()
            config["apiKey"] = api_key
            config["secret"] = secret

            self.exchange = ccxt_async.bybit(config)
            # In live mode, public and private are the same
            self.exchange_public = self.exchange
            self.exchange_private = self.exchange
            self.logger.info("  ⚠️  LIVE MODE - REAL MONEY")
        self._connected = False
        self._ready = False

        # CCXT CONCURRENCY PROTECTION: Protect all CCXT calls from concurrent access
        self._ccxt_lock = asyncio.Lock()  # Protect CCXT internal state

        self.logger.info(f"✅ Bybit connector initialized | Mode: {mode.upper()}")

    # =========================================================
    # 📊 PROPERTIES
    # =========================================================

    @property
    def exchange_name(self) -> str:
        """
        Get exchange name.

        Returns:
            Exchange name
        """
        return "bybit"

    @property
    def is_connected(self) -> bool:
        """
        Check if connector is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    @property
    def ready(self) -> bool:
        """
        Check if connector is ready to operate.

        Returns:
            True if ready, False otherwise
        """
        return self._ready

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Get connector status dictionary.

        Returns:
            Dictionary with connection status
        """
        return {"connected": self._connected, "ready": self._ready}

    # =========================================================
    # 🔐 CREDENTIALS
    # =========================================================

    def _load_credentials(self) -> Dict[str, str]:
        """
        Load Bybit credentials from environment variables.

        Returns:
            Dict with apiKey and secret
        """
        api_key = os.getenv("BYBIT_API_KEY") or os.getenv("BYBIT_FUTURES_API_KEY")
        secret = os.getenv("BYBIT_API_SECRET") or os.getenv("BYBIT_FUTURES_API_SECRET")

        return {
            "apiKey": api_key or "",
            "secret": secret or "",
        }

    # =========================================================
    # 🔒 CCXT CONCURRENCY PROTECTION
    # =========================================================

    async def _safe_ccxt_call(self, method_name: str, *args, **kwargs):
        """
        Safely execute CCXT method with concurrency protection.
        Prevents KeyError: 0 and other concurrency issues in CCXT internal state.
        """
        async with self._ccxt_lock:
            method = getattr(self.exchange, method_name)
            return await method(*args, **kwargs)

    async def _safe_ccxt_call_on_exchange(self, exchange_instance, method_name: str, *args, **kwargs):
        """
        Safely execute CCXT method on specific exchange instance with concurrency protection.
        Used for dual exchange setup (public/private).
        """
        async with self._ccxt_lock:
            method = getattr(exchange_instance, method_name)
            return await method(*args, **kwargs)

    # =========================================================
    # 🔧 DIRECT API CALLS (Demo Mode Only)
    # =========================================================

    def _generate_signature(self, timestamp: str, params: str) -> str:
        """Generate HMAC SHA256 signature for Bybit API."""
        param_str = f"{timestamp}{self._api_key}{5000}{params}"
        return hmac.new(self._secret.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make direct HTTP request to Bybit API (demo mode only).

        This bypasses CCXT to avoid unsupported endpoints in demo trading.
        """
        url = f"https://api-demo.bybit.com{endpoint}"
        timestamp = str(int(time.time() * 1000))

        # Prepare params
        params_str = ""
        if params:
            params_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        # Generate signature
        signature = self._generate_signature(timestamp, params_str)

        # Headers
        headers = {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": "5000",
            "Content-Type": "application/json",
        }

        # Make request
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                full_url = f"{url}?{params_str}" if params_str else url
                async with session.get(full_url, headers=headers) as response:
                    data = await response.json()
            else:
                async with session.post(url, headers=headers, json=params or {}) as response:
                    data = await response.json()

        # Check for errors
        if data.get("retCode") != 0:
            raise Exception(f"Bybit API error: {data}")

        return data.get("result", {})

    async def _fetch_balance_direct(self) -> Dict[str, Any]:
        """Fetch balance using direct API call (demo mode)."""
        result = await self._make_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})

        # Convert to CCXT format
        balance = {"free": {}, "used": {}, "total": {}, "info": result}

        if "list" in result and result["list"]:
            account = result["list"][0]
            for coin in account.get("coin", []):
                currency = coin.get("coin")
                if currency:
                    # Safely convert to float, defaulting to 0 for empty strings
                    available = coin.get("availableToWithdraw", "0") or "0"
                    locked = coin.get("locked", "0") or "0"
                    wallet = coin.get("walletBalance", "0") or "0"

                    balance["free"][currency] = float(available)
                    balance["used"][currency] = float(locked)
                    balance["total"][currency] = float(wallet)

        return balance

    async def _fetch_positions_direct(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch positions using direct API call (demo mode)."""
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbols:
            params["symbol"] = symbols[0] if len(symbols) == 1 else None

        result = await self._make_request("GET", "/v5/position/list", params)

        # Convert to CCXT format
        positions = []
        for pos in result.get("list", []):
            if float(pos.get("size", 0)) > 0:
                positions.append(
                    {
                        "symbol": pos.get("symbol"),
                        "side": pos.get("side"),
                        "contracts": float(pos.get("size", 0)),
                        "contractSize": 1,
                        "unrealizedPnl": float(pos.get("unrealisedPnl", 0)),
                        "leverage": float(pos.get("leverage", 1)),
                        "entryPrice": float(pos.get("avgPrice", 0)),
                        "markPrice": float(pos.get("markPrice", 0)),
                        "liquidationPrice": float(pos.get("liqPrice", 0)),
                        "info": pos,
                    }
                )

        return positions

    async def _fetch_my_trades_direct(
        self, symbol: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch my trades using direct API call (demo mode)."""
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = self.normalize_symbol(symbol)
        if limit:
            params["limit"] = limit

        result = await self._make_request("GET", "/v5/execution/list", params)

        # Convert to CCXT format
        trades = []
        for trade in result.get("list", []):
            trades.append(
                {
                    "id": trade.get("execId"),
                    "order": trade.get("orderId"),
                    "symbol": trade.get("symbol"),
                    "side": trade.get("side").lower(),
                    "price": float(trade.get("execPrice", 0)),
                    "amount": float(trade.get("execQty", 0)),
                    "cost": float(trade.get("execValue", 0)),
                    "fee": {"cost": float(trade.get("execFee", 0)), "currency": "USDT"},
                    "timestamp": int(trade.get("execTime", 0)),
                    "info": trade,
                }
            )

        return trades

    async def _fetch_open_orders_direct(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open orders using direct API call (demo mode)."""
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = self.normalize_symbol(symbol)

        result = await self._make_request("GET", "/v5/order/realtime", params)

        # Convert to CCXT format
        orders = []
        for order in result.get("list", []):
            orders.append(
                {
                    "id": order.get("orderId"),
                    "symbol": order.get("symbol"),
                    "type": order.get("orderType").lower(),
                    "side": order.get("side").lower(),
                    "price": float(order.get("price", 0)),
                    "amount": float(order.get("qty", 0)),
                    "filled": float(order.get("cumExecQty", 0)),
                    "remaining": float(order.get("leavesQty", 0)),
                    "status": order.get("orderStatus").lower(),
                    "timestamp": int(order.get("createdTime", 0)),
                    "info": order,
                }
            )

        return orders

    # =========================================================
    # 🔌 CONNECTION
    # =========================================================

    async def connect(self) -> None:
        """
        Connect to Bybit exchange.

        In demo mode, connects both public (mainnet) and private (demo) exchanges.
        In live mode, connects single exchange.

        This method loads markets and validates the connection.
        """
        try:
            self.logger.info("🔌 Connecting to Bybit...")

            # Load markets from public exchange (mainnet for real market data)
            await self.exchange_public.load_markets()
            self.logger.info(f"✅ Public exchange connected | Markets: {len(self.exchange_public.markets)}")

            # In demo mode, also connect private exchange
            if self._demo:
                # Private exchange doesn't need to load markets (uses public markets)
                # Just verify it's initialized
                self.logger.info("✅ Private exchange (demo) ready for trading")

            self._connected = True
            self._ready = True
            self.logger.info(f"✅ Bybit connector ready | Mode: {self._mode.upper()}")

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Bybit: {e}")
            raise

    async def close(self) -> None:
        """Close connection to Bybit exchange."""
        try:
            # Close public exchange
            # PROTECTED: Prevent CCXT concurrent access
            if hasattr(self.exchange_public, "close"):
                await self._safe_ccxt_call_on_exchange(self.exchange_public, "close")

            # In demo mode, also close private exchange if it's different
            if self._demo and self.exchange_private != self.exchange_public:
                # PROTECTED: Prevent CCXT concurrent access
                if hasattr(self.exchange_private, "close"):
                    await self._safe_ccxt_call_on_exchange(self.exchange_private, "close")

            self._connected = False
            self._ready = False
            self.logger.info("🔌 Connection to Bybit closed")
        except Exception as e:
            self.logger.warning(f"⚠️ Error closing Bybit connection: {e}")

    async def disconnect(self) -> None:
        """Alias for close() for compatibility."""
        await self.close()

    # =========================================================
    # 🔄 SYMBOL NORMALIZATION
    # =========================================================

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol from bot format to Bybit format.

        Args:
            symbol: Symbol in bot format (e.g., "BTC/USD:USD")

        Returns:
            Symbol in Bybit format (e.g., "BTCUSDT")
        """
        return normalize_bybit_symbol(symbol)

    def denormalize_symbol(self, bybit_symbol: str) -> str:
        """
        Denormalize symbol from Bybit format to bot format.

        Args:
            bybit_symbol: Symbol in Bybit format (e.g., "BTCUSDT")

        Returns:
            Symbol in bot format (e.g., "BTC/USD:USD")
        """
        return denormalize_bybit_symbol(bybit_symbol)

    # =========================================================
    # 💰 BALANCE & POSITIONS
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance from Bybit.

        In demo mode: Uses direct API call to /v5/account/wallet-balance
        In live mode: Uses CCXT's fetch_balance()

        Returns:
            Balance dictionary in CCXT format
        """
        try:
            if self._demo:
                # Demo mode: Direct API call (CCXT tries to call unsupported endpoint)
                return await self._fetch_balance_direct()
            else:
                # Live mode: Use CCXT
                balance = await self.exchange_private.fetch_balance()
                self.logger.debug(
                    f"💰 Balance fetched: {balance.get('total', {}).get(BASE_CURRENCY, 0)} {BASE_CURRENCY}"
                )
                return balance
        except Exception as e:
            self.logger.error(f"❌ Error fetching balance: {e}")
            raise

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch open positions from Bybit.

        In demo mode: Uses direct API call to /v5/position/list
        In live mode: Uses CCXT's fetch_positions()

        Args:
            symbols: Optional list of symbols to filter

        Returns:
            List of positions in CCXT format
        """
        try:
            if self._demo:
                # Demo mode: Direct API call
                return await self._fetch_positions_direct(symbols)
            else:
                # Live mode: Use CCXT
                positions = await self.exchange_private.fetch_positions(symbols)
                self.logger.debug(f"📊 Positions fetched: {len(positions)}")
                return positions
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
                # PROTECTED: Prevent CCXT concurrent access
                await self._safe_ccxt_call("load_markets")

            market = self.exchange.markets.get(symbol)
            if not market:
                self.logger.warning(f"⚠️ Market info not found for {symbol}, skipping validation")
                return round(amount, 8)

            # Get limits
            limits = market.get("limits", {})
            amount_limits = limits.get("amount", {})

            min_amount = amount_limits.get("min", 0)
            max_amount = amount_limits.get("max", float("inf"))

            # Get precision
            precision = market.get("precision", {})
            amount_precision = precision.get("amount")

            # Ensure precision is a valid integer
            if amount_precision is None or not isinstance(amount_precision, (int, float)):
                amount_precision = 8  # Default precision
            else:
                amount_precision = int(amount_precision)

            # Round to precision
            amount_rounded = round(amount, amount_precision)

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

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an order on Bybit.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD:USD")
            side: Order side - 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price (required for limit orders)
            order_type: Order type - 'market' or 'limit'
            params: Additional Bybit-specific parameters

        Returns:
            Normalized order result in CCXT format
        """
        try:
            # Normalize symbol to Bybit format
            bybit_symbol = self.normalize_symbol(symbol)

            # Validate amount
            if amount is None or amount <= 0:
                raise ValueError(f"Invalid order amount: {amount}")

            # Validate and adjust amount according to exchange limits
            amount = await self._validate_and_adjust_amount(bybit_symbol, amount)

            # Log order details
            self.logger.info(
                f"📋 Creating order: symbol={bybit_symbol}, side={side}, "
                f"amount={amount}, price={price}, type={order_type}"
            )

            # Clean params
            clean_params = (params or {}).copy()

            # Add Bybit-specific params
            if "positionIdx" not in clean_params:
                clean_params["positionIdx"] = POSITION_MODE_ONE_WAY  # One-way mode by default

            # Create order on Bybit
            # PROTECTED: Prevent CCXT concurrent access
            order = await self._safe_ccxt_call(
                "create_order",
                bybit_symbol,
                order_type,
                side.lower(),
                amount,
                price,
                clean_params,
            )

            # Normalize response
            normalized = {
                "id": order.get("id"),
                "symbol": symbol,  # Return in bot format
                "side": side.lower(),
                "type": order_type,
                "status": order.get("status"),
                "price": float(order.get("price") or 0),
                "amount": float(order.get("amount") or 0),
                "filled": float(order.get("filled") or 0),
                "remaining": float(order.get("remaining") or 0),
                "cost": float(order.get("cost") or 0),
                "fee": order.get("fee", {}),
                "timestamp": order.get("timestamp"),
                "trades": order.get("trades", []),
            }

            self.logger.info(f"✅ Order created | {symbol} {side.upper()} {amount} @ {price or 'market'}")

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

    # =========================================================
    # 🎯 ORDER WITH TP/SL (NATIVE BYBIT SUPPORT)
    # =========================================================

    async def create_order_with_tpsl(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        """
        Create an order with Take Profit and Stop Loss using Bybit's native support.

        **VENTAJA SOBRE KRAKEN**: Bybit soporta TP/SL en la misma orden.
        No necesita crear 3 órdenes separadas ni OCO Monitor.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD:USD")
            side: "buy" or "sell"
            amount: Order amount
            price: Limit price (for limit orders)
            order_type: "market" or "limit"
            tp_price: Take Profit trigger price
            sl_price: Stop Loss trigger price
            params: Additional parameters

        Returns:
            Order information

        Example:
            >>> order = await connector.create_order_with_tpsl(
            ...     symbol="BTC/USD:USD",
            ...     side="buy",
            ...     amount=0.01,
            ...     order_type="market",
            ...     tp_price=50000,
            ...     sl_price=48000
            ... )
        """
        # Validate TP/SL prices
        if price is not None and (tp_price or sl_price):
            if tp_price and side == "buy" and tp_price <= price:
                raise ValueError("TP must be greater than entry price for BUY orders")
            if tp_price and side == "sell" and tp_price >= price:
                raise ValueError("TP must be less than entry price for SELL orders")
            if sl_price and side == "buy" and sl_price >= price:
                raise ValueError("SL must be less than entry price for BUY orders")
            if sl_price and side == "sell" and sl_price <= price:
                raise ValueError("SL must be greater than entry price for SELL orders")

        # Prepare params with TP/SL
        order_params = (params or {}).copy()

        # Add TP/SL to params (Bybit native support)
        if tp_price:
            order_params["takeProfit"] = str(tp_price)
            order_params["tpOrderType"] = ORDER_TYPE_MARKET  # Market TP for immediate execution
            order_params["tpTriggerBy"] = TRIGGER_BY_LAST_PRICE
            self.logger.info(f"✅ Take Profit set: {tp_price}")

        if sl_price:
            order_params["stopLoss"] = str(sl_price)
            order_params["slOrderType"] = ORDER_TYPE_MARKET  # Market SL for immediate execution
            order_params["slTriggerBy"] = TRIGGER_BY_LAST_PRICE
            self.logger.info(f"✅ Stop Loss set: {sl_price}")

        # Set TP/SL mode
        if tp_price or sl_price:
            order_params["tpslMode"] = TPSL_MODE_FULL  # Full position TP/SL

        # Create order with TP/SL
        main_order = await self.create_order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            params=order_params,
        )

        self.logger.info(
            f"✅ Order with TP/SL created | "
            f"ID: {main_order['id']} | "
            f"TP: {tp_price or 'None'} | "
            f"SL: {sl_price or 'None'}"
        )

        # Add TP/SL prices to result for backtest compatibility
        main_order["tp_price"] = tp_price
        main_order["sl_price"] = sl_price

        return main_order

    # =========================================================
    # 📊 ORDER QUERIES
    # =========================================================

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch order information from Bybit.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Order information
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            order = await self.exchange_private.fetch_order(order_id, bybit_symbol)
            return order
        except Exception as e:
            self.logger.error(f"❌ Error fetching order: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an order on Bybit.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Cancellation result
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            # PROTECTED: Prevent CCXT concurrent access
            result = await self._safe_ccxt_call("cancel_order", order_id, bybit_symbol)
            self.logger.info(f"❌ Order canceled: {order_id}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error canceling order: {e}")
            raise

    # =========================================================
    # 📊 MARKET INFO
    # =========================================================

    async def load_markets(self) -> Dict[str, Any]:
        """
        Load markets from Bybit.

        Uses exchange_public (mainnet) in demo mode for real market info.

        Returns:
            Dictionary of markets
        """
        try:
            if not hasattr(self.exchange_public, "markets") or not self.exchange_public.markets:
                await self.exchange_public.load_markets()
            return self.exchange_public.markets
        except Exception as e:
            self.logger.error(f"❌ Error loading markets: {e}")
            raise

    @property
    def timeframes(self) -> Dict[str, str]:
        """
        Get available timeframes.

        Returns:
            Dictionary of timeframes
        """
        return self.exchange.timeframes if hasattr(self.exchange, "timeframes") else {}

    # =========================================================
    # 📈 MARKET DATA
    # =========================================================

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data from Bybit.

        Uses exchange_public (mainnet) in demo mode for real market prices.

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker data
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            self.logger.info(f"🔍 fetch_ticker | input={symbol} | normalized={bybit_symbol}")
            ticker = await self.exchange_public.fetch_ticker(bybit_symbol)
            self.logger.info(
                f"📊 ticker received | "
                f"symbol={ticker.get('symbol')} | "
                f"last={ticker.get('last')} | "
                f"bid={ticker.get('bid')} | "
                f"ask={ticker.get('ask')} | "
                f"high={ticker.get('high')} | "
                f"low={ticker.get('low')}"
            )
            return ticker
        except Exception as e:
            self.logger.error(f"❌ Error fetching ticker: {e}")
            raise

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[List]:
        """
        Fetch OHLCV (candlestick) data from Bybit.

        Uses exchange_public (mainnet) in demo mode for real market data.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., "1m", "5m", "1h")
            since: Timestamp in ms
            limit: Number of candles

        Returns:
            List of OHLCV data
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            ohlcv = await self.exchange_public.fetch_ohlcv(bybit_symbol, timeframe, since, limit)
            return ohlcv
        except Exception as e:
            self.logger.error(f"❌ Error fetching OHLCV: {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch order book from Bybit.

        Uses exchange_public (mainnet) in demo mode for real market data.

        Args:
            symbol: Trading pair symbol
            limit: Depth limit

        Returns:
            Order book data
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            order_book = await self.exchange_public.fetch_order_book(bybit_symbol, limit)
            return order_book
        except Exception as e:
            self.logger.error(f"❌ Error fetching order book: {e}")
            raise

    async def fetch_trades(self, symbol: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch recent trades from Bybit.

        Uses exchange_public (mainnet) in demo mode for real market data.

        Args:
            symbol: Trading pair symbol
            limit: Number of trades

        Returns:
            List of trades
        """
        try:
            bybit_symbol = self.normalize_symbol(symbol)
            trades = await self.exchange_public.fetch_trades(bybit_symbol, limit=limit)
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades: {e}")
            raise

    async def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch my trades from Bybit.

        In demo mode: Uses direct API call to /v5/execution/list
        In live mode: Uses CCXT's fetch_my_trades()

        Args:
            symbol: Trading pair symbol (optional)
            since: Timestamp in ms (optional, not used in demo mode)
            limit: Number of trades

        Returns:
            List of my trades
        """
        try:
            if self._demo:
                # Demo mode: Direct API call (since not supported)
                return await self._fetch_my_trades_direct(symbol, limit)
            else:
                # Live mode: Use CCXT
                bybit_symbol = self.normalize_symbol(symbol) if symbol else None
                trades = await self.exchange_private.fetch_my_trades(bybit_symbol, since=since, limit=limit)
                return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching my trades: {e}")
            raise

    def normalize_trade(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a Bybit trade to detect position closes.

        Bybit-specific fields:
            - info.closedPnl: PnL realized from this trade (string)
            - info.execType: "Trade", "Funding", "AdlTrade", etc.
            - info.orderType: Order type

        A trade is a close if:
            - closedPnl != "0" (Bybit returns string "0" for non-closes)

        Args:
            raw_trade: Raw trade from CCXT

        Returns:
            Normalized trade with is_close, realized_pnl, close_reason
        """
        info = raw_trade.get("info", {})

        # Bybit returns closedPnl as string
        closed_pnl_str = info.get("closedPnl", "0")
        realized_pnl = float(closed_pnl_str) if closed_pnl_str else 0.0

        # A trade is a close if closedPnl != 0
        is_close = realized_pnl != 0.0

        # Try to detect close reason from order type
        close_reason = None
        if is_close:
            order_type = info.get("orderType", "").upper()
            if "LIMIT" in order_type:
                close_reason = "TP"
            elif "MARKET" in order_type:
                # Could be SL or manual, check stopOrderType
                stop_order_type = info.get("stopOrderType", "")
                if stop_order_type:
                    close_reason = "SL"
                else:
                    close_reason = "MANUAL"
            else:
                close_reason = "MANUAL"

        return {
            **raw_trade,
            "is_close": is_close,
            "realized_pnl": realized_pnl,
            "close_reason": close_reason,
        }

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch open orders from Bybit.

        In demo mode: Uses direct API call to /v5/order/realtime
        In live mode: Uses CCXT's fetch_open_orders()

        Args:
            symbol: Trading pair symbol (optional)

        Returns:
            List of open orders
        """
        try:
            if self._demo:
                # Demo mode: Direct API call
                return await self._fetch_open_orders_direct(symbol)
            else:
                # Live mode: Use CCXT
                bybit_symbol = self.normalize_symbol(symbol) if symbol else None
                orders = await self.exchange_private.fetch_open_orders(bybit_symbol)
                return orders
        except Exception as e:
            self.logger.error(f"❌ Error fetching open orders: {e}")
            raise
