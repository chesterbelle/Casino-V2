"""
Kraken Futures Connector Implementation.

This connector provides integration with Kraken Futures exchange (testnet + mainnet).
Extracted and refactored from table_ccxt_pro_legacy.py.

Features:
    - REST API integration via CCXT
    - WebSocket support (optional)
    - Testnet and mainnet support
    - Automatic credential loading
    - Symbol normalization
    - Error handling and retry logic

Usage:
    ```python
    from tables.connectors.kraken import KrakenConnector

    # With explicit credentials
    connector = KrakenConnector(
        api_key="your_key",
        secret="your_secret",
        testnet=True
    )

    # Or auto-load from environment
    connector = KrakenConnector(testnet=True)

    # Connect and use
    await connector.connect()
    candles = await connector.fetch_ohlcv("BTC/USD", "1m", limit=100)
    balance = await connector.fetch_balance()
    await connector.close()
    ```
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt_async

from ..connector_base import BaseConnector
from .kraken_constants import BASE_CURRENCY, KRAKEN_DEFAULT_CONFIG
from .kraken_constants import denormalize_symbol as denormalize_kraken_symbol
from .kraken_constants import get_urls
from .kraken_constants import normalize_symbol as normalize_kraken_symbol


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
        testnet: bool = True,
        enable_websocket: bool = False,
    ):
        """
        Initialize Kraken connector.

        Args:
            api_key: Kraken API key (if None, will try to load from environment)
            secret: Kraken API secret (if None, will try to load from environment)
            testnet: If True, use demo environment; if False, use mainnet
            enable_websocket: If True, enable WebSocket connections (experimental)
        """
        self.logger = logging.getLogger("KrakenConnector")

        # Configuration
        self.testnet = testnet
        self.enable_websocket = enable_websocket

        # Load credentials if not provided
        if api_key is None or secret is None:
            self.logger.info("📝 Cargando credenciales de Kraken desde environment...")
            loaded_creds = self._load_credentials()
            api_key = api_key or loaded_creds.get("apiKey")
            secret = secret or loaded_creds.get("secret")

        if not api_key or not secret:
            raise ValueError(
                "Kraken API credentials not provided and not found in environment. "
                "Set KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables."
            )

        self.api_key = api_key
        self.secret = secret

        # State
        self.exchange: Optional[ccxt_async.Exchange] = None
        self._connected = False
        self._markets: Dict[str, Any] = {}

        env_name = "DEMO" if testnet else "MAINNET"
        self.logger.info(f"🔧 KrakenConnector inicializado | Env: {env_name}")

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
            self.logger.info("🔌 Conectando a Kraken Futures...")

            # Get URLs based on environment
            urls = get_urls(self.testnet)

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

            env_name = "DEMO" if self.testnet else "MAINNET"
            market_count = len(self._markets)
            self.logger.info(f"✅ Conectado a Kraken Futures {env_name} | {market_count} mercados cargados")

        except ccxt_async.AuthenticationError as e:
            self.logger.error(f"❌ Error de autenticación: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error conectando a Kraken: {e}")
            raise ConnectionError(f"Failed to connect to Kraken: {e}")

    async def close(self) -> None:
        """
        Close connection to Kraken exchange.

        Closes the CCXT exchange instance and cleans up resources.
        """
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

            # Fetch OHLCV from Kraken
            ohlcv = await self.exchange.fetch_ohlcv(kraken_symbol, timeframe, limit=limit)

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
            # Fetch balance from Kraken
            balance = await self.exchange.fetch_balance()

            # Normalize format
            normalized = {
                "total": balance.get("total", {}),
                "free": balance.get("free", {}),
                "used": balance.get("used", {}),
                "timestamp": balance.get("timestamp"),
                "currency": BASE_CURRENCY,
            }

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

            # Normalize format
            normalized = []
            for pos in positions:
                normalized.append(
                    {
                        "symbol": self.denormalize_symbol(pos.get("symbol", "")),
                        "side": pos.get("side", "").upper(),  # 'LONG' or 'SHORT'
                        "size": float(pos.get("contracts", 0)),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "mark_price": float(pos.get("markPrice", 0)),
                        "liquidation_price": float(pos.get("liquidationPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                        "margin": float(pos.get("initialMargin", 0)),
                        "leverage": float(pos.get("leverage", 1)),
                        "timestamp": pos.get("timestamp"),
                    }
                )

            return normalized

        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
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

            # Create order on Kraken
            order = await self.exchange.create_order(
                symbol=kraken_symbol,
                type=order_type,
                side=side.lower(),
                amount=amount,
                price=price,
                params=params or {},
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
        return normalize_kraken_symbol(symbol)

    def denormalize_symbol(self, kraken_symbol: str) -> str:
        """
        Convert Kraken symbol back to standard format.

        Args:
            kraken_symbol: Kraken format (e.g., "PF_XBTUSD")

        Returns:
            Standard format (e.g., "BTC/USD")
        """
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
