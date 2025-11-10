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

import logging
import os
from typing import Any, Dict, List, Literal, Optional

import ccxt.async_support as ccxt_async

from ..connector_base import BaseConnector
from .binance_constants import (
    BASE_CURRENCY,
    BINANCE_DEFAULT_CONFIG,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    WORKING_TYPE_CONTRACT_PRICE,
)
from .binance_constants import denormalize_symbol as denormalize_binance_symbol
from .binance_constants import normalize_symbol as normalize_binance_symbol

# =========================================================
# 🔧 CUSTOM CCXT CLASS FOR TESTNET
# =========================================================


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
        enable_websocket: bool = False,
    ):
        """
        Initialize Binance connector.

        Args:
            api_key: Binance API key (optional, loaded from env if not provided)
            secret: Binance API secret (optional, loaded from env if not provided)
            mode: "testnet" for testnet (recommended), "live" for production
            enable_websocket: Enable WebSocket (not implemented yet)
        """
        self.logger = logging.getLogger("BinanceConnector")

        if mode not in {"testnet", "live"}:
            raise ValueError(f"Invalid mode for BinanceConnector: {mode}")

        self._mode = mode
        self._testnet = mode == "testnet"
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
        self.logger.info(f"✅ Binance connector initialized | Mode: {mode.upper()}")

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

            min_amount = amount_limits.get("min", 0)
            max_amount = amount_limits.get("max", float("inf"))

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

        # Determine closing side (opposite of entry)
        close_side = "sell" if side == "buy" else "buy"

        # Create Take Profit order if specified
        if tp_price:
            try:
                # Round TP price to correct precision
                binance_symbol = self.normalize_symbol(symbol)
                tp_price_rounded = float(self.exchange.price_to_precision(binance_symbol, tp_price))

                tp_params = {
                    "stopPrice": tp_price_rounded,
                    "workingType": WORKING_TYPE_CONTRACT_PRICE,
                    "positionSide": "BOTH",
                }
                await self.exchange.create_order(
                    symbol=binance_symbol,
                    type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                    side=close_side,
                    amount=amount,
                    params=tp_params,
                )
                self.logger.info(f"✅ Take Profit order created at {tp_price_rounded}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create TP order: {e}")
                # Don't raise, main order is already created

        # Create Stop Loss order if specified
        if sl_price:
            try:
                # Round SL price to correct precision
                binance_symbol = self.normalize_symbol(symbol)
                sl_price_rounded = float(self.exchange.price_to_precision(binance_symbol, sl_price))

                sl_params = {
                    "stopPrice": sl_price_rounded,
                    "workingType": WORKING_TYPE_CONTRACT_PRICE,
                    "positionSide": "BOTH",
                }
                await self.exchange.create_order(
                    symbol=binance_symbol,
                    type=ORDER_TYPE_STOP_MARKET,
                    side=close_side,
                    amount=amount,
                    params=sl_params,
                )
                self.logger.info(f"✅ Stop Loss order created at {sl_price_rounded}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create SL order: {e}")
                # Don't raise, main order is already created

        self.logger.info(
            f"✅ Order with TP/SL created | "
            f"ID: {main_order['id']} | "
            f"TP: {tp_price or 'None'} | "
            f"SL: {sl_price or 'None'}"
        )

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

    async def fetch_my_trades(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch user's trade history from Binance.

        Args:
            symbol: Optional symbol to filter
            limit: Optional limit

        Returns:
            List of trades
        """
        try:
            binance_symbol = self.normalize_symbol(symbol) if symbol else None
            trades = await self.exchange.fetch_my_trades(binance_symbol, limit=limit)
            self.logger.debug(f"📊 Trades fetched: {len(trades)}")
            return trades
        except Exception as e:
            self.logger.error(f"❌ Error fetching trades: {e}")
            raise

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
