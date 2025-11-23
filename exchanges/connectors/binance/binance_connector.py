"""Binance Futures Connector - Exchange-Specific Implementation.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este conector maneja TODAS las particularidades específicas de Binance Futures.
NO mover lógica específica de Binance al adaptador (CCXTAdapter).

Particularidades de Binance Futures:
    - TP/SL: Soporta stopPrice y stopLimitPrice en params
    - API: Moderna y bien documentada
    - Símbolos: "BTC/USD:USD" → "BTC/USDT:USDT"
    - Testnet: demo.binancefuture.com
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
- Testnet: demo.binancefuture.com (simulación con datos reales, sin riesgo)
- Live: fapi.binance.com (dinero real)

El demo de Binance Futures está activo y funcional.
CCXT tiene un bug con la opción "demo", pero se puede usar configurando
manualmente las URLs del demo.

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
import time
from typing import Any, Dict, List, Literal, Optional

import ccxt.async_support as ccxt_async
import ccxt.pro as ccxtpro

from ..connector_base import BaseConnector
from .binance_constants import BASE_CURRENCY, BINANCE_DEFAULT_CONFIG
from .binance_constants import denormalize_symbol as denormalize_binance_symbol
from .binance_constants import normalize_symbol as normalize_binance_symbol

# =========================================================
# 🔧 CUSTOM CCXT CLASS FOR TESTNET WORKAROUND
# =========================================================


class BinanceTestnet(ccxt_async.binance):
    """
    Minimal workaround for Binance Futures Testnet.

    The core issue is that CCXT's default binance class tries to call spot endpoints
    which don't work with futures-only testnet API keys. This class simply redirects
    all URLs to the testnet domain and disables problematic spot calls.
    """

    def describe(self):
        """Override describe() to hard-code all API URLs to the testnet domain."""
        return self.deep_extend(
            super().describe(),
            {
                "urls": {
                    "api": {
                        # Main endpoints - redirect to futures
                        "public": "https://testnet.binancefuture.com/fapi/v1",
                        "private": "https://testnet.binancefuture.com/fapi/v1",
                        # Futures endpoints
                        "fapiPublic": "https://testnet.binancefuture.com/fapi/v1",
                        "fapiPrivate": "https://testnet.binancefuture.com/fapi/v1",
                        "fapiPublicV2": "https://testnet.binancefuture.com/fapi/v2",
                        "fapiPrivateV2": "https://testnet.binancefuture.com/fapi/v2",
                        "fapiPublicV3": "https://testnet.binancefuture.com/fapi/v3",
                        "fapiPrivateV3": "https://testnet.binancefuture.com/fapi/v3",
                        # Spot endpoints - redirect to futures to avoid auth errors
                        "sapi": "https://testnet.binancefuture.com/fapi/v1",
                        "sapiV2": "https://testnet.binancefuture.com/fapi/v2",
                        "sapiV3": "https://testnet.binancefuture.com/fapi/v1",
                        # Delivery endpoints - redirect to futures
                        "dapiPublic": "https://testnet.binancefuture.com/fapi/v1",
                        "dapiPrivate": "https://testnet.binancefuture.com/fapi/v1",
                    }
                }
            },
        )

    async def fetch_currencies(self, params={}):
        """Override to prevent failing calls to spot currency endpoints."""
        return {}

    async def fetch_markets(self, params={}):
        """Override fetch_markets to ONLY fetch futures markets and avoid spot calls."""
        try:
            # Only fetch futures markets, skip spot/margin
            response = await self.fapiPublicGetExchangeInfo(params)
            markets = self.parse_markets(response["symbols"])
            return markets
        except Exception as e:
            # If futures call fails, return empty to avoid cascading errors
            self.logger.error(f"⚠️ BinanceTestnet.fetch_markets failed: {e}")
            return []

    async def fetch_positions(self, symbols=None, params={}):
        """Override fetch_positions to use futures endpoint and fix leverage parsing."""
        await self.load_markets()
        response = await self.fapiPrivateV2GetPositionRisk(params)

        # Parse positions manually to ensure proper data types
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

            # Ensure leverage is never None
            leverage = self.safe_number(position, "leverage", 1.0)
            if leverage is None or leverage == 0:
                leverage = 1.0

            positions.append(
                {
                    "info": position,
                    "symbol": market["symbol"],
                    "contracts": abs(contracts),
                    "contractSize": self.safe_number(market, "contractSize", 1),
                    "side": "long" if contracts > 0 else "short",
                    "notional": self.safe_number(position, "notional"),
                    "leverage": leverage,  # Ensure this is never None
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


class BinanceTestnetPro(ccxtpro.binance):
    """
    Custom Binance Pro class for testnet WebSocket connections.

    This class extends CCXT Pro to support Binance Futures testnet WebSocket streams.
    """

    def __init__(self, config={}):
        """Initialize with currency setup to prevent KeyError issues."""
        # CORRECCIÓN DE CONCURRENCIA: Asegurar config válido antes de super().__init__
        if not isinstance(config, dict):
            config = {}

        # Validar credenciales ANTES de la inicialización
        if not config.get("apiKey") or not config.get("secret"):
            raise ValueError(
                f"BinanceTestnetPro requires valid credentials. Got apiKey={bool(config.get('apiKey'))}, secret={bool(config.get('secret'))}"
            )

        super().__init__(config)

        # CORRECCIÓN DE CONCURRENCIA: Deshabilitar snapshots automáticos que disparan
        # llamadas REST (fetch_positions) desde ccxt.pro al iniciar WS
        if hasattr(self, "options"):
            self.options = self.deep_extend(
                self.options or {},
                {
                    "watchPositions": {
                        "fetchPositionsSnapshot": False,
                        "awaitPositionsSnapshot": False,
                    },
                    # watchOrders usa set_positions_cache() que consulta opciones de watchPositions
                    "watchOrders": {
                        "fetchPositionsSnapshot": False,
                        "awaitPositionsSnapshot": False,
                    },
                },
            )

        # Pre-populate currencies to prevent KeyError in currency_to_precision
        self.currencies = {
            "USDT": {"id": "USDT", "code": "USDT", "name": "Tether USD", "precision": 8, "type": "crypto"},
            "BTC": {"id": "BTC", "code": "BTC", "name": "Bitcoin", "precision": 8, "type": "crypto"},
        }

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

    async def fetch_currencies(self, params={}):
        """Override to prevent failing calls to spot currency endpoints."""
        # Retornar currencies básicas para evitar KeyError en WebSocket
        return {
            "USDT": {"id": "USDT", "code": "USDT", "name": "Tether USD", "precision": 8, "type": "crypto"},
            "BTC": {"id": "BTC", "code": "BTC", "name": "Bitcoin", "precision": 8, "type": "crypto"},
        }

    async def load_markets(self, reload=False, params={}):
        """Override load_markets to ONLY load futures markets."""
        markets = self.markets
        if not markets or reload:
            # Only fetch futures markets, skip spot/margin
            response = await self.fapiPublicGetExchangeInfo(params)
            markets = self.parse_markets(response["symbols"])
            self.markets = self.index_by(markets, "symbol")

            # Load currencies to prevent WebSocket KeyError
            self.currencies = await self.fetch_currencies()

        return self.markets

    async def fetch_markets(self, params={}):
        """Override fetch_markets to ONLY fetch futures markets."""
        try:
            response = await self.fapiPublicGetExchangeInfo(params)
            markets = self.parse_markets(response["symbols"])
            return markets
        except Exception as e:
            self.logger.error(f"⚠️ BinanceTestnetPro.fetch_markets failed: {e}")
            return []

    async def fetch_positions(self, symbols=None, params={}):
        """Override fetch_positions to use futures V2 risk endpoint for testnet."""
        await self.load_markets()
        # Use V2 endpoint which is stable on testnet
        response = await self.fapiPrivateV2GetPositionRisk(params)

        positions = []
        for position in response:
            symbol_id = self.safe_string(position, "symbol")
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
            leverage = self.safe_number(position, "leverage", 1.0)
            if leverage is None or leverage == 0:
                leverage = 1.0
            positions.append(
                {
                    "info": position,
                    "symbol": market["symbol"],
                    "contracts": abs(contracts),
                    "contractSize": self.safe_number(market, "contractSize", 1),
                    "side": "long" if contracts > 0 else "short",
                    "notional": self.safe_number(position, "notional"),
                    "leverage": leverage,
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


class BinanceConnector(BaseConnector):
    # =========================================================
    # 🟢 WEBSOCKET QUERIES (STUBS)
    # =========================================================

    async def watch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance using WebSocket (if supported).
        Returns balance dict in CCXT format.
        """
        if not self.enable_websocket or not self.ws_exchange:
            raise NotImplementedError("WebSocket balance not available or not initialized.")
        # CCXT Pro does not natively support watch_balance for Binance Futures, so this is a placeholder.
        # If/when supported, implement here.
        raise NotImplementedError("watch_balance not implemented for Binance Futures.")

    async def watch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch open positions using WebSocket (if supported).
        Returns list of positions in CCXT format.
        """
        if not self.enable_websocket or not self.ws_exchange:
            raise NotImplementedError("WebSocket positions not available or not initialized.")
        # CCXT Pro supports watchPositions for Binance Futures, but may require custom handling.
        try:
            positions = await self.ws_exchange.watch_positions(symbols, params={"type": "future"})
            self.logger.debug(f"📊 WS positions fetched: {len(positions)} active")
            return positions
        except Exception as e:
            self.logger.error(f"❌ Error fetching positions via WS: {e}")
            raise

    async def watch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch order book using WebSocket (if supported).
        Returns order book dict in CCXT format.
        """
        if not self.enable_websocket or not self.ws_exchange:
            raise NotImplementedError("WebSocket order book not available or not initialized.")
        try:
            binance_symbol = self.normalize_symbol(symbol)
            order_book = await self.ws_exchange.watch_order_book(binance_symbol, limit)
            self.logger.debug(f"📊 WS order book fetched: {symbol}")
            return order_book
        except Exception as e:
            self.logger.error(f"❌ Error fetching order book via WS: {e}")
            raise

    """
    Connector for Binance Futures exchange (USDT Perpetual).

    This connector handles all communication with Binance Futures API,
    including REST and WebSocket connections.

    Testnet vs Live:
    - demo: Binance Futures Testnet (simulated trading)
    - live: Binance Futures Production (real money)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: Literal["demo", "live", "testnet"] = "demo",
        enable_websocket: bool = True,
    ):
        """
        Initialize Binance connector.

        Args:
            api_key: Binance API key (optional, loaded from env if not provided)
            secret: Binance API secret (optional, loaded from env if not provided)
            mode: "demo" for demo (recommended), "live" for production
            enable_websocket: Enable WebSocket + OCO manual monitoring
                            (default: False, auto-enabled in demo since OCO doesn't work automatically)
        """
        self.logger = logging.getLogger("BinanceConnector")

        if mode not in {"demo", "live"}:
            raise ValueError(f"Invalid mode for BinanceConnector: {mode}")

        self._mode = mode
        self._demo = mode == "demo"

        # TEMPORARY: Disable auto-enable WebSocket due to CCXT Pro concurrency issues
        # Auto-enable WebSocket + OCO manual in testnet (OCO doesn't work automatically)
        if self._demo and not enable_websocket:
            self.logger.info(
                "🧪 Testnet detected - Auto-enabling WebSocket + OCO manual (OCO doesn't work automatically in testnet)"
            )
            self.enable_websocket = True
        else:
            self.enable_websocket = enable_websocket
            if self.enable_websocket:
                self.logger.info(
                    "ℹ️ WebSocket habilitado: ccxt.pro puede tener bugs de concurrencia. Se aplicaron mitigaciones (pre-auth, sin snapshots, espejado de markets)."
                )
            else:
                self.logger.info(
                    "🔌 WebSocket está deshabilitado. Se usará sondeo REST para el monitoreo de órdenes OCO."
                )

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
                "Set BINANCE_DEMO_API_KEY and BINANCE_DEMO_SECRET (or BINANCE_API_KEY/BINANCE_SECRET for live) "
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
        # Set default type to future for all connections
        config["options"]["defaultType"] = "future"

        # Initialize locks BEFORE creating the exchange instance
        # This is critical because the monkey-patching code needs to reference these locks
        self._markets_lock = asyncio.Lock()  # Prevent concurrent market loading
        self._oco_lock = asyncio.Lock()  # Prevent concurrent modifications (Hummingbot pattern)
        self._ccxt_lock = asyncio.Lock()  # Protect CCXT internal state

        # Use the custom class for demo mode to apply the URL workaround
        if self._demo:
            self.logger.info("🧪 Testnet mode enabled. Using custom BinanceTestnet class.")
            self.exchange = BinanceTestnet(config)
        else:
            self.exchange = ccxt_async.binance(config)

        # MONKEY-PATCH: Override the ccxt instance's load_markets with a thread-safe version
        # This is the canonical way to fix CCXT's concurrency issues.
        # Since BinanceTestnet doesn't override load_markets, we can use the instance method for both
        original_load_markets = self.exchange.load_markets

        async def load_markets_safe(reload=False, params={}):
            async with self._markets_lock:
                if not reload and self.exchange.markets:
                    return self.exchange.markets

                # Call the original method normally
                await original_load_markets(reload, params)

            return self.exchange.markets

        # Replace the instance method with our thread-safe version
        self.exchange.load_markets = load_markets_safe

        self._connected = False
        self._ready = False

        # Initialize WebSocket (CCXT Pro) if enabled
        self.ws_exchange = None
        self._ws_connected = False
        self._order_monitor_task = None

        # Concurrency locks
        self._ccxt_lock = asyncio.Lock()

        # HUMMINGBOT CLOCK PATTERN: Central clock coordinates all tasks
        self._clock_task = None
        self._clock_running = False
        self._last_tick = 0

        if self.enable_websocket:
            self.logger.info("🔌 WebSocket enabled - will initialize on connect()")

        self.logger.info(f"✅ Binance connector initialized | Mode: {mode.upper()}")

    # =========================================================
    # 🔒 CCXT CONCURRENCY PROTECTION
    # =========================================================

    async def _safe_ccxt_call(self, method_name: str, *args, **kwargs):
        """Safely execute a method with concurrency protection."""
        async with self._ccxt_lock:
            # Try to get the method from the ccxt exchange instance first
            method = getattr(self.exchange, method_name, None)
            # If not found, try to get it from the connector instance itself
            if method is None:
                method = getattr(self, method_name)
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
        if self._demo:
            # Load demo credentials
            api_key = os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
            secret = os.getenv("BINANCE_DEMO_SECRET") or os.getenv("BINANCE_TESTNET_SECRET")
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

            # Eager load markets to prevent race conditions
            await self._safe_ccxt_call("load_markets")
            self.logger.info(f"✅ Markets loaded | Count: {len(self.exchange.markets)}")

            # Try to fetch balance to validate credentials
            try:
                # PROTECTED: Prevent CCXT concurrent access
                balance = await self._safe_ccxt_call("fetch_balance")
                usdt_balance = balance.get("total", {}).get(BASE_CURRENCY, 0)
                self.logger.info(f"✅ Balance fetched | {BASE_CURRENCY}: {usdt_balance}")
            except Exception as balance_error:
                if "Invalid API-key" in str(balance_error):
                    self.logger.error(f"❌ Invalid API credentials: {balance_error}")
                    self.logger.error("🔑 Please check your API keys in .env file")
                    self.logger.error("📝 Required permissions: Futures Trading + Reading")
                    raise  # Re-raise authentication errors as they are critical
                else:
                    self.logger.warning(f"⚠️  Could not fetch balance: {balance_error}")
                    self.logger.warning("⚠️  API keys may need specific permissions enabled")
                    self.logger.warning("⚠️  Required: Enable Reading + Futures Trading permissions")

            self._connected = True
            self._ready = True

            # Start WebSocket monitoring if enabled
            if self.enable_websocket:
                try:
                    # CORRECCIÓN DE CONCURRENCIA: Inicializar WebSocket de forma secuencial
                    self.logger.info("🔌 Starting WebSocket initialization...")

                    # Esperar un poco para asegurar que el REST exchange esté completamente listo
                    await asyncio.sleep(0.1)

                    await self._init_websocket()

                    if self._ws_connected:  # Solo crear tasks si WebSocket está conectado
                        self._ws_task = asyncio.create_task(self._monitor_orders())
                        # Agregar callback para manejar excepciones no capturadas
                        self._ws_task.add_done_callback(self._handle_task_exception)
                        self.logger.info("👁️ Order monitoring started")
                    else:
                        self.logger.warning(
                            "⚠️ WebSocket failed to connect, continuing without disabling WebSocket flag"
                        )
                except Exception as ws_error:
                    self.logger.error(f"❌ WebSocket initialization failed: {ws_error}")
                    self.logger.info("🔄 Continuing in REST mode while keeping WebSocket enabled for retries")

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

            # Close the underlying ccxt exchange instance explicitly
            if self.exchange:
                await self.exchange.close()

            self._connected = False
            self._ready = False
            self.logger.info("🔌 Connection to Binance closed")
        except Exception as e:
            self.logger.warning(f"⚠️ Error closing Binance connection: {e}")

    async def disconnect(self) -> None:
        """Alias for close() for compatibility."""
        await self.close()

    # ⚠️  DEPRECATED: OCO Manual moved to PositionTracker
    # This method is kept for backwards compatibility but should not be used
    # async def _oco_monitor_loop_rest(self): ...

    # ⚠️  DEPRECATED: OCO Manual moved to PositionTracker
    # async def _handle_oco_fill(self, symbol: str, filled_order_id: str): ...
    # async def oco_monitor_tick(self) -> None: ...

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
            # PROTECTED: Prevent CCXT concurrent access
            balance = await self._safe_ccxt_call("fetch_balance", params={"type": "future"})
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
            # PROTECTED: Prevent CCXT concurrent access
            positions = await self._safe_ccxt_call("fetch_positions", symbols)
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
                # PROTECTED: Prevent CCXT concurrent access
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

    async def _ensure_stop_price_safe(
        self, binance_symbol: str, side: str, stop_price: float, order_type: str = "STOP"
    ) -> float:
        """
        Ensure a stop/take-profit price won't "immediately trigger" on Binance by
        comparing against current market price and adjusting by one tick if needed.

        This is a conservative safeguard to avoid the ccxt/binance error "Order would
        immediately trigger" (-2021) without performing any forced closes.
        """
        try:
            # Load markets if needed
            if not self.exchange.markets:
                await self._safe_ccxt_call("load_markets")

            market = self.exchange.markets.get(binance_symbol)
            current_ticker = await self.fetch_ticker(self.denormalize_symbol(binance_symbol))
            last_price = float(current_ticker.get("last") or current_ticker.get("close") or 0)

            # Determine tick/price precision
            tick = None
            if market:
                # 1. Try 'precision' (ccxt unified)
                precision = market.get("precision") or {}
                price_prec = precision.get("price")

                if isinstance(price_prec, (int, float)):
                    if isinstance(price_prec, int):
                        # If int, it's decimal places (e.g. 2 -> 0.01)
                        tick = 10 ** (-price_prec)
                    else:
                        # If float, it's the tick size itself (e.g. 0.01)
                        tick = price_prec

                # 2. If no tick yet, try 'info.filters' (Binance specific)
                if tick is None:
                    info = market.get("info", {})
                    filters = info.get("filters", [])
                    for f in filters:
                        if f.get("filterType") == "PRICE_FILTER":
                            tick_size = f.get("tickSize")
                            if tick_size:
                                tick = float(tick_size)
                            break

                # 3. Fallback to limits (careful with min price vs tick)
                if tick is None:
                    limits = market.get("limits", {})
                    price_limits = limits.get("price", {})
                    # DO NOT use 'min' as tick, it can be large (e.g. 3.61 for LTC)
                    # Only use if it looks like a tick (small)
                    min_price = price_limits.get("min")
                    if min_price and float(min_price) < 0.1:
                        tick = float(min_price)

            # Final fallback tick
            if tick is None or tick == 0:
                tick = max(0.0001, abs(last_price) * 1e-6)

            side_lower = side.lower()
            adjusted = float(stop_price)
            order_type_upper = (order_type or "").upper()

            # Determine if this is a Take Profit or Stop Loss
            is_tp = "TAKE_PROFIT" in order_type_upper
            # is_sl = "STOP" in order_type_upper  <-- Removed unused variable

            # Logic for BUY (Long Entry or Short Close)
            if side_lower == "buy":
                if is_tp:
                    # TP BUY: Trigger when price FALLS to stopPrice (stopPrice < current)
                    # Ensure stopPrice is strictly LESS than last_price
                    if adjusted >= last_price:
                        adjusted = float(last_price) - tick
                        self.logger.warning(
                            f"⚠️ Adjusting TP BUY stopPrice from {stop_price} -> {adjusted} to avoid immediate-trigger (last={last_price})"
                        )
                else:
                    # SL BUY (or default): Trigger when price RISES to stopPrice (stopPrice > current)
                    # Ensure stopPrice is strictly GREATER than last_price
                    if adjusted <= last_price:
                        adjusted = float(last_price) + tick
                        self.logger.warning(
                            f"⚠️ Adjusting SL BUY stopPrice from {stop_price} -> {adjusted} to avoid immediate-trigger (last={last_price})"
                        )

            # Logic for SELL (Short Entry or Long Close)
            else:
                if is_tp:
                    # TP SELL: Trigger when price RISES to stopPrice (stopPrice > current)
                    # Ensure stopPrice is strictly GREATER than last_price
                    if adjusted <= last_price:
                        adjusted = float(last_price) + tick
                        self.logger.warning(
                            f"⚠️ Adjusting TP SELL stopPrice from {stop_price} -> {adjusted} to avoid immediate-trigger (last={last_price})"
                        )
                else:
                    # SL SELL (or default): Trigger when price FALLS to stopPrice (stopPrice < current)
                    # Ensure stopPrice is strictly LESS than last_price
                    if adjusted >= last_price:
                        adjusted = float(last_price) - tick
                        self.logger.warning(
                            f"⚠️ Adjusting SL SELL stopPrice from {stop_price} -> {adjusted} to avoid immediate-trigger (last={last_price})"
                        )

            return adjusted
        except Exception as e:
            # If anything fails, don't block order creation — return original value
            self.logger.debug(f"ℹ️ _ensure_stop_price_safe fallback due to: {e}")
            return float(stop_price)

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
        confirm_with_ws: bool = False,
        ws_timeout_ms: Optional[int] = None,
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

            # If this is a TP/SL style order, ensure stopPrice won't immediately trigger
            try:
                order_type_upper = (order_type or "").upper()
                # Binance-specific order types that use stopPrice
                tp_sl_types = {"TAKE_PROFIT_MARKET", "STOP_MARKET", "TAKE_PROFIT", "STOP"}
                if ("stopPrice" in clean_params) or (order_type_upper in tp_sl_types):
                    sp = clean_params.get("stopPrice")
                    if sp is not None:
                        try:
                            adjusted_sp = await self._ensure_stop_price_safe(
                                binance_symbol, side, float(sp), order_type
                            )
                            clean_params["stopPrice"] = adjusted_sp
                        except Exception:
                            # If safety check fails, continue with original stopPrice
                            pass

            except Exception:
                # Defensive: never block order creation due to safety check
                pass

            # Create order on Binance
            order_create_ts = time.time()
            # PROTECTED: Prevent CCXT concurrent access
            order = await self._safe_ccxt_call(
                "create_order",
                binance_symbol,
                order_type,
                side.lower(),
                amount,
                price,
                clean_params,
            )

            # Normalize response
            # For market orders, calculate price from cost/filled
            order_price = float(order.get("price") or 0)
            if order_price == 0 and order_type.lower() == "market":
                filled = float(order.get("filled") or 0)
                cost = float(order.get("cost") or 0)
                if filled > 0 and cost > 0:
                    order_price = cost / filled

            # Convertir avgPrice a float (puede venir como string de Binance)
            avg_price_raw = order.get("avgPrice")
            avg_price = float(avg_price_raw) if avg_price_raw else 0.0

            normalized = {
                "id": order.get("id"),
                "symbol": symbol,  # Return in bot format
                "side": side.lower(),
                "type": order_type,
                "status": order.get("status"),
                "price": order_price,
                "avgPrice": avg_price,  # ← avgPrice para MARKET orders
                "amount": float(order.get("amount") or 0),
                "filled": float(order.get("filled") or 0),
                "remaining": float(order.get("remaining") or 0),
                "cost": float(order.get("cost") or 0),
                "fee": order.get("fee", {}),
                "timestamp": order.get("timestamp"),
                "trades": order.get("trades", []),
                # Instrumentation fields
                "order_create_ts": int(order_create_ts * 1000),
                "ws_confirm_ts": None,
                "used_ws_confirm": False,
                "used_rest_fallback": False,
            }

            self.logger.info(
                f"✅ Order created | {symbol} {side.upper()} {amount} @ {price or 'market'} | avgPrice: {avg_price}"
            )

            # If requested, wait for WebSocket confirmation (avgPrice/fill)
            if confirm_with_ws and (avg_price == 0.0 or normalized.get("filled", 0) == 0):
                # Determine timeout
                timeout_ms = int(ws_timeout_ms) if ws_timeout_ms is not None else 2000
                deadline = time.time() + (timeout_ms / 1000.0)

                # Try to wait for WS confirmation if WS is connected
                ws_order = None
                try:
                    if getattr(self, "_ws_connected", False) and self.ws_exchange:
                        # Keep calling watch_orders until we find our order or timeout
                        while time.time() < deadline:
                            remaining = max(0.1, deadline - time.time())
                            try:
                                orders = await asyncio.wait_for(
                                    self.ws_exchange.watch_orders(None, None, None, {"type": "future"}),
                                    timeout=remaining,
                                )
                            except asyncio.TimeoutError:
                                continue

                            if not isinstance(orders, list):
                                continue

                            for o in orders:
                                try:
                                    if not isinstance(o, dict):
                                        continue
                                    # Match by exchange id or clientOrderId
                                    if o.get("id") == normalized.get("id") or o.get("clientOrderId") == normalized.get(
                                        "clientOrderId"
                                    ):
                                        ws_order = o
                                        break
                                except Exception:
                                    continue

                            if ws_order:
                                break

                except Exception as e:
                    self.logger.debug(f"⚠️ WS confirmation attempt failed: {e}")

                # If WS didn't provide confirmation, fallback to REST fetch_order once
                if not ws_order:
                    try:
                        fetched = await self._safe_ccxt_call(
                            "fetch_order", normalized.get("id"), self.normalize_symbol(symbol)
                        )
                        # Update avgPrice if available
                        fetched_avg = fetched.get("avgPrice") or fetched.get("average") or fetched.get("price")
                        if fetched_avg:
                            try:
                                normalized["avgPrice"] = float(fetched_avg)
                                normalized["used_rest_fallback"] = True
                                normalized["ws_confirm_ts"] = int(time.time() * 1000)
                            except Exception:
                                pass
                    except Exception:
                        # Best-effort: do not raise to avoid blocking callers
                        self.logger.debug("ℹ️ fetch_order fallback did not return avgPrice")

                else:
                    # Update normalized using ws_order fields
                    try:
                        ws_avg = ws_order.get("avgPrice") or ws_order.get("average") or ws_order.get("price")
                        if ws_avg:
                            normalized["avgPrice"] = float(ws_avg)
                        normalized["used_ws_confirm"] = True
                        normalized["ws_confirm_ts"] = int(time.time() * 1000)
                        # Update filled/cost if present
                        if ws_order.get("filled") is not None:
                            normalized["filled"] = float(ws_order.get("filled") or 0)
                        if ws_order.get("cost") is not None:
                            normalized["cost"] = float(ws_order.get("cost") or 0)
                    except Exception:
                        pass

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
            # PROTECTED: Prevent CCXT concurrent access
            order = await self._safe_ccxt_call("fetch_order", order_id, binance_symbol)
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
            # PROTECTED: Prevent CCXT concurrent access
            orders = await self._safe_ccxt_call("fetch_open_orders", binance_symbol)
            self.logger.debug(f"📊 Open orders fetched: {len(orders)}")
            return orders
        except Exception as e:
            self.logger.error(f"❌ Error fetching open orders: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Cancel an order on Binance.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol
            params: Additional parameters (optional)

        Returns:
            Cancellation result
        """
        try:
            binance_symbol = self.normalize_symbol(symbol)
            # PROTECTED: Prevent CCXT concurrent access
            result = await self._safe_ccxt_call("cancel_order", order_id, binance_symbol)
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
                    # PROTECTED: Prevent CCXT concurrent access
                    result = await self._safe_ccxt_call("cancel_order", order["id"], binance_symbol)
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
            # PROTECTED: Prevent CCXT concurrent access
            ticker = await self._safe_ccxt_call("fetch_ticker", binance_symbol)
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
            # PROTECTED: Prevent CCXT concurrent access
            ohlcv = await self._safe_ccxt_call("fetch_ohlcv", binance_symbol, timeframe, since, limit)
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
            # Si no se especifica symbol, retornar lista vacía en lugar de fallar
            if symbol is None:
                self.logger.debug("📊 No symbol specified for trades, returning empty list")
                return []

            binance_symbol = self.normalize_symbol(symbol)
            trades = await self.exchange.fetch_my_trades(binance_symbol, since=since, limit=limit)
            self.logger.debug(f"📊 Trades fetched: {len(trades)}")
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades: {e}")
            return []  # Retornar lista vacía en lugar de raise para no romper el flujo

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

            # Create CCXT Pro exchange
            config = BINANCE_DEFAULT_CONFIG.copy()
            config["apiKey"] = self._api_key
            config["secret"] = self._secret
            config["options"]["defaultType"] = "future"

            # CRÍTICO: Asegurar que las credenciales están presentes
            if not config["apiKey"] or not config["secret"]:
                raise ValueError("WebSocket requires valid API credentials")

            # Use custom class for demo, standard for live
            if self._demo:
                self.ws_exchange = BinanceTestnetPro(config)
                self.logger.info(f"🧪 Using BinanceTestnetPro for WebSocket demo (API: {config['apiKey'][:8]}...)")
            else:
                self.ws_exchange = ccxtpro.binance(config)

            # Evitar condiciones de carrera: reutilizar markets y currencies del REST
            try:
                if getattr(self.exchange, "markets", None):
                    self.ws_exchange.markets = self.exchange.markets
                    # Mirror derived CCXT indexes to avoid ccxt.pro trying to compute them concurrently
                    if getattr(self.exchange, "markets_by_id", None):
                        self.ws_exchange.markets_by_id = self.exchange.markets_by_id
                    if getattr(self.exchange, "symbols", None):
                        self.ws_exchange.symbols = self.exchange.symbols
                if getattr(self.exchange, "currencies", None):
                    self.ws_exchange.currencies = self.exchange.currencies
            except Exception as e:
                self.logger.warning(f"⚠️ Could not mirror markets/currencies to WS exchange: {e}")

            # Pre-authenticate WS to provision listenKey and avoid internal snapshot/auth races
            try:
                await self.ws_exchange.authenticate({"type": "future"})
                self.logger.info("🔑 WebSocket authenticated and listenKey provisioned (future)")
            except Exception as auth_e:
                self.logger.warning(f"⚠️ WS pre-authenticate failed (will retry on first watch): {auth_e}")

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

    async def ensure_websocket(self) -> None:
        """Public method to (re)initialize WebSocket if enabled but not connected.

        Fail fast: raises on initialization failure so upper layers can decide recovery.
        """
        if not getattr(self, "enable_websocket", False):
            return
        # If already connected, nothing to do
        if getattr(self, "_ws_connected", False) and self.ws_exchange is not None:
            return
        # Try to init WS
        await self._init_websocket()

    async def _monitor_orders(self) -> None:
        """Monitor order updates via WebSocket."""
        try:
            while self._ws_connected:
                try:
                    # Watch for order updates (explicitly use futures stream)
                    orders = await self.ws_exchange.watch_orders(None, None, None, {"type": "future"})

                    # Debug: Log what we received (use info for visibility)
                    self.logger.info(
                        f"🔍 watch_orders() returned: type={type(orders)}, length={len(orders) if isinstance(orders, list) else 'N/A'}"
                    )

                    # Validar que orders es una lista
                    if not isinstance(orders, list):
                        self.logger.warning(f"⚠️ watch_orders() returned non-list: {type(orders)}, data={orders}")
                        continue

                    for order in orders:
                        # Validar que order es un diccionario
                        if not isinstance(order, dict):
                            self.logger.warning(f"⚠️ Order is not a dict: {type(order)}, data={order}")
                            continue

                        # ⚠️  DEPRECATED: Order update handling moved to PositionTracker
                        # The connector no longer processes order updates for OCO logic
                        # This is now handled by PositionTracker.monitor_oco_execution()
                        self.logger.debug(f"📋 Order update received (handled by PositionTracker): {order.get('id')}")

                except Exception as e:
                    self.logger.error(f"❌ WebSocket order monitoring error: {e}")
                    # Log the full traceback for debugging
                    import traceback

                    self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"❌ Order monitoring failed: {e}")
        finally:
            self._ws_connected = False

    # ⚠️  DEPRECATED: All OCO Manual logic moved to PositionTracker
    # The following methods are no longer used:
    # - _oco_monitor_loop()
    # - _handle_order_update()
    # - _handle_tpsl_execution()
    # - _handle_task_exception()
    # - _register_tpsl_pair()
    # - _check_manual_tpsl_execution()
    # - _get_position_side()
    # - _execute_tpsl_manually()
    # - _register_single_order()
    #
    # See: core/portfolio/position_tracker.py for the new implementation

    def _handle_task_exception(self, task: "asyncio.Task") -> None:
        """
        Callback for asyncio.Task.done() to surface exceptions instead of
        letting them be silently ignored. Added to prevent WebSocket init
        from crashing when the callback is missing.

        Args:
            task: The completed asyncio.Task
        """
        try:
            # task.exception() will re-raise the exception if one occurred
            exc = None
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                # Task was cancelled intentionally
                return

            if exc:
                self.logger.error(f"❌ Background task raised: {exc}", exc_info=True)
        except Exception as e:
            # Defensive: ensure callback never raises
            self.logger.error(f"❌ _handle_task_exception failed: {e}", exc_info=True)
