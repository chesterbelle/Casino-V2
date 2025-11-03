"""
Base Connector Interface for Exchange Integration.

This module defines the abstract base class that all exchange connectors must implement.
Inspired by Hummingbot's connector architecture.

Architecture:
    TableCCXTPro (Mesa) → BaseConnector (Interface) → KrakenConnector (Implementation)

Key Principles:
    - Separation of concerns: Mesa handles business logic, Connector handles exchange communication
    - Standardized interface: All exchanges implement the same methods
    - Normalization: Each connector normalizes exchange-specific responses to a common format
    - Error handling: Connectors handle exchange-specific errors and retry logic
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseConnector(ABC):
    """
    Abstract base class for exchange connectors.

    All exchange connectors (Kraken, Binance, Hyperliquid, etc.) must inherit from this class
    and implement all abstract methods.

    Responsibilities:
        - Connect to exchange (REST + WebSocket)
        - Fetch market data (OHLCV, order book)
        - Execute orders
        - Fetch account data (balance, positions)
        - Normalize exchange-specific responses to common format
        - Handle exchange-specific errors and rate limits

    Example:
        ```python
        class KrakenConnector(BaseConnector):
            async def connect(self):
                # Kraken-specific connection logic
                pass

            async def fetch_ohlcv(self, symbol, timeframe, limit):
                # Kraken-specific OHLCV fetching
                pass
        ```
    """

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the exchange.

        This method should:
            1. Initialize CCXT exchange instance
            2. Configure API URLs (testnet/mainnet)
            3. Load markets
            4. Setup WebSocket connections (if enabled)
            5. Authenticate with API keys

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If API keys are invalid

        Example:
            ```python
            connector = KrakenConnector(api_key, secret, testnet=True)
            await connector.connect()
            ```
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close all connections to the exchange.

        This method should:
            1. Close WebSocket connections
            2. Close CCXT exchange instance
            3. Clean up resources

        Example:
            ```python
            await connector.close()
            ```
        """
        pass

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV (candlestick) data from the exchange.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD", "ETH/USDT")
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch (default: 100)

        Returns:
            List of normalized candle dictionaries:
            ```python
            [
                {
                    'timestamp': 1699000000000,  # Unix timestamp in ms
                    'timestamp_ms': 1699000000000,
                    'open': 35000.0,
                    'high': 35100.0,
                    'low': 34900.0,
                    'close': 35050.0,
                    'volume': 123.45,
                    'symbol': 'BTC/USD',
                    'timeframe': '1m'
                },
                ...
            ]
            ```

        Raises:
            ValueError: If symbol or timeframe is invalid
            ExchangeError: If exchange returns an error

        Example:
            ```python
            candles = await connector.fetch_ohlcv("BTC/USD", "1m", limit=100)
            latest_candle = candles[-1]
            print(f"Close: {latest_candle['close']}")
            ```
        """
        pass

    # =========================================================
    # 💰 ACCOUNT DATA
    # =========================================================

    @abstractmethod
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance from the exchange.

        Returns:
            Normalized balance dictionary:
            ```python
            {
                'total': {
                    'USD': 10000.0,
                    'BTC': 0.5,
                },
                'free': {
                    'USD': 8000.0,
                    'BTC': 0.3,
                },
                'used': {
                    'USD': 2000.0,
                    'BTC': 0.2,
                },
                'timestamp': 1699000000000,
                'currency': 'USD'  # Account currency
            }
            ```

        Raises:
            AuthenticationError: If API keys are invalid
            ExchangeError: If exchange returns an error

        Example:
            ```python
            balance = await connector.fetch_balance()
            free_usd = balance['free'].get('USD', 0.0)
            print(f"Available: ${free_usd}")
            ```
        """
        pass

    @abstractmethod
    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch open positions from the exchange (for perpetual/futures markets).

        Returns:
            List of normalized position dictionaries:
            ```python
            [
                {
                    'symbol': 'BTC/USD',
                    'side': 'LONG',  # 'LONG' or 'SHORT'
                    'size': 0.5,  # Position size
                    'entry_price': 35000.0,
                    'mark_price': 35100.0,
                    'liquidation_price': 30000.0,
                    'unrealized_pnl': 50.0,
                    'margin': 1000.0,
                    'leverage': 10,
                    'timestamp': 1699000000000
                },
                ...
            ]
            ```

        Note:
            For spot markets, this should return an empty list.

        Raises:
            ExchangeError: If exchange returns an error

        Example:
            ```python
            positions = await connector.fetch_positions()
            for pos in positions:
                print(f"{pos['symbol']}: {pos['side']} {pos['size']}")
            ```
        """
        pass

    # =========================================================
    # 📝 ORDER EXECUTION
    # =========================================================

    @abstractmethod
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
        Create an order on the exchange.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            side: Order side - 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price (required for limit orders, ignored for market orders)
            order_type: Order type - 'market' or 'limit' (default: 'market')
            params: Additional exchange-specific parameters

        Returns:
            Normalized order result:
            ```python
            {
                'id': 'order_123456',
                'symbol': 'BTC/USD',
                'side': 'buy',
                'type': 'market',
                'status': 'closed',  # 'open', 'closed', 'canceled', 'rejected'
                'price': 35000.0,  # Execution price
                'amount': 0.1,
                'filled': 0.1,
                'remaining': 0.0,
                'cost': 3500.0,  # Total cost in quote currency
                'fee': {
                    'cost': 3.5,
                    'currency': 'USD'
                },
                'timestamp': 1699000000000,
                'trades': [...]  # List of trades (if available)
            }
            ```

        Raises:
            InsufficientFunds: If account balance is insufficient
            InvalidOrder: If order parameters are invalid
            ExchangeError: If exchange returns an error

        Example:
            ```python
            # Market order
            order = await connector.create_order(
                symbol="BTC/USD",
                side="buy",
                amount=0.1,
                order_type="market"
            )

            # Limit order
            order = await connector.create_order(
                symbol="BTC/USD",
                side="buy",
                amount=0.1,
                price=35000.0,
                order_type="limit"
            )
            ```
        """
        pass

    # =========================================================
    # 🔧 UTILITY METHODS
    # =========================================================

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize a symbol to the exchange's format.

        Different exchanges use different symbol formats:
            - Kraken: "BTC/USD" → "PF_XBTUSD"
            - Binance: "BTC/USDT" → "BTCUSDT"
            - Hyperliquid: "BTC/USD" → "BTC"

        Args:
            symbol: Standard symbol format (e.g., "BTC/USD")

        Returns:
            Exchange-specific symbol format

        Example:
            ```python
            # Kraken
            normalized = connector.normalize_symbol("BTC/USD")
            # Returns: "PF_XBTUSD"
            ```
        """
        pass

    @abstractmethod
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """
        Convert exchange-specific symbol back to standard format.

        Args:
            exchange_symbol: Exchange-specific symbol (e.g., "PF_XBTUSD")

        Returns:
            Standard symbol format (e.g., "BTC/USD")

        Example:
            ```python
            # Kraken
            standard = connector.denormalize_symbol("PF_XBTUSD")
            # Returns: "BTC/USD"
            ```
        """
        pass

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """
        Get the name of the exchange.

        Returns:
            Exchange name (e.g., "kraken", "binance", "hyperliquid")

        Example:
            ```python
            print(f"Connected to: {connector.exchange_name}")
            ```
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if the connector is connected to the exchange.

        Returns:
            True if connected, False otherwise

        Example:
            ```python
            if not connector.is_connected:
                await connector.connect()
            ```
        """
        pass

    # =========================================================
    # 📈 OPTIONAL: ADVANCED FEATURES
    # =========================================================

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.

        This is an optional method with a default implementation that raises NotImplementedError.
        Connectors can override this if the exchange supports ticker data.

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker data dictionary

        Raises:
            NotImplementedError: If not implemented by the connector
        """
        raise NotImplementedError(f"{self.exchange_name} connector does not implement fetch_ticker")

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch order book for a symbol.

        This is an optional method with a default implementation that raises NotImplementedError.
        Connectors can override this if the exchange supports order book data.

        Args:
            symbol: Trading pair symbol
            limit: Depth of order book

        Returns:
            Order book dictionary

        Raises:
            NotImplementedError: If not implemented by the connector
        """
        raise NotImplementedError(f"{self.exchange_name} connector does not implement fetch_order_book")
