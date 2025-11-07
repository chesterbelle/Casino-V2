"""
Kraken Futures Connector - Exchange-Specific Implementation.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este conector maneja TODAS las particularidades específicas de Kraken Futures.
NO mover lógica específica de Kraken al adaptador (CCXTAdapter).

Particularidades de Kraken Futures:
    - TP/SL requieren órdenes separadas (conditional orders)
    - Tipos de órdenes: "take_profit", "stop", "limit", "market"
    - Parámetros específicos: "triggerPrice", "reduceOnly"
    - Símbolos: "BTC/USD" → "PF_XBTUSD"
    - Testnet: demo-futures.kraken.com
    - Live: futures.kraken.com

Implementación de TP/SL (Kraken-specific):
    - create_order_with_tpsl() crea 3 órdenes:
      1. Orden principal (market/limit)
      2. Take Profit (conditional order con triggerPrice)
      3. Stop Loss (stop order con triggerPrice)

📚 Referencias:
    - Interface: exchanges/connectors/connector_base.py
    - Adaptador agnóstico: exchanges/adapters/ccxt_adapter.py
    - Análisis: docs/ARQUITECTURA_MODULARIDAD_ANALISIS.md

================================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

import ccxt.async_support as ccxt_async

from ..connector_base import BaseConnector
from .kraken_constants import BASE_CURRENCY, KRAKEN_DEFAULT_CONFIG
from .kraken_constants import denormalize_symbol as denormalize_kraken_symbol
from .kraken_constants import get_urls
from .kraken_constants import normalize_symbol as normalize_kraken_symbol
from .kraken_websocket import KrakenWebSocket
from .oco_monitor import OCOOrderMonitor


class KrakenConnector(BaseConnector):
    """
    Connector for Kraken Futures exchange.

    This connector handles all communication with Kraken Futures API,
    including REST and WebSocket connections.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        mode: Literal["testing", "live"] = "testing",
        enable_websocket: bool = False,
        testnet: Optional[bool] = None,
    ):
        """
        Hybrid Kraken connector.

        Args:
            api_key: Kraken API key (optional, loaded from env si no se provee)
            secret: Kraken API secret (optional, loaded from env si no se provee)
            mode: "testing" (Kraken Demo) o "live" (Kraken producción)
            enable_websocket: Habilitar WebSocket (experimental)
            testnet: Parámetro legacy; si se provee, sobrescribe `mode`
        """
        self.logger = logging.getLogger("KrakenConnector")
        if testnet is not None:
            mode = "testing" if testnet else "live"

        if mode not in {"testing", "live"}:
            raise ValueError(f"Modo inválido para KrakenConnector: {mode}")

        self._mode = mode
        self._testnet = mode == "testing"
        self.enable_websocket = enable_websocket

        if mode == "live":
            self.logger.warning("=" * 60)
            self.logger.warning("🚨 KRAKEN LIVE MODE ACTIVADO — DINERO REAL 🚨")
            self.logger.warning("=" * 60)

        if api_key is None or secret is None:
            self.logger.info("📝 Cargando credenciales de Kraken desde environment...")
            loaded_creds = self._load_credentials()
            api_key = api_key or loaded_creds.get("apiKey")
            secret = secret or loaded_creds.get("secret")

        if not api_key or not secret:
            raise ValueError(
                "Kraken API credentials not provided and not found in environment. "
                "Set KRAKEN_API_KEY y KRAKEN_API_SECRET en tu entorno."
            )

        if mode == "live":
            self._validate_live_credentials(api_key)

        self.api_key = api_key
        self.secret = secret

        self.exchange: Optional[ccxt_async.Exchange] = None
        self._connected = False
        self._markets: Dict[str, Any] = {}
        self._balance_updated = False
        self._last_balance_update: float = 0.0

        # WebSocket (opcional)
        self._ws: Optional[KrakenWebSocket] = None
        self._ws_connected = False
        if enable_websocket:
            self._ws = KrakenWebSocket(testnet=self._testnet)
            self.logger.info("✅ WebSocket habilitado")

        # OCO Monitor (para órdenes TP/SL)
        # Kraken Futures NO soporta OCO automático, por lo que debemos
        # monitorear y cancelar órdenes manualmente
        self._oco_monitor: Optional[OCOOrderMonitor] = None

        env = "DEMO" if self._testnet else "MAINNET"
        self.logger.info("🔧 KrakenConnector inicializado | modo=%s", env)

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================

    async def connect(self) -> None:
        """
        Connect to Kraken Futures exchange.

        This method:
            1. Initializes CCXT exchange instance
            2. Configures API URLs (testnet/mainnet)
            3. Loads markets
            4. Validates connection

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If API keys are invalid
        """
        try:
            self.logger.info("🔌 Conectando a Kraken Futures (%s)...", self._mode)

            use_testnet = self._testnet

            # Get URLs based on environment
            urls = get_urls(use_testnet)

            # Create CCXT exchange instance
            exchange_config = {
                "apiKey": self.api_key,
                "secret": self.secret,
                **KRAKEN_DEFAULT_CONFIG,
                "urls": urls,
            }

            self.exchange = ccxt_async.krakenfutures(exchange_config)

            # Load markets
            self._markets = await self.exchange.load_markets()

            # Validate connection by fetching balance
            await self.exchange.fetch_balance()

            self._connected = True

            env_name = "DEMO" if use_testnet else "MAINNET"
            market_count = len(self._markets)
            self.logger.info(f"✅ Conectado a Kraken Futures {env_name} | {market_count} mercados cargados")

            # Conectar WebSocket si está habilitado
            if self._ws:
                try:
                    self.logger.info("🔌 Conectando WebSocket...")
                    self._ws_connected = await self._ws.connect()
                    if self._ws_connected:
                        self.logger.info("✅ WebSocket conectado")
                    else:
                        self.logger.warning("⚠️ WebSocket falló, usando solo REST")
                except Exception as e:
                    self.logger.warning(f"⚠️ WebSocket falló, usando solo REST: {e}")
                    self._ws_connected = False

            # Iniciar OCO Monitor
            # Kraken Futures NO soporta OCO automático, por lo que necesitamos
            # monitorear las órdenes TP/SL manualmente
            if self._oco_monitor is None:
                self._oco_monitor = OCOOrderMonitor(self, check_interval=2.0)
                await self._oco_monitor.start()
                self.logger.info("✅ OCO Monitor started")

        except ccxt_async.AuthenticationError as e:
            self.logger.error(f"❌ Error de autenticación: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error conectando a Kraken: {e}")
            raise ConnectionError(f"Failed to connect to Kraken: {e}")

    async def close(self) -> None:
        """
        Close connection to Kraken exchange.

        Closes the CCXT exchange instance, WebSocket, and OCO Monitor.
        """
        # Detener OCO Monitor primero
        if self._oco_monitor:
            try:
                await self._oco_monitor.stop()
                self.logger.info("⏹️ OCO Monitor stopped")
            except Exception as e:
                self.logger.error(f"❌ Error stopping OCO Monitor: {e}")

        # Desconectar WebSocket
        if self._ws and self._ws_connected:
            try:
                await self._ws.disconnect()
                self._ws_connected = False
            except Exception as e:
                self.logger.error(f"❌ Error cerrando WebSocket: {e}")

        # Desconectar REST
        if self.exchange:
            try:
                await self.exchange.close()
                self._connected = False
                self.logger.info("🔌 Conexión a Kraken cerrada")
            except Exception as e:
                self.logger.warning(f"⚠️ Error cerrando conexión: {e}")

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV (candlestick) data from Kraken.

        Args:
            symbol: Standard symbol format (e.g., "BTC/USD")
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h")
            limit: Number of candles to fetch

        Returns:
            List of normalized candle dictionaries

        Raises:
            ValueError: If symbol or timeframe is invalid
            ExchangeError: If Kraken returns an error
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken. Call connect() first.")

        try:
            # Normalize symbol to Kraken format
            kraken_symbol = self.normalize_symbol(symbol)

            # Fetch OHLCV from Kraken with timeout
            import asyncio

            try:
                ohlcv = await asyncio.wait_for(
                    self.exchange.fetch_ohlcv(kraken_symbol, timeframe, limit=limit), timeout=30.0  # 30 second timeout
                )
            except asyncio.TimeoutError:
                self.logger.error(f"❌ Timeout fetching OHLCV for {kraken_symbol}")
                raise RuntimeError(f"Timeout fetching OHLCV for {symbol}")

            # Normalize to standard format
            normalized = []
            for candle in ohlcv:
                normalized.append(
                    {
                        "timestamp": candle[0],
                        "timestamp_ms": candle[0],
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": float(candle[5]),
                        "symbol": symbol,  # Standard format
                        "timeframe": timeframe,
                    }
                )

            return normalized

        except ValueError:
            # Symbol normalization error
            raise
        except Exception as e:
            self.logger.error(f"❌ Error fetching OHLCV: {e}")
            raise

    # =========================================================
    # 💰 ACCOUNT DATA
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance from Kraken.

        Returns:
            Normalized balance dictionary with 'total', 'free', 'used' keys

        Raises:
            AuthenticationError: If API keys are invalid
            ExchangeError: If Kraken returns an error
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken. Call connect() first.")

        try:
            balance = await self.exchange.fetch_balance()

            total = balance.get("total", {}) or {}
            free = balance.get("free", {}) or {}
            used = balance.get("used", {}) or {}

            normalized: Dict[str, Any] = {
                "total": total,
                "free": free,
                "used": used,
                "timestamp": balance.get("timestamp"),
                "currency": BASE_CURRENCY,
            }

            for currency_code in set(list(total.keys()) + list(free.keys()) + list(used.keys())):
                normalized[currency_code] = {
                    "total": float(total.get(currency_code, 0) or 0.0),
                    "free": float(free.get(currency_code, 0) or 0.0),
                    "used": float(used.get(currency_code, 0) or 0.0),
                }

            primary_currency = BASE_CURRENCY
            if primary_currency in normalized and normalized[primary_currency]["total"] <= 0:
                if normalized[primary_currency]["free"] > 0:
                    normalized[primary_currency]["total"] = normalized[primary_currency]["free"]

            # Mark balance as updated
            import time

            self._balance_updated = True
            self._last_balance_update = time.time()

            return normalized

        except Exception as e:
            self.logger.error(f"❌ Error fetching balance: {e}")
            raise

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch open positions from Kraken Futures.

        Returns:
            List of normalized position dictionaries

        Raises:
            ExchangeError: If Kraken returns an error
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken. Call connect() first.")

        try:
            # Fetch positions from Kraken
            positions = await self.exchange.fetch_positions()

            # Normalize to standard format
            normalized = []
            for pos in positions:
                normalized.append(
                    {
                        "symbol": self.denormalize_symbol(pos.get("symbol", "")),
                        "side": pos.get("side", "").upper(),  # 'LONG' or 'SHORT'
                        "size": float(pos.get("contracts") or 0),
                        "entry_price": float(pos.get("entryPrice") or 0),
                        "mark_price": float(pos.get("markPrice") or 0),
                        "unrealized_pnl": float(pos.get("unrealizedPnl") or 0),
                        "initial_margin": float(pos.get("initialMargin") or 0),
                        "leverage": float(pos.get("leverage") or 1),
                        "timestamp": pos.get("timestamp") or 0,
                    }
                )

            return normalized

        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
            raise

    # =========================================================
    # 📊 TRADE HISTORY
    # =========================================================

    async def fetch_my_trades(
        self,
        symbol: Optional[str] = None,
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch user's trade history (fills confirmados).

        Args:
            symbol: Filter by symbol (optional, standard format e.g., "BTC/USD")
            since: Timestamp in ms (optional, fetch trades since this time)
            limit: Max number of trades to fetch (default: 100)

        Returns:
            List of normalized trade dictionaries with:
                - id: Trade ID
                - order_id: Order ID that generated this trade
                - symbol: Standard symbol format
                - side: "buy" or "sell"
                - price: Execution price (REAL)
                - amount: Trade amount
                - cost: Total cost (price * amount)
                - fee: Fee information
                - timestamp: Execution timestamp
                - datetime: ISO datetime string

        Raises:
            RuntimeError: If not connected
            ExchangeError: If Kraken returns an error
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken. Call connect() first.")

        try:
            # Normalize symbol if provided
            kraken_symbol = None
            if symbol:
                kraken_symbol = self.normalize_symbol(symbol)

            # Fetch trades from Kraken
            trades = await self.exchange.fetch_my_trades(symbol=kraken_symbol, since=since, limit=limit)

            # Normalize to standard format
            normalized = []
            for trade in trades:
                normalized.append(
                    {
                        "id": trade.get("id", ""),
                        "order_id": trade.get("order"),
                        "symbol": self.denormalize_symbol(trade.get("symbol", "")),
                        "side": trade.get("side", ""),
                        "price": float(trade.get("price") or 0),
                        "amount": float(trade.get("amount") or 0),
                        "cost": float(trade.get("cost") or 0),
                        "fee": (
                            {
                                "cost": float(trade.get("fee", {}).get("cost") or 0),
                                "currency": trade.get("fee", {}).get("currency", "USD"),
                            }
                            if isinstance(trade.get("fee"), dict)
                            else {"cost": 0.0, "currency": "USD"}
                        ),
                        "timestamp": trade.get("timestamp", 0),
                        "datetime": trade.get("datetime", ""),
                        "info": trade.get("info", {}),  # Raw data del exchange
                    }
                )

            self.logger.debug(
                f"📊 Fetched {len(normalized)} trades"
                f"{f' for {symbol}' if symbol else ''}"
                f"{f' since {since}' if since else ''}"
            )

            return normalized

        except Exception as e:
            self.logger.error(f"❌ Error fetching my trades: {e}")
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
        """
        Create an order on Kraken Futures.

        Args:
            symbol: Standard symbol format (e.g., "BTC/USD")
            side: Order side - 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price (required for limit orders)
            order_type: Order type - 'market' or 'limit'
            params: Additional Kraken-specific parameters

        Returns:
            Normalized order result

        Raises:
            InsufficientFunds: If account balance is insufficient
            InvalidOrder: If order parameters are invalid
            ExchangeError: If Kraken returns an error
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken. Call connect() first.")

        try:
            # Normalize symbol to Kraken format
            kraken_symbol = self.normalize_symbol(symbol)

            # Round amount to avoid decimal.ConversionSyntax error
            # Kraken Futures requires specific precision
            amount = round(float(amount), 8)  # 8 decimals should be enough

            # Log order details for debugging
            self.logger.info(
                f"📋 Creating order: symbol={kraken_symbol}, side={side}, "
                f"amount={amount}, price={price}, type={order_type}, params={params}"
            )

            # Note: Kraken Futures handles leverage at account level
            # The 'leverage' param is informational and used for position sizing calculation
            # but the actual leverage is configured in the account settings

            # Clean params - remove leverage as it causes decimal.ConversionSyntax error
            clean_params = (params or {}).copy()
            leverage_value = None
            if "leverage" in clean_params:
                leverage_value = clean_params.pop("leverage")
                self.logger.info(f"🔧 Removed leverage={leverage_value} from params")

            # IMPORTANTE: Configurar margin mode ANTES de crear la orden
            # Kraken Futures requiere llamar a set_margin_mode() explícitamente
            try:
                # Usar isolated margin por defecto (no cross)
                await self.exchange.set_margin_mode("isolated", symbol=kraken_symbol)
                self.logger.info(f"🔧 Set margin mode to ISOLATED for {kraken_symbol}")

                # Si se especificó leverage, configurarlo también
                if leverage_value:
                    await self.exchange.set_leverage(int(leverage_value), symbol=kraken_symbol)
                    self.logger.info(f"🔧 Set leverage to {leverage_value}x for {kraken_symbol}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not set margin mode/leverage: {e}")

            self.logger.info(f"📋 Clean params being sent: {clean_params}")

            # Create order on Kraken
            order = await self.exchange.create_order(
                symbol=kraken_symbol,
                type=order_type,
                side=side.lower(),
                amount=amount,
                price=price,
                params=clean_params,
            )

            # Normalize response
            normalized = {
                "id": order.get("id"),
                "symbol": symbol,  # Standard format
                "side": side.lower(),
                "type": order_type,
                "status": order.get("status"),
                "price": float(order.get("price", 0)) if order.get("price") else None,
                "amount": float(order.get("amount", 0)),
                "filled": float(order.get("filled", 0)),
                "remaining": float(order.get("remaining", 0)),
                "cost": float(order.get("cost", 0)),
                "fee": order.get("fee", {}),
                "timestamp": order.get("timestamp"),
                "trades": order.get("trades", []),
            }

            self.logger.info(f"✅ Orden creada | {symbol} {side.upper()} {amount} @ {price or 'market'}")

            return normalized

        except ccxt_async.InsufficientFunds as e:
            self.logger.error(f"❌ Fondos insuficientes: {e}")
            raise
        except ccxt_async.InvalidOrder as e:
            self.logger.error(f"❌ Orden inválida: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error creando orden: {e}")
            raise

    # =========================================================
    # 🔧 UTILITY METHODS
    # =========================================================

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to Kraken format.

        Args:
            symbol: Standard format (e.g., "BTC/USD")

        Returns:
            Kraken format (e.g., "PF_XBTUSD")
        """
        if ":" in symbol:
            symbol = symbol.split(":")[0]
        if symbol.endswith("/USD") and symbol.count("/") >= 1:
            symbol = symbol.upper()
        return normalize_kraken_symbol(symbol)

    def denormalize_symbol(self, kraken_symbol: str) -> str:
        """
        Convert Kraken symbol back to standard format.

        Args:
            kraken_symbol: Kraken format (e.g., "PF_XBTUSD" or "LTC/USD:USD")

        Returns:
            Standard format (e.g., "BTC/USD")
        """
        # CCXT a veces devuelve símbolos con :USD, removerlo
        if ":" in kraken_symbol:
            kraken_symbol = kraken_symbol.split(":")[0]

        # Si ya está en formato estándar, retornarlo
        if "/" in kraken_symbol and not kraken_symbol.startswith("PF_"):
            return kraken_symbol

        return denormalize_kraken_symbol(kraken_symbol)

    @property
    def exchange_name(self) -> str:
        """Get the name of the exchange."""
        return "kraken"

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kraken."""
        return self._connected

    # =========================================================
    # 🔐 PRIVATE METHODS
    # =========================================================

    def _load_credentials(self) -> Dict[str, str]:
        """
        Load Kraken credentials from environment.

        Returns:
            Dictionary with 'apiKey' and 'secret' keys

        Note:
            This uses the existing kraken_env_loader utility.
        """
        try:
            from utils.exchanges.kraken_env_loader import get_kraken_credentials

            creds = get_kraken_credentials()
            if creds:
                return creds
            return {}
        except ImportError:
            self.logger.warning("⚠️ No se pudo importar kraken_env_loader, credenciales no cargadas")
            return {}

    def _validate_live_credentials(self, api_key: str) -> None:
        """Basic validation for live credentials."""
        if "demo" in api_key.lower():
            raise ValueError("🚨 API key de Kraken Demo detectada. No puede usarse en modo live.")
        self.logger.info("✅ Credenciales validadas para modo live")

    # =========================================================
    # 📊 ADDITIONAL MARKET DATA METHODS
    # =========================================================

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")

        Returns:
            Normalized ticker data
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            normalized_symbol = self.normalize_symbol(symbol)
            ticker = await self.exchange.fetch_ticker(normalized_symbol)
            return ticker
        except Exception as e:
            self.logger.error(f"❌ Error fetching ticker for {symbol}: {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch order book for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            limit: Number of orders to fetch (optional)

        Returns:
            Normalized order book data
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            normalized_symbol = self.normalize_symbol(symbol)
            orderbook = await self.exchange.fetch_order_book(normalized_symbol, limit=limit)
            return orderbook
        except Exception as e:
            self.logger.error(f"❌ Error fetching order book for {symbol}: {e}")
            raise

    async def fetch_trades(
        self, symbol: str, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent public trades for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            since: Timestamp in ms to fetch trades from (optional)
            limit: Number of trades to fetch (optional)

        Returns:
            List of normalized trade data
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            normalized_symbol = self.normalize_symbol(symbol)
            trades = await self.exchange.fetch_trades(normalized_symbol, since=since, limit=limit)
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades for {symbol}: {e}")
            raise

    async def fetch_open_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch open orders.

        Args:
            symbol: Trading pair symbol (optional, fetches all if not provided)
            since: Timestamp in ms to fetch orders from (optional)
            limit: Number of orders to fetch (optional)

        Returns:
            List of normalized order data
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            normalized_symbol = self.normalize_symbol(symbol) if symbol else None
            orders = await self.exchange.fetch_open_orders(symbol=normalized_symbol, since=since, limit=limit)
            return orders
        except Exception as e:
            self.logger.error(f"❌ Error fetching open orders: {e}")
            raise

    async def load_markets(self, reload: bool = False) -> Dict[str, Any]:
        """
        Load markets from exchange.

        Args:
            reload: Force reload markets (optional)

        Returns:
            Dictionary of markets
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            if reload or not self._markets:
                self._markets = await self.exchange.load_markets(reload=reload)
            return self._markets
        except Exception as e:
            self.logger.error(f"❌ Error loading markets: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Disconnect from exchange.

        Calls close() for compatibility.
        """
        await self.close()

    # =========================================================
    # 🧾 PROPERTIES
    # =========================================================

    @property
    def timeframes(self) -> Dict[str, str]:
        """
        Available timeframes for OHLCV data.

        Returns:
            Dictionary mapping timeframe keys to their values
        """
        if self.exchange and hasattr(self.exchange, "timeframes"):
            return self.exchange.timeframes
        # Default Kraken Futures timeframes
        return {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "12h": "12h",
            "1d": "1d",
            "1w": "1w",
        }

    # =========================================================
    # 🧾 PROPERTIES (CONTINUED)
    # =========================================================

    @property
    def mode(self) -> Literal["testing", "live"]:
        """Return connector mode."""
        return "testing" if self._testnet else "live"

    @property
    def testnet(self) -> bool:
        """Legacy compatibility flag (True si usa entorno demo)."""
        return self._testnet

    # =========================================================
    # 📊 STATUS & HEALTH (Hummingbot-inspired)
    # =========================================================

    @property
    def ready(self) -> bool:
        """
        Indica si el conector está listo para operar.

        Un conector de Kraken está "ready" cuando:
        - Está conectado al exchange
        - Ha cargado los mercados
        - Tiene balance actualizado (opcional)

        Returns:
            True si el conector está listo, False en caso contrario
        """
        if not self._connected:
            return False

        if not self._markets:
            return False

        # Balance update is optional for ready status
        # (puede operar sin balance actualizado)

        return True

    async def create_order_with_tpsl(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create order with TP/SL for Kraken Futures with manual OCO implementation.

        Kraken Futures API does NOT support automatic OCO (One Cancels the Other).
        This method creates:
        1. Main order (market/limit)
        2. Take Profit order (separate, conditional)
        3. Stop Loss order (separate, conditional)

        The OCO logic must be implemented externally by monitoring these orders.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            side: Order side - 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price (for limit orders)
            order_type: Order type - 'market' or 'limit'
            tp_price: Take profit trigger price (optional)
            sl_price: Stop loss trigger price (optional)
            params: Additional parameters

        Returns:
            Dict with main order result and TP/SL order IDs:
            {
                'id': main_order_id,
                'symbol': symbol,
                'side': side,
                'amount': amount,
                ...
                'tp_order_id': tp_order_id,  # if TP created
                'sl_order_id': sl_order_id,  # if SL created
            }

        Raises:
            ExchangeError: If order creation fails
        """
        # 1. Create main order
        main_order = await self.create_order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            params=params,
        )

        self.logger.info(
            f"✅ Main order created | " f"{symbol} {side.upper()} {amount:.4f} @ {main_order.get('price', 'market')}"
        )

        # If no TP/SL, return main order
        if not tp_price and not sl_price:
            return main_order

        # 2. Determine close side (opposite of entry)
        close_side = "sell" if side == "buy" else "buy"

        # 3. Create TP/SL orders (Kraken-specific types)
        tp_order_id = None
        sl_order_id = None

        try:
            # Create Take Profit order (if provided)
            # CCXT no reconoce tipos específicos de Kraken (takeProfitLimit)
            # Solución: usar type="limit" estándar + triggerPrice en params
            if tp_price:
                tp_order = await self.exchange.create_order(
                    symbol=symbol,
                    type="limit",  # Tipo estándar CCXT
                    side=close_side,
                    amount=amount,
                    price=tp_price,  # Limit price
                    params={
                        "triggerPrice": tp_price,  # Trigger para activar la orden
                        "reduceOnly": True,  # Solo cerrar posición
                    },
                )
                # CCXT ya normaliza la respuesta
                tp_order_id = tp_order.get("id")
                self.logger.info(
                    f"✅ Take Profit order created | "
                    f"{symbol} {close_side.upper()} @ ${tp_price:.2f} | "
                    f"ID: {tp_order_id}"
                )

            # Create Stop Loss order (if provided)
            # Mismo enfoque: type="limit" + triggerPrice
            if sl_price:
                sl_order = await self.exchange.create_order(
                    symbol=symbol,
                    type="limit",  # Tipo estándar CCXT
                    side=close_side,
                    amount=amount,
                    price=sl_price,  # Limit price
                    params={
                        "triggerPrice": sl_price,  # Trigger para activar la orden
                        "reduceOnly": True,  # Solo cerrar posición
                    },
                )
                # CCXT ya normaliza la respuesta
                sl_order_id = sl_order.get("id")
                self.logger.info(
                    f"✅ Stop Loss order created | "
                    f"{symbol} {close_side.upper()} @ ${sl_price:.2f} | "
                    f"ID: {sl_order_id}"
                )

        except Exception as e:
            self.logger.error(f"❌ Error creating TP/SL orders: {e}")
            # Don't fail the main order if TP/SL creation fails
            # The main order was already executed successfully

        # 4. Add TP/SL order IDs to main order result
        main_order["tp_order_id"] = tp_order_id
        main_order["sl_order_id"] = sl_order_id

        # 5. Register OCO pair for monitoring
        if self._oco_monitor and (tp_order_id or sl_order_id):
            try:
                pair_id = self._oco_monitor.register_oco_pair(
                    symbol=symbol,
                    tp_order_id=tp_order_id,
                    sl_order_id=sl_order_id,
                )
                self.logger.info(f"📋 OCO pair registered: {pair_id}")
            except Exception as e:
                self.logger.error(f"❌ Error registering OCO pair: {e}")

        self.logger.info(
            f"✅ Order with TP/SL created | "
            f"Main: {main_order.get('id')} | "
            f"TP: {tp_order_id or 'None'} | "
            f"SL: {sl_order_id or 'None'}"
        )

        return main_order

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Estado de componentes del conector.

        Returns:
            Diccionario con estado de cada componente
        """
        return {
            "connected": self._connected,
            "markets_loaded": bool(self._markets),
            "balance_updated": self._balance_updated,
            "websocket_active": self._ws_connected if self._ws else False,
            "ready": self.ready,
        }

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """
        Estado para persistencia.

        Returns:
            Diccionario con estado persistente del conector
        """
        return {
            "mode": self._mode,
            "connected": self._connected,
            "markets_count": len(self._markets),
            "balance_updated": self._balance_updated,
            "last_balance_update": self._last_balance_update,
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restaura estado guardado.

        Args:
            saved_states: Estado guardado previamente
        """
        if "balance_updated" in saved_states:
            self._balance_updated = saved_states["balance_updated"]

        if "last_balance_update" in saved_states:
            self._last_balance_update = saved_states["last_balance_update"]

        self.logger.info("📂 Estado restaurado desde guardado anterior")
