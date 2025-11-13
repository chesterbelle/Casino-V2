"""Binance Futures Connector - Exchange-Specific Implementation.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este conector maneja TODAS las particularidades específicas de Binance Futures.
NO mover lógica específica de Binance al adaptador (CCXTAdapter).

Particularidades de Binance Futures:
    - TP/SL: Soporta stopPrice y stopLimitPrice en params
    - API: Moderna y bien documentada
    - Símbolos: "BTC/USD:USD" → "BTC/USDT:USDT"
    - Testnet: testnet.binancefuture.com
    - Live: fapi.binance.com

Implementación de TP/SL (Binance-specific):
    - create_order_with_tpsl() crea 1 orden principal + 2 órdenes condicionales:
      * Orden principal (market/limit)
      * Take Profit order (TAKE_PROFIT_MARKET)
      * Stop Loss order (STOP_MARKET)
    - Binance NO soporta TP/SL en la misma orden como Bybit
    - Necesita crear 3 órdenes separadas (similar a Kraken)
    - Comportamiento OCO: Usando timeInForce=GTE_GTC + closePosition=True,
      cuando una orden (TP o SL) se ejecuta, la otra se cancela automáticamente

🔄 TESTNET vs LIVE:
================================================================================
- Testnet: testnet.binancefuture.com (simulación con datos reales, sin riesgo)
- Live: fapi.binance.com (dinero real)

El testnet de Binance Futures está activo y funcional.
CCXT tiene un bug con la opción "testnet", pero se puede usar configurando
manualmente las URLs del testnet.

📚 Referencias:
    - Interface: exchanges/connectors/connector_base.py
    - Adaptador agnóstico: exchanges/adapters/ccxt_adapter.py
    - Binance API: https://binance-docs.github.io/apidocs/futures/en/
    - CCXT Binance: https://docs.ccxt.com/#/exchanges/binance

================================================================================
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Literal, Optional

import ccxt.async_support as ccxt_async
import ccxt.pro as ccxtpro

from ..connector_base import BaseConnector
from .binance_constants import (
    BASE_CURRENCY,
    BINANCE_DEFAULT_CONFIG,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    TIME_IN_FORCE_GTE_GTC,
    WORKING_TYPE_CONTRACT_PRICE,
)
from .binance_constants import denormalize_symbol as denormalize_binance_symbol
from .binance_constants import normalize_symbol as normalize_binance_symbol

# =========================================================
# 🔧 CUSTOM CCXT CLASS FOR TESTNET
# =========================================================


class BinanceTestnetPro(ccxtpro.binance):
    """
    Custom Binance Pro class for testnet WebSocket connections.

    This class extends CCXT Pro to support Binance Futures testnet WebSocket streams.
    """

    def describe(self):
        """Override describe() to force testnet URLs for WebSocket endpoints."""
        testnet_base = "https://testnet.binancefuture.com"
        testnet_ws_api = "wss://testnet.binancefuture.com/ws-fapi/v1"
        testnet_ws_stream = "wss://stream.binancefuture.com/ws"

        return self.deep_extend(
            super().describe(),
            {
                "urls": {
                    "api": {
                        # Main endpoints - redirect to futures testnet
                        "public": f"{testnet_base}/fapi/v1",
                        "private": f"{testnet_base}/fapi/v1",
                        # Futures endpoints
                        "fapiPublic": f"{testnet_base}/fapi/v1",
                        "fapiPrivate": f"{testnet_base}/fapi/v1",
                        "fapiPublicV2": f"{testnet_base}/fapi/v2",
                        "fapiPrivateV2": f"{testnet_base}/fapi/v2",
                        # Delivery endpoints
                        "dapiPublic": f"{testnet_base}/dapi/v1",
                        "dapiPrivate": f"{testnet_base}/dapi/v1",
                        # SAPI endpoints (spot/margin) - redirect to futures testnet
                        "sapi": f"{testnet_base}/fapi/v1",
                        "sapiV2": f"{testnet_base}/fapi/v2",
                        "sapiV3": f"{testnet_base}/fapi/v1",
                        # WebSocket endpoints
                        "ws": {
                            # API WebSocket (for orders, account data)
                            "fapiPrivate": testnet_ws_api,
                            # Stream WebSocket (for market data)
                            "fapiPublic": testnet_ws_stream,
                            # Other WebSocket streams - redirect to testnet
                            "spot": testnet_ws_stream,
                            "margin": testnet_ws_stream,
                            "future": testnet_ws_stream,
                            "delivery": testnet_ws_stream,
                            "ws-api": {
                                "spot": testnet_ws_api,
                                "future": testnet_ws_api,
                                "delivery": testnet_ws_api,
                            },
                        },
                    }
                }
            },
        )

    async def load_markets(self, reload=False, params={}):
        """Override load_markets to ONLY load futures markets."""
        markets = self.markets
        if not markets or reload:
            # Only fetch futures markets, skip spot/margin
            response = await self.fapiPublicGetExchangeInfo(params)
            # Parse the response - use parent's parse_markets
            markets = self.parse_markets(response["symbols"])
            # Store in correct format
            self.markets = self.index_by(markets, "symbol")
            self.markets_by_id = self.index_by(markets, "id")
            self.currencies_by_id = {}
            self.currencies = {}
        return markets

    async def fetch_currencies(self, params={}):
        """Override to avoid spot currency calls in futures testnet."""
        # Return empty currencies for futures testnet
        return {}

    async def fetch_trading_fees(self, params={}):
        """Override to avoid margin trading fees calls."""
        # Return default futures fees
        return {}


class BinanceTestnet(ccxt_async.binance):
    """
    Custom Binance class that overrides URLs to point to testnet.

    This is necessary because CCXT hardcodes URLs internally and ignores
    the 'urls' config parameter for Binance Futures testnet.
    """

    def describe(self):
        """Override describe() to force testnet URLs for ALL endpoints."""
        testnet_base = "https://testnet.binancefuture.com"
        return self.deep_extend(
            super().describe(),
            {
                "urls": {
                    "api": {
                        # Main endpoints
                        "public": f"{testnet_base}/fapi/v1",
                        "private": f"{testnet_base}/fapi/v1",
                        # Futures endpoints
                        "fapiPublic": f"{testnet_base}/fapi/v1",
                        "fapiPrivate": f"{testnet_base}/fapi/v1",
                        "fapiPublicV2": f"{testnet_base}/fapi/v2",
                        "fapiPrivateV2": f"{testnet_base}/fapi/v2",
                        # Delivery endpoints
                        "dapiPublic": f"{testnet_base}/dapi/v1",
                        "dapiPrivate": f"{testnet_base}/dapi/v1",
                        # SAPI endpoints (spot/margin) - redirect to futures testnet
                        # These don't exist on testnet but we redirect to avoid errors
                        "sapi": f"{testnet_base}/fapi/v1",
                        "sapiV2": f"{testnet_base}/fapi/v2",
                        "sapiV3": f"{testnet_base}/fapi/v1",
                    }
                }
            },
        )

    async def fetch_markets(self, params={}):
        """Override fetch_markets to ONLY fetch futures markets."""
        # Only fetch futures markets, skip spot/margin
        return await self.fapiPublicGetExchangeInfo(params)

    async def load_markets(self, reload=False, params={}):
        """Override load_markets to ONLY load futures markets."""
        markets = self.markets
        if not markets or reload:
            response = await self.fetch_markets(params)
            # Parse the response - use parent's parse_markets
            markets = self.parse_markets(response["symbols"])
            # Store in correct format
            self.markets = self.index_by(markets, "symbol")
            self.markets_by_id = self.index_by(markets, "id")
            # Also store as list for safe_market lookups
            self.symbols = [m["symbol"] for m in markets]
            self.ids = [m["id"] for m in markets]
            self.currencies_by_id = {}
        return self.markets

    async def fetch_balance(self, params={}):
        """Override fetch_balance to ONLY call futures endpoints."""
        # Direct call to futures balance endpoint
        await self.load_markets()
        response = await self.fapiPrivateV2GetAccount(params)

        # Parse futures balance manually
        result = {"info": response, "timestamp": None, "datetime": None}
        balances = {}

        if "assets" in response:
            for asset in response["assets"]:
                code = self.safe_currency_code(asset["asset"])
                account = self.account()
                account["free"] = self.safe_string(asset, "availableBalance")
                account["used"] = self.safe_string(asset, "initialMargin")
                account["total"] = self.safe_string(asset, "walletBalance")
                balances[code] = account

        result = self.safe_balance(self.extend(result, balances))
        return result

    async def fetch_positions(self, symbols=None, params={}):
        """Override fetch_positions to use futures endpoint directly and parse manually."""
        await self.load_markets()
        response = await self.fapiPrivateV2GetPositionRisk(params)

        # Parse positions manually to avoid safe_market KeyError
        positions = []
        for position in response:
            symbol_id = self.safe_string(position, "symbol")
            # Find market by id
            market = None
            for s, m in self.markets.items():
                if m["id"] == symbol_id:
                    market = m
                    break

            if market is None:
                continue

            contracts = self.safe_number(position, "positionAmt")
            if contracts == 0:
                continue

            positions.append(
                {
                    "info": position,
                    "symbol": market["symbol"],
                    "contracts": abs(contracts),
                    "contractSize": self.safe_number(market, "contractSize", 1),
                    "side": "long" if contracts > 0 else "short",
                    "notional": self.safe_number(position, "notional"),
                    "leverage": self.safe_number(position, "leverage"),
                    "unrealizedPnl": self.safe_number(position, "unRealizedProfit"),
                    "percentage": None,
                    "entryPrice": self.safe_number(position, "entryPrice"),
                    "markPrice": self.safe_number(position, "markPrice"),
                    "liquidationPrice": self.safe_number(position, "liquidationPrice"),
                    "marginMode": self.safe_string_lower(position, "marginType"),
                    "hedged": False,
                    "timestamp": self.safe_integer(position, "updateTime"),
                    "datetime": self.iso8601(self.safe_integer(position, "updateTime")),
                }
            )

        return self.filter_by_array(positions, "symbol", symbols, False) if symbols else positions

    async def fetch_ticker(self, symbol, params={}):
        """Override fetch_ticker to avoid safe_market issues."""
        await self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"]}
        response = await self.fapiPublicGetTicker24hr(self.extend(request, params))
        # Parse manually to avoid safe_market KeyError
        return {
            "symbol": symbol,
            "timestamp": self.safe_integer(response, "closeTime"),
            "datetime": self.iso8601(self.safe_integer(response, "closeTime")),
            "high": self.safe_number(response, "highPrice"),
            "low": self.safe_number(response, "lowPrice"),
            "bid": self.safe_number(response, "bidPrice"),
            "ask": self.safe_number(response, "askPrice"),
            "last": self.safe_number(response, "lastPrice"),
            "close": self.safe_number(response, "lastPrice"),
            "baseVolume": self.safe_number(response, "volume"),
            "quoteVolume": self.safe_number(response, "quoteVolume"),
            "info": response,
        }

    async def create_order(self, symbol, type, side, amount, price=None, params={}):
        """Override create_order to avoid safe_market issues in parse_order."""
        await self.load_markets()
        market = self.market(symbol)

        # Build request
        request = {
            "symbol": market["id"],
            "side": side.upper(),
            "type": type.upper(),
        }

        # Add quantity
        request["quantity"] = self.amount_to_precision(symbol, amount)

        # Add price for limit orders
        if price is not None:
            request["price"] = self.price_to_precision(symbol, price)

        # Merge params
        request = self.extend(request, params)

        # Call appropriate endpoint
        response = await self.fapiPrivatePostOrder(request)

        # Parse manually to avoid safe_market KeyError
        return {
            "id": self.safe_string(response, "orderId"),
            "clientOrderId": self.safe_string(response, "clientOrderId"),
            "timestamp": self.safe_integer(response, "updateTime"),
            "datetime": self.iso8601(self.safe_integer(response, "updateTime")),
            "symbol": symbol,
            "type": type,
            "side": side,
            "price": self.safe_number(response, "price"),
            "amount": self.safe_number(response, "origQty"),
            "filled": self.safe_number(response, "executedQty"),
            "remaining": self.safe_number(response, "origQty") - self.safe_number(response, "executedQty"),
            "status": self.parse_order_status(self.safe_string(response, "status")),
            "info": response,
        }

    async def fetch_my_trades(self, symbol=None, since=None, limit=None, params={}):
        """Override fetch_my_trades to avoid safe_market issues."""
        await self.load_markets()
        request = {}
        market = None

        if symbol is not None:
            market = self.market(symbol)
            request["symbol"] = market["id"]

        if limit is not None:
            request["limit"] = limit

        if since is not None:
            request["startTime"] = since

        response = await self.fapiPrivateGetUserTrades(self.extend(request, params))

        # Parse trades manually
        trades = []
        for trade in response:
            trades.append(
                {
                    "id": self.safe_string(trade, "id"),
                    "order": self.safe_string(trade, "orderId"),
                    "timestamp": self.safe_integer(trade, "time"),
                    "datetime": self.iso8601(self.safe_integer(trade, "time")),
                    "symbol": symbol if symbol else self.safe_string(trade, "symbol"),
                    "type": None,
                    "side": self.safe_string_lower(trade, "side"),
                    "price": self.safe_number(trade, "price"),
                    "amount": self.safe_number(trade, "qty"),
                    "cost": self.safe_number(trade, "quoteQty"),
                    "fee": {
                        "cost": self.safe_number(trade, "commission"),
                        "currency": self.safe_string(trade, "commissionAsset"),
                    },
                    "info": trade,
                }
            )

        return trades

    async def fetch_open_orders(self, symbol=None, since=None, limit=None, params={}):
        """Override fetch_open_orders to avoid safe_market issues."""
        await self.load_markets()
        request = {}

        if symbol is not None:
            market = self.market(symbol)
            request["symbol"] = market["id"]

        response = await self.fapiPrivateGetOpenOrders(self.extend(request, params))

        # Parse orders manually
        orders = []
        for order in response:
            orders.append(
                {
                    "id": self.safe_string(order, "orderId"),
                    "clientOrderId": self.safe_string(order, "clientOrderId"),
                    "timestamp": self.safe_integer(order, "time"),
                    "datetime": self.iso8601(self.safe_integer(order, "time")),
                    "symbol": symbol if symbol else self.safe_string(order, "symbol"),
                    "type": self.safe_string_lower(order, "type"),
                    "side": self.safe_string_lower(order, "side"),
                    "price": self.safe_number(order, "price"),
                    "amount": self.safe_number(order, "origQty"),
                    "filled": self.safe_number(order, "executedQty"),
                    "remaining": self.safe_number(order, "origQty") - self.safe_number(order, "executedQty"),
                    "status": self.parse_order_status(self.safe_string(order, "status")),
                    "info": order,
                }
            )

        return orders

    async def cancel_order(self, id, symbol=None, params={}):
        """Override cancel_order to avoid safe_market issues."""
        await self.load_markets()

        if symbol is None:
            raise ValueError("cancel_order() requires a symbol argument")

        market = self.market(symbol)
        request = {
            "symbol": market["id"],
            "orderId": id,
        }

        response = await self.fapiPrivateDeleteOrder(self.extend(request, params))

        return {
            "id": self.safe_string(response, "orderId"),
            "symbol": symbol,
            "status": "canceled",
            "info": response,
        }

    async def fapiPrivateV3GetOrder(self, params={}):
        """
        Direct API call to get order details from Binance Futures API v3.
        This method is used as a fallback when CCXT's fetch_order fails.
        """
        if "symbol" not in params or "orderId" not in params:
            raise ValueError("fapiPrivateV3GetOrder requires 'symbol' and 'orderId' parameters")

        # Use the private API endpoint directly
        return await self.fapiPrivateGetOrder(params)


class BinanceConnector(BaseConnector):
    """
    Connector for Binance Futures exchange (USDT Perpetual).

    This connector handles all communication with Binance Futures API,
    including REST and WebSocket connections.

    Testnet vs Live:
    - testnet: Binance Futures Testnet (simulated trading)
    - live: Binance Futures Production (real money)

    TP/SL Implementation:
    - Binance requires 3 separate orders (main + TP + SL)
    - Similar to Kraken, but with different order types
    - Uses TAKE_PROFIT_MARKET and STOP_MARKET order types
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: Literal["testnet", "live"] = "testnet",
        enable_websocket: bool = True,
    ):
        """
        Initialize Binance connector.

        Args:
            api_key: Binance API key (optional, loaded from env if not provided)
            secret: Binance API secret (optional, loaded from env if not provided)
            mode: "testnet" for testnet (recommended), "live" for production
            enable_websocket: Enable WebSocket + OCO manual monitoring
                            (default: True, auto-enabled in testnet since OCO doesn't work automatically)
        """
        self.logger = logging.getLogger("BinanceConnector")

        if mode not in {"testnet", "live"}:
            raise ValueError(f"Invalid mode for BinanceConnector: {mode}")

        self._mode = mode
        self._testnet = mode == "testnet"

        # Auto-enable WebSocket + OCO manual in testnet (OCO doesn't work automatically)
        if self._testnet and not enable_websocket:
            self.logger.info(
                "🧪 Testnet detected - Auto-enabling WebSocket + OCO manual (OCO doesn't work automatically in testnet)"
            )
            self.enable_websocket = True
        else:
            self.enable_websocket = enable_websocket

        if mode == "live":
            self.logger.warning("=" * 60)
            self.logger.warning("🚨 BINANCE LIVE MODE ACTIVATED — REAL MONEY 🚨")
            self.logger.warning("=" * 60)

        # Load credentials from environment if not provided
        if api_key is None or secret is None:
            self.logger.info("📝 Loading Binance credentials from environment...")
            loaded_creds = self._load_credentials()
            api_key = api_key or loaded_creds.get("apiKey")
            secret = secret or loaded_creds.get("secret")

        if not api_key or not secret:
            raise ValueError(
                "Binance API credentials not provided and not found in environment. "
                "Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET (or BINANCE_API_KEY/BINANCE_SECRET for live) "
                "in your environment."
            )

        # Store credentials
        self._api_key = api_key
        self._secret = secret

        # Initialize CCXT exchange
        self.logger.info(f"🌐 Initializing Binance Futures connection ({mode})...")
        config = BINANCE_DEFAULT_CONFIG.copy()
        config["apiKey"] = api_key
        config["secret"] = secret

        # CRÍTICO: Configurar opciones para evitar problemas de auth
        config["options"]["fetchCurrencies"] = False
        config["options"]["recvWindow"] = 60000
        config["options"]["warnOnFetchOpenOrdersWithoutSymbol"] = False

        # Crear exchange - usar clase custom para testnet
        if self._testnet:
            # Usar BinanceTestnet que sobrescribe describe() para forzar URLs de testnet
            self.exchange = BinanceTestnet(config)
            self.logger.info("🧪 Testnet mode enabled with custom BinanceTestnet class")
        else:
            # Usar clase estándar de CCXT para live
            self.exchange = ccxt_async.binance(config)

        self._connected = False
        self._ready = False

        # Initialize WebSocket (CCXT Pro) if enabled
        self.ws_exchange = None
        self._ws_connected = False
        self._order_monitor_task = None
        self._active_orders = {}  # Track TP/SL orders for OCO
        self._oco_lock = asyncio.Lock()  # Prevent concurrent modifications (Hummingbot pattern)

        # HUMMINGBOT CLOCK PATTERN: Central clock coordinates all tasks
        self._clock_task = None
        self._clock_running = False
        self._last_tick = 0

        # CCXT CONCURRENCY PROTECTION: Protect all CCXT calls from concurrent access
        self._ccxt_lock = asyncio.Lock()  # Protect CCXT internal state

        if self.enable_websocket:
            self.logger.info("🔌 WebSocket enabled - will initialize on connect()")

        self.logger.info(f"✅ Binance connector initialized | Mode: {mode.upper()}")

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
        return "binance"

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
        Load Binance credentials from environment variables.

        Returns:
            Dict with apiKey and secret
        """
        if self._testnet:
            # Load testnet credentials
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            secret = os.getenv("BINANCE_TESTNET_SECRET")
        else:
            # Load live credentials
            api_key = os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_FUTURES_API_KEY")
            secret = os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_FUTURES_API_SECRET")

        return {
            "apiKey": api_key or "",
            "secret": secret or "",
        }

    # =========================================================
    # 🔌 CONNECTION
    # =========================================================

    async def connect(self) -> None:
        """
        Connect to Binance exchange.

        This method loads markets and validates the connection.
        """
        try:
            self.logger.info("🔌 Connecting to Binance Futures...")

            # Try to load markets - if fails, continue anyway
            try:
                await self.exchange.load_markets()
                self.logger.info(f"✅ Markets loaded | Count: {len(self.exchange.markets)}")
            except Exception as market_error:
                self.logger.warning(f"⚠️  Could not load markets: {market_error}")
                self.logger.warning("⚠️  Continuing without market data (will fetch on demand)")

            # Try to fetch balance to validate credentials
            try:
                balance = await self.exchange.fetch_balance()
                usdt_balance = balance.get("total", {}).get(BASE_CURRENCY, 0)
                self.logger.info(f"✅ Balance fetched | {BASE_CURRENCY}: {usdt_balance}")
            except Exception as balance_error:
                self.logger.warning(f"⚠️  Could not fetch balance: {balance_error}")
                self.logger.warning("⚠️  API keys may need specific permissions enabled")
                self.logger.warning("⚠️  Required: Enable Reading + Futures Trading permissions")

            self._connected = True
            self._ready = True

            # Start WebSocket monitoring if enabled
            if self.enable_websocket:
                # CORRECCIÓN CRÍTICA: Inicializar WebSocket ANTES de crear tasks
                await self._init_websocket()

                if self._ws_connected:  # Solo crear tasks si WebSocket está conectado
                    self._ws_task = asyncio.create_task(self._monitor_orders())
                    self.logger.info("👁️ Order monitoring started")
                else:
                    self.logger.warning("⚠️ WebSocket failed to connect, falling back to REST-only")

                # OCO Manual INDEPENDIENTE del WebSocket (usa self._connected)
                self._oco_task = asyncio.create_task(self._oco_monitor_loop())
                self.logger.info("🎯 OCO Manual monitoring started (independent task)")

            self.logger.info(f"✅ Binance connector ready | Mode: {self._mode.upper()}")

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Binance: {e}")
            # Don't raise - allow connection even if some endpoints fail
            self._connected = True
            self._ready = True
            self.logger.warning("⚠️  Connected with limited functionality")

    async def close(self) -> None:
        """Close connection to Binance exchange."""
        try:
            # Close WebSocket connection if active
            if self.ws_exchange:
                await self._close_websocket()

            await self.exchange.close()
            self._connected = False
            self._ready = False
            self.logger.info("🔌 Connection to Binance closed")
        except Exception as e:
            self.logger.warning(f"⚠️ Error closing Binance connection: {e}")

    async def disconnect(self) -> None:
        """Alias for close() for compatibility."""
        await self.close()

    # =========================================================
    # 🔄 SYMBOL NORMALIZATION
    # =========================================================

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol from bot format to Binance format.

        Args:
            symbol: Symbol in bot format (e.g., "BTC/USD:USD")

        Returns:
            Symbol in Binance format (e.g., "BTC/USDT:USDT")
        """
        return normalize_binance_symbol(symbol)

    def denormalize_symbol(self, binance_symbol: str) -> str:
        """
        Denormalize symbol from Binance format to bot format.

        Args:
            binance_symbol: Symbol in Binance format (e.g., "BTCUSDT")

        Returns:
            Symbol in bot format (e.g., "BTC/USD:USD")
        """
        return denormalize_binance_symbol(binance_symbol)

    # =========================================================
    # 💰 BALANCE & POSITIONS
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance from Binance Futures.

        Returns:
            Balance dictionary in CCXT format
        """
        try:
            # IMPORTANTE: Usar fetch_balance con params para forzar solo futures
            # Esto evita que CCXT intente llamar endpoints de SPOT/MARGIN
            balance = await self.exchange.fetch_balance(params={"type": "future"})
            self.logger.debug(f"💰 Balance fetched: {balance.get('total', {}).get(BASE_CURRENCY, 0)} {BASE_CURRENCY}")
            return balance
        except Exception as e:
            self.logger.error(f"❌ Error fetching balance: {e}")
            raise

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch open positions from Binance.

        Args:
            symbols: Optional list of symbols to filter

        Returns:
            List of positions in CCXT format

        Raises:
            ExchangeError: If exchange returns an error
        """
        try:
            # Call exchange method which uses our BinanceTestnet override
            positions = await self.exchange.fetch_positions(symbols)
            # Filter out empty positions (contracts > 0)
            active_positions = [p for p in positions if abs(float(p.get("contracts", 0))) > 0]
            self.logger.debug(f"📊 Positions fetched: {len(active_positions)} active")
            return active_positions
        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
            raise  # Fail-fast: let the adapter handle the error

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
                await self.exchange.load_markets()

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
                amount_precision = 8  # Default to 8 decimals
                amount_rounded = round(amount, amount_precision)
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
        Create an order on Binance.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD:USD")
            side: Order side - 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price (required for limit orders)
            order_type: Order type - 'market' or 'limit'
            params: Additional Binance-specific parameters

        Returns:
            Normalized order result in CCXT format
        """
        try:
            # Normalize symbol to Binance format
            binance_symbol = self.normalize_symbol(symbol)

            # Convert amount to float if it's a string (can happen from exchange responses)
            if isinstance(amount, str):
                amount = float(amount)

            # Validate amount
            if amount is None or amount <= 0:
                raise ValueError(f"Invalid order amount: {amount}")

            # Validate and adjust amount according to exchange limits
            amount = await self._validate_and_adjust_amount(binance_symbol, amount)

            # Log order details
            self.logger.info(
                f"📋 Creating order: symbol={binance_symbol}, side={side}, "
                f"amount={amount}, price={price}, type={order_type}"
            )

            # Clean params
            clean_params = (params or {}).copy()

            # Add Binance-specific params
            if "positionSide" not in clean_params:
                clean_params["positionSide"] = "BOTH"  # One-way mode by default

            # Create order on Binance
            order = await self.exchange.create_order(
                symbol=binance_symbol,
                type=order_type,
                side=side.lower(),
                amount=amount,
                price=price,
                params=clean_params,
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
    # 🎯 ORDER WITH TP/SL (BINANCE-SPECIFIC)
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
        Create an order with Take Profit and Stop Loss on Binance.

        **IMPORTANTE**: Binance NO soporta TP/SL en la misma orden como Bybit.
        Necesita crear 3 órdenes separadas:
        1. Orden principal (market/limit)
        2. Take Profit order (TAKE_PROFIT_MARKET)
        3. Stop Loss order (STOP_MARKET)

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
            Main order information (TP/SL orders are created but not returned)

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

        # Create main order
        main_order = await self.create_order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            params=params,
        )

        # CRITICAL: Wait for position to be updated on exchange before creating TP/SL
        # Binance needs time to update position state for GTE_GTC orders
        # Without this delay, we get error -4129: "GTE can only be used with open positions"
        import asyncio

        await asyncio.sleep(1)

        # Determine closing side (opposite of entry)
        close_side = "sell" if side == "buy" else "buy"

        # Create Take Profit order if specified
        tp_order_id = None
        if tp_price:
            try:
                # Round TP price to correct precision
                binance_symbol = self.normalize_symbol(symbol)
                tp_price_rounded = float(self.exchange.price_to_precision(binance_symbol, tp_price))

                tp_params = {
                    "stopPrice": tp_price_rounded,
                    "workingType": WORKING_TYPE_CONTRACT_PRICE,
                    "positionSide": "BOTH",
                    "timeInForce": TIME_IN_FORCE_GTE_GTC,  # Habilita OCO: cancela SL cuando TP se ejecuta
                }
                tp_order = await self.exchange.create_order(
                    symbol=binance_symbol,
                    type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                    side=close_side,
                    amount=amount,
                    params=tp_params,
                )
                tp_order_id = tp_order.get("id")
                self.logger.info(f"✅ Take Profit order created at {tp_price_rounded}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create TP order: {e}")
                # Don't raise, main order is already created

        # Create Stop Loss order if specified
        sl_order_id = None
        if sl_price:
            try:
                # Round SL price to correct precision
                binance_symbol = self.normalize_symbol(symbol)
                sl_price_rounded = float(self.exchange.price_to_precision(binance_symbol, sl_price))

                sl_params = {
                    "stopPrice": sl_price_rounded,
                    "workingType": WORKING_TYPE_CONTRACT_PRICE,
                    "positionSide": "BOTH",
                    "timeInForce": TIME_IN_FORCE_GTE_GTC,  # Habilita OCO: cancela TP cuando SL se ejecuta
                }
                sl_order = await self.exchange.create_order(
                    symbol=binance_symbol,
                    type=ORDER_TYPE_STOP_MARKET,
                    side=close_side,
                    amount=amount,
                    params=sl_params,
                )
                sl_order_id = sl_order.get("id")
                self.logger.info(f"✅ Stop Loss order created at {sl_price_rounded}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create SL order: {e}")
                # Don't raise, main order is already created

        # Register TP/SL for WebSocket OCO monitoring
        # Note: Binance only allows ONE closing order per position (error -4130)
        # So we register whichever order was created successfully
        self.logger.info(
            f"🔍 OCO Registration Debug: websocket={self.enable_websocket}, tp_id={tp_order_id}, sl_id={sl_order_id}"
        )
        if self.enable_websocket and (tp_order_id or sl_order_id):
            if tp_order_id and sl_order_id:
                # Both created - register for OCO monitoring
                self.logger.info(f"📝 Registering TP/SL pair for OCO monitoring: TP={tp_order_id}, SL={sl_order_id}")
                await self._register_tpsl_pair(symbol, tp_order_id, sl_order_id)
            elif tp_order_id:
                # Only TP created - register for monitoring
                self.logger.info(f"📝 Registering single TP order for monitoring: {tp_order_id}")
                await self._register_single_order(symbol, tp_order_id, "TP", sl_price)
            elif sl_order_id:
                # Only SL created - register for monitoring
                self.logger.info(f"📝 Registering single SL order for monitoring: {sl_order_id}")
                await self._register_single_order(symbol, sl_order_id, "SL", tp_price)
        else:
            self.logger.warning(
                f"⚠️ OCO registration skipped: websocket={self.enable_websocket}, orders={tp_order_id or sl_order_id}"
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
        Fetch order information from Binance.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Order information
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            order = await self.exchange.fetch_order(order_id, binance_symbol)
            self.logger.debug(f"📊 Order fetched: {order_id}")
            return order
        except Exception as e:
            self.logger.error(f"❌ Error fetching order: {e}")
            raise

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch open orders from Binance.

        Args:
            symbol: Optional symbol to filter

        Returns:
            List of open orders
        """
        try:
            binance_symbol = self.normalize_symbol(symbol) if symbol else None
            orders = await self.exchange.fetch_open_orders(binance_symbol)
            self.logger.debug(f"📊 Open orders fetched: {len(orders)}")
            return orders
        except Exception as e:
            self.logger.error(f"❌ Error fetching open orders: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an order on Binance.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Cancellation result
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            result = await self.exchange.cancel_order(order_id, binance_symbol)
            self.logger.info(f"✅ Order cancelled: {order_id}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error cancelling order: {e}")
            raise

    async def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Cancel all open orders for a symbol on Binance.

        Args:
            symbol: Trading pair symbol

        Returns:
            List of cancellation results
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)

            # Get all open orders first
            open_orders = await self.fetch_open_orders(symbol)

            if not open_orders:
                self.logger.info(f"ℹ️ No open orders to cancel for {symbol}")
                return []

            # Cancel each order
            results = []
            for order in open_orders:
                try:
                    result = await self.exchange.cancel_order(order["id"], binance_symbol)
                    results.append(result)
                    self.logger.info(f"✅ Order cancelled: {order['id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to cancel order {order['id']}: {e}")

            self.logger.info(f"✅ Cancelled {len(results)}/{len(open_orders)} orders for {symbol}")
            return results

        except Exception as e:
            self.logger.error(f"❌ Error cancelling all orders: {e}")
            raise

    # =========================================================
    # 📈 MARKET DATA
    # =========================================================

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data from Binance.

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker data

        Raises:
            BadSymbol: If symbol is invalid
            ExchangeError: If exchange returns an error
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            ticker = await self.exchange.fetch_ticker(binance_symbol)
            self.logger.debug(f"📊 Ticker fetched: {symbol} @ {ticker.get('last', 0)}")
            return ticker
        except Exception as e:
            self.logger.error(f"❌ Error fetching ticker {symbol}: {e}")
            raise  # Fail-fast: let the adapter handle the error

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1m", limit: int = 100, since: Optional[int] = None
    ) -> List[List]:
        """
        Fetch OHLCV data from Binance.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1m', '5m', '1h')
            limit: Number of candles to fetch
            since: Timestamp in ms (optional)

        Returns:
            List of OHLCV candles
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            ohlcv = await self.exchange.fetch_ohlcv(binance_symbol, timeframe, since, limit)
            self.logger.debug(f"📊 OHLCV fetched: {symbol} {timeframe} ({len(ohlcv)} candles)")
            return ohlcv
        except Exception as e:
            self.logger.error(f"❌ Error fetching OHLCV: {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch order book from Binance.

        Args:
            symbol: Trading pair symbol
            limit: Depth limit

        Returns:
            Order book data
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            order_book = await self.exchange.fetch_order_book(binance_symbol, limit)
            self.logger.debug(f"📊 Order book fetched: {symbol}")
            return order_book
        except Exception as e:
            self.logger.error(f"❌ Error fetching order book: {e}")
            raise

    # =========================================================
    # 📜 TRADE HISTORY
    # =========================================================

    async def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch user's trade history from Binance.

        Args:
            symbol: Trading pair symbol (optional)
            since: Timestamp in milliseconds to fetch trades from (optional)
            limit: Maximum number of trades to fetch (optional)

        Returns:
            List of trades
        """
        try:
            binance_symbol = self.normalize_symbol(symbol) if symbol else None
            trades = await self.exchange.fetch_my_trades(binance_symbol, since=since, limit=limit)
            self.logger.debug(f"📊 Trades fetched: {len(trades)}")
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades: {e}")
            raise

    def normalize_trade(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a Binance trade to detect position closes.

        Binance-specific fields:
            - info.realizedPnl: PnL realized from this trade (string, "0" if not a close)
            - info.positionSide: "BOTH", "LONG", or "SHORT"
            - info.side: "BUY" or "SELL"

        A trade is a close if:
            - realizedPnl != "0" (Binance returns string "0" for non-closes)

        Args:
            raw_trade: Raw trade from CCXT

        Returns:
            Normalized trade with is_close, realized_pnl, close_reason
        """
        info = raw_trade.get("info", {})

        # Binance returns realizedPnl as string
        realized_pnl_str = info.get("realizedPnl", "0")
        realized_pnl = float(realized_pnl_str) if realized_pnl_str else 0.0

        # A trade is a close if realizedPnl != 0
        is_close = realized_pnl != 0.0

        # Try to detect close reason from order type
        close_reason = None
        if is_close:
            order_type = info.get("type", "").upper()
            if "TAKE_PROFIT" in order_type:
                close_reason = "TP"
            elif "STOP" in order_type or "STOP_MARKET" in order_type:
                close_reason = "SL"
            else:
                close_reason = "MANUAL"

        return {
            **raw_trade,
            "is_close": is_close,
            "realized_pnl": realized_pnl,
            "close_reason": close_reason,
        }

    async def fetch_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent public trades from Binance.

        Args:
            symbol: Trading pair symbol
            limit: Number of trades to fetch

        Returns:
            List of trades
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            trades = await self.exchange.fetch_trades(binance_symbol, limit=limit)
            self.logger.debug(f"📊 Public trades fetched: {len(trades)}")
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching public trades: {e}")
            raise

    # =========================================================
    # 📋 MARKET INFO
    # =========================================================

    async def load_markets(self) -> Dict[str, Any]:
        """
        Load market information from Binance.

        Returns:
            Dictionary of markets
        """
        try:
            markets = await self.exchange.load_markets()
            self.logger.debug(f"📊 Markets loaded: {len(markets)}")
            return markets
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
    # 🔌 WEBSOCKET METHODS (CCXT Pro)
    # =========================================================

    async def _init_websocket(self) -> None:
        """Initialize WebSocket connection using CCXT Pro."""
        try:
            self.logger.info("🔌 Initializing WebSocket connection...")

            # Create CCXT Pro exchange instance
            config = {
                "apiKey": self._api_key,
                "secret": self._secret,
                "options": {
                    "defaultType": "future",
                    "recvWindow": 60000,
                },
            }

            # Use custom class for testnet, standard for live
            if self._testnet:
                self.ws_exchange = BinanceTestnetPro(config)
                self.logger.info("🧪 Using BinanceTestnetPro for WebSocket testnet")
            else:
                self.ws_exchange = ccxtpro.binance(config)

            # Start order monitoring task
            if not self._order_monitor_task or self._order_monitor_task.done():
                self._order_monitor_task = asyncio.create_task(self._monitor_orders())

            self._ws_connected = True
            self.logger.info("✅ WebSocket connection initialized")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize WebSocket: {e}")
            self.logger.warning("⚠️ Falling back to REST-only mode")
            self.ws_exchange = None
            self._ws_connected = False

    async def _close_websocket(self) -> None:
        """Close WebSocket connection."""
        try:
            # Cancel WebSocket task
            if hasattr(self, "_ws_task") and self._ws_task:
                self._ws_task.cancel()
                try:
                    await self._ws_task
                except asyncio.CancelledError:
                    pass

            # Cancel OCO Manual task
            if hasattr(self, "_oco_task") and self._oco_task:
                self._oco_task.cancel()
                try:
                    await self._oco_task
                except asyncio.CancelledError:
                    pass

            if self._order_monitor_task and not self._order_monitor_task.done():
                self._order_monitor_task.cancel()
                try:
                    await self._order_monitor_task
                except asyncio.CancelledError:
                    pass

            if self.ws_exchange:
                await self.ws_exchange.close()
                self.ws_exchange = None

            self._ws_connected = False
            self.logger.info("🔌 WebSocket connection closed")

        except Exception as e:
            self.logger.warning(f"⚠️ Error closing WebSocket: {e}")

    async def _monitor_orders(self) -> None:
        """Monitor order updates via WebSocket."""
        try:
            while self._ws_connected:
                try:
                    # Watch for order updates
                    orders = await self.ws_exchange.watch_orders()

                    for order in orders:
                        await self._handle_order_update(order)

                except Exception as e:
                    self.logger.error(f"❌ WebSocket order monitoring error: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"❌ Order monitoring failed: {e}")
        finally:
            self._ws_connected = False

    async def _oco_monitor_loop(self) -> None:
        """
        OCO Manual monitoring loop - INDEPENDIENTE del WebSocket.
        Inspirado en Hummingbot Clock architecture.
        Se ejecuta cada segundo independientemente del estado del WebSocket.
        """
        self.logger.info("🎯 OCO Manual: Starting independent monitoring loop")

        try:
            # CORRECCIÓN: OCO Manual independiente del WebSocket (usa self._connected)
            while self._connected:  # Mientras el conector esté activo
                try:
                    # HUMMINGBOT CLOCK PATTERN: Use asyncio.Lock to prevent concurrent modifications
                    async with self._oco_lock:
                        # CLOCK TICK: Ejecutar OCO Manual cada segundo (como Hummingbot)
                        await self._check_manual_tpsl_execution()

                    # Esperar 1 segundo antes del próximo tick (como Hummingbot Clock)
                    await asyncio.sleep(1.0)

                except Exception as e:
                    self.logger.error(f"❌ OCO Manual: Error in monitoring loop: {e}")
                    await asyncio.sleep(1.0)  # Continue even on errors

        except Exception as e:
            self.logger.error(f"❌ OCO Manual: Monitoring loop failed: {e}")
        finally:
            self.logger.info("🎯 OCO Manual: Monitoring loop stopped")

    async def _handle_order_update(self, order: Dict[str, Any]) -> None:
        """Handle real-time order updates for OCO management."""
        try:
            order_id = order.get("id")
            symbol = order.get("symbol")
            status = order.get("status")
            order_type = order.get("type", "")

            # Only handle TP/SL orders
            if not any(tp_sl in order_type.upper() for tp_sl in ["TAKE_PROFIT", "STOP"]):
                return

            self.logger.debug(f"📋 Order update: {order_id} {order_type} {status}")

            # If TP/SL order was filled, cancel the opposite order
            if status == "closed":
                await self._handle_tpsl_execution(order_id, symbol, order_type)

        except Exception as e:
            self.logger.warning(f"⚠️ Error handling order update: {e}")

    async def _handle_tpsl_execution(self, executed_order_id: str, symbol: str, order_type: str) -> None:
        """Handle TP/SL execution and cancel opposite order (OCO behavior)."""
        try:
            self.logger.info(f"🎯 TP/SL executed: {order_type} for {symbol}")

            # Find the opposite order to cancel
            symbol_orders = self._active_orders.get(symbol, {})

            for order_id, order_info in symbol_orders.items():
                if order_id != executed_order_id:
                    # This is the opposite order - cancel it
                    try:
                        await self.exchange.cancel_order(order_id, symbol)
                        self.logger.info(f"✅ OCO: Cancelled opposite order {order_id}")
                    except Exception as cancel_error:
                        self.logger.warning(f"⚠️ Failed to cancel opposite order {order_id}: {cancel_error}")

            # Clean up tracking - NOTE: This will be handled by caller to avoid dictionary iteration issues
            # if symbol in self._active_orders:
            #     del self._active_orders[symbol]

        except Exception as e:
            self.logger.error(f"❌ Error handling TP/SL execution: {e}")

    async def _register_tpsl_pair(self, symbol: str, tp_order_id: str, sl_order_id: str) -> None:
        """Register TP/SL order pair for OCO monitoring."""
        async with self._oco_lock:
            if symbol not in self._active_orders:
                self._active_orders[symbol] = {}

            self._active_orders[symbol][tp_order_id] = {"type": "TP", "opposite": sl_order_id}
            self._active_orders[symbol][sl_order_id] = {"type": "SL", "opposite": tp_order_id}

        self.logger.info(f"📝 Registered TP/SL pair for {symbol}: TP={tp_order_id}, SL={sl_order_id}")
        self.logger.info(
            f"📊 Active orders now: {len(self._active_orders)} symbols, {sum(len(orders) for orders in self._active_orders.values())} total orders"
        )

    async def _check_manual_tpsl_execution(self) -> None:
        """Check if any TP/SL orders should be executed manually based on current price."""
        if not self._active_orders:
            self.logger.debug("🔍 OCO Manual: No active orders to check")
            return

        # Rate limiting removido - ahora se ejecuta cada segundo desde loop independiente
        self.logger.debug(f"🔍 OCO Manual: Checking {len(self._active_orders)} symbols for execution")

        try:
            # Collect symbols to clean up after iteration (avoid dictionary changed size error)
            symbols_to_cleanup = []

            # Check each symbol's active orders
            for symbol, orders in list(self._active_orders.items()):
                self.logger.debug(f"🔍 OCO Manual: Checking symbol {symbol} with {len(orders)} orders")
                try:
                    # Get current price - PROTECTED: Prevent CCXT concurrent access
                    ticker = await self._safe_ccxt_call("fetch_ticker", self.normalize_symbol(symbol))
                    current_price = ticker.get("last", 0)

                    if not current_price:
                        self.logger.warning(f"⚠️ OCO Manual: No current price for {symbol}")
                        continue

                    self.logger.debug(f"💰 OCO Manual: Current price for {symbol}: ${current_price:.4f}")

                    # Check each order
                    orders_to_execute = []
                    orders_to_remove = []
                    for order_id, order_info in orders.items():
                        self.logger.debug(
                            f"🔍 OCO Manual: Checking order {order_id[:8]}... type={order_info.get('type')}"
                        )
                        try:
                            # Get order details to check if it should be executed
                            try:
                                # WORKAROUND: Use direct API call instead of CCXT fetch_order
                                # CCXT has issues parsing STOP_MARKET orders, but raw API works fine
                                try:
                                    # PROTECTED: Prevent CCXT concurrent access
                                    order = await self._safe_ccxt_call(
                                        "fetch_order", order_id, self.normalize_symbol(symbol)
                                    )
                                except Exception as ccxt_error:
                                    self.logger.debug(
                                        f"🔍 OCO Manual: CCXT fetch failed for {order_id[:8]}...: {ccxt_error}"
                                    )
                                    # Try direct API call as fallback
                                    try:
                                        # PROTECTED: Prevent CCXT concurrent access
                                        raw_response = await self._safe_ccxt_call(
                                            "fapiPrivateV3GetOrder",
                                            {"symbol": self.normalize_symbol(symbol), "orderId": order_id},
                                        )
                                        # Convert raw response to CCXT format
                                        raw_status = raw_response.get("status", "")
                                        # Map Binance status to CCXT status
                                        ccxt_status = "open" if raw_status == "NEW" else raw_status.lower()

                                        order = {
                                            "id": str(raw_response.get("orderId", "")),
                                            "status": ccxt_status,
                                            "type": raw_response.get("type", ""),
                                            "side": raw_response.get("side", "").lower(),
                                            "info": raw_response,
                                        }
                                        self.logger.debug(f"🔍 OCO Manual: Raw API success for {order_id[:8]}...")
                                    except Exception as raw_error:
                                        self.logger.debug(
                                            f"🔍 OCO Manual: Raw API also failed for {order_id[:8]}...: {raw_error}"
                                        )
                                        continue

                                if not order:
                                    self.logger.warning(
                                        f"⚠️ OCO Manual: Order {order_id[:8]}... not found, removing from tracking"
                                    )
                                    orders_to_remove.append(order_id)
                                    continue
                            except Exception as fetch_error:
                                self.logger.debug(
                                    f"🔍 OCO Manual: Could not fetch order {order_id[:8]}...: {fetch_error}"
                                )
                                self.logger.debug(
                                    f"🔍 OCO Manual: Error type: {type(fetch_error).__name__}, args: {fetch_error.args}"
                                )
                                continue  # Skip this order for now, try again next tick

                            order_status = order.get("status")
                            order_type = order.get("type", "")

                            # Múltiples formas de obtener stopPrice (inspirado en CCXT oficial + raw API)
                            info = order.get("info", {})
                            stop_price = (
                                order.get("stopPrice")
                                or order.get("triggerPrice")
                                or info.get("stopPrice")
                                or info.get("triggerPrice")
                                or info.get("activatePrice")
                            )

                            # Convert string to float if needed (Binance API returns strings)
                            if stop_price and isinstance(stop_price, str):
                                try:
                                    stop_price = float(stop_price)
                                except (ValueError, TypeError):
                                    stop_price = None

                            self.logger.debug(
                                f"📋 OCO Manual: Order {order_id[:8]}... status={order_status}, type={order_type}, stopPrice={stop_price}"
                            )

                            if order_status != "open":
                                self.logger.debug(
                                    f"⏭️ OCO Manual: Skipping order {order_id[:8]}... (status: {order_status})"
                                )
                                continue  # Skip if not open

                            if not stop_price:
                                self.logger.warning(
                                    f"⚠️ OCO Manual: No stopPrice found for order {order_id[:8]}... (order: {order})"
                                )
                                continue

                            stop_price = float(stop_price)
                            self.logger.debug(f"🎯 OCO Manual: Order {order_id[:8]}... stopPrice=${stop_price:.4f}")

                            # Get position side
                            position_side = await self._get_position_side(symbol)
                            self.logger.debug(f"📊 OCO Manual: Position side for {symbol}: {position_side}")

                            # Check if price should trigger execution
                            should_execute = False
                            execution_reason = ""

                            # Detección robusta de tipos de orden (inspirado en crypto-bot y CCXT)
                            is_take_profit = (
                                "take_profit" in order_type.lower()
                                or "TAKE_PROFIT" in order_type
                                or order_info.get("type") == "TP"
                                or order_type in ["TAKE_PROFIT_MARKET", "TAKE_PROFIT_LIMIT"]
                            )

                            is_stop_loss = (
                                "stop" in order_type.lower()
                                or "STOP" in order_type
                                or order_info.get("type") == "SL"
                                or order_type in ["STOP_MARKET", "STOP_LOSS_MARKET", "STOP_LOSS_LIMIT"]
                            )

                            if is_take_profit:
                                # TP logic: depends on position side
                                if position_side == "short" and current_price <= stop_price:
                                    should_execute = True
                                    execution_reason = f"SHORT TP: price ${current_price:.4f} <= ${stop_price:.4f}"
                                elif position_side == "long" and current_price >= stop_price:
                                    should_execute = True
                                    execution_reason = f"LONG TP: price ${current_price:.4f} >= ${stop_price:.4f}"
                                else:
                                    self.logger.debug(
                                        f"🚫 OCO Manual: TP not triggered - {position_side} position, price ${current_price:.4f} vs ${stop_price:.4f}"
                                    )

                            elif is_stop_loss:
                                # SL logic: depends on position side
                                if position_side == "short" and current_price >= stop_price:
                                    should_execute = True
                                    execution_reason = f"SHORT SL: price ${current_price:.4f} >= ${stop_price:.4f}"
                                elif position_side == "long" and current_price <= stop_price:
                                    should_execute = True
                                    execution_reason = f"LONG SL: price ${current_price:.4f} <= ${stop_price:.4f}"
                                else:
                                    self.logger.debug(
                                        f"🚫 OCO Manual: SL not triggered - {position_side} position, price ${current_price:.4f} vs ${stop_price:.4f}"
                                    )

                            if should_execute:
                                self.logger.info(f"🚨 OCO Manual: TRIGGER DETECTED! {execution_reason}")
                                orders_to_execute.append((order_id, order_info, order, stop_price))
                            else:
                                self.logger.debug(f"⏸️ OCO Manual: Order {order_id[:8]}... not triggered")

                        except Exception as e:
                            self.logger.error(f"❌ OCO Manual: Error checking order {order_id[:8]}...: {e}")

                    # Execute triggered orders
                    if orders_to_execute:
                        self.logger.info(f"⚡ OCO Manual: Executing {len(orders_to_execute)} triggered orders")
                        for order_id, order_info, order, stop_price in orders_to_execute:
                            await self._execute_tpsl_manually(
                                symbol, order_id, order_info, order, current_price, stop_price
                            )
                            # Mark symbol for cleanup after execution
                            if symbol not in symbols_to_cleanup:
                                symbols_to_cleanup.append(symbol)
                    else:
                        self.logger.debug(f"⏸️ OCO Manual: No orders to execute for {symbol}")

                except Exception as e:
                    self.logger.error(f"❌ OCO Manual: Error checking symbol {symbol}: {e}")

            # Clean up symbols after iteration is complete
            for symbol in symbols_to_cleanup:
                if symbol in self._active_orders:
                    del self._active_orders[symbol]
                    self.logger.debug(f"🧹 OCO Manual: Cleaned up tracking for {symbol}")

        except Exception as e:
            self.logger.error(f"❌ OCO Manual: Error in manual TP/SL check: {e}")

    async def _get_position_side(self, symbol: str) -> str:
        """Get the side of the current position for a symbol."""
        try:
            normalized_symbol = self.normalize_symbol(symbol)
            self.logger.debug(f"🔍 OCO Manual: Fetching positions for {symbol} (normalized: {normalized_symbol})")

            # PROTECTED: Prevent CCXT concurrent access
            positions = await self._safe_ccxt_call("fetch_positions", [normalized_symbol])
            self.logger.debug(f"📊 OCO Manual: Found {len(positions)} positions")

            for pos in positions:
                pos_symbol = pos.get("symbol")
                contracts = pos.get("contracts", 0)
                side = pos.get("side", "")

                self.logger.debug(f"📊 OCO Manual: Position - symbol={pos_symbol}, contracts={contracts}, side={side}")

                if pos_symbol == normalized_symbol and abs(contracts) > 0:
                    self.logger.debug(
                        f"✅ OCO Manual: Found active position for {symbol}: {side} with {contracts} contracts"
                    )
                    return side.lower()

            self.logger.warning(f"⚠️ OCO Manual: No active position found for {symbol}")
            return "unknown"
        except Exception as e:
            self.logger.error(f"❌ OCO Manual: Error getting position side for {symbol}: {e}")
            return "unknown"

    async def _execute_tpsl_manually(
        self, symbol: str, order_id: str, order_info: dict, order: dict, current_price: float, trigger_price: float
    ) -> None:
        """Execute a TP/SL order manually by converting it to a market order."""
        order_type = order_info.get("type", "unknown")
        max_retries = 3

        for attempt in range(max_retries):
            try:
                self.logger.info(
                    f"🎯 Executing {order_type} manually (attempt {attempt + 1}/{max_retries}): {symbol} @ ${current_price:.2f} (trigger: ${trigger_price:.2f})"
                )

                # Step 1: Cancel the original TP/SL order (with retry)
                for cancel_attempt in range(2):
                    try:
                        # PROTECTED: Prevent CCXT concurrent access
                        await self._safe_ccxt_call("cancel_order", order_id, self.normalize_symbol(symbol))
                        self.logger.debug(f"✅ OCO Manual: Cancelled original {order_type} order {order_id[:8]}...")
                        # Order cancelled successfully
                        break
                    except Exception as cancel_error:
                        if cancel_attempt == 0:
                            self.logger.warning(
                                f"⚠️ OCO Manual: Cancel attempt {cancel_attempt + 1} failed: {cancel_error}"
                            )
                            await asyncio.sleep(0.1)  # Brief pause before retry
                        else:
                            self.logger.error(f"❌ OCO Manual: Failed to cancel order after retries: {cancel_error}")

                # Step 2: Create market order to close position
                side = order.get("side", "")
                amount = order.get("amount", 0)

                if not side or amount <= 0:
                    self.logger.error(f"❌ OCO Manual: Invalid order data - side: {side}, amount: {amount}")
                    return

                # Robust market order creation (inspired by Hummingbot + ChatGPT recommendations)
                market_order_params = {
                    "reduceOnly": True,  # Evita aperturas no deseadas
                    "type": "MARKET",  # Explicit type for Binance
                }

                # PROTECTED: Prevent CCXT concurrent access
                market_order = await self._safe_ccxt_call(
                    "create_order",
                    self.normalize_symbol(symbol),
                    "market",
                    side,
                    amount,
                    None,  # price
                    market_order_params,
                )

                self.logger.info(f"✅ OCO Manual: {order_type} executed manually: {market_order.get('id')}")

                # Step 3: Cancel opposite order (OCO behavior)
                opposite_id = order_info.get("opposite")
                if opposite_id and opposite_id in self._active_orders.get(symbol, {}):
                    try:
                        # PROTECTED: Prevent CCXT concurrent access
                        await self._safe_ccxt_call("cancel_order", opposite_id, self.normalize_symbol(symbol))
                        self.logger.info(f"✅ OCO Manual: Cancelled opposite order {opposite_id[:8]}...")
                    except Exception as e:
                        self.logger.warning(f"⚠️ OCO Manual: Failed to cancel opposite order: {e}")

                # Step 4: Clean up tracking (inspired by crypto-bot cleanup)
                # NOTE: Cleanup is handled by caller to avoid dictionary iteration issues
                # if symbol in self._active_orders:
                #     del self._active_orders[symbol]
                #     self.logger.debug(f"🧹 OCO Manual: Cleaned up tracking for {symbol}")

                # Success - exit retry loop
                return

            except Exception as e:
                self.logger.error(f"❌ OCO Manual: Execution attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5  # Exponential backoff
                    self.logger.info(f"⏳ OCO Manual: Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"❌ OCO Manual: All {max_retries} attempts failed for {order_type}")
                    # Emergency cleanup - remove from tracking even if execution failed
                    # NOTE: Cleanup is handled by caller to avoid dictionary iteration issues
                    # if symbol in self._active_orders:
                    #     del self._active_orders[symbol]

    async def _register_single_order(self, symbol: str, order_id: str, order_type: str, opposite_price: float) -> None:
        """Register single TP or SL order for monitoring (when only one could be created)."""
        async with self._oco_lock:
            if symbol not in self._active_orders:
                self._active_orders[symbol] = {}

            self._active_orders[symbol][order_id] = {
                "type": order_type,
                "opposite_price": opposite_price,
                "opposite": None,  # No opposite order exists yet
            }

        self.logger.info(
            f"📝 Registered single {order_type} order for {symbol}: {order_id} (opposite price: {opposite_price})"
        )
        self.logger.info("🎯 OCO Manual: Will monitor price and create opposite order dynamically if needed")
