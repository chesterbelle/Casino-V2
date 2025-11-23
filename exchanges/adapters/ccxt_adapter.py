"""
CCXTAdapter - Adaptador CCXT para Mesas (DataSource).

Este adaptador envuelve la lógica de negocio del trading y delega
la comunicación con exchanges a conectores modulares específicos.

⚠️  ARQUITECTURA MODULAR - IMPORTANTE:
================================================================================
Este adaptador DEBE ser 100% EXCHANGE-AGNOSTIC.
NO agregar lógica específica de ningún exchange aquí.

Arquitectura (v2.0):
    Mesa (DataSource) → CCXTAdapter (Adaptador) → Conector (Driver) → CCXT → Exchange

    Ejemplo:
    LiveDataSource → CCXTAdapter → KrakenConnector → CCXT → Kraken API

================================================================================

📋 RESPONSABILIDADES DEL ADAPTADOR (CCXTAdapter):
    ✅ PERMITIDO (Business Logic - Exchange Agnostic):
        - Gestión de balance (BalanceManager)
        - Tracking de posiciones (PositionTracker)
        - Validación de órdenes (límites, balance)
        - Cálculo de precios TP/SL (multipliers → absolute prices)
        - Logging y auditoría
        - Sincronización de estado real (ExchangeStateSync)

    ❌ PROHIBIDO (Exchange-Specific Logic):
        - Lógica específica de Kraken, Binance, etc.
        - Tipos de órdenes específicos de un exchange
        - Parámetros específicos de un exchange
        - Manejo de particularidades de un exchange

📋 RESPONSABILIDADES DEL CONECTOR (KrakenConnector, BinanceConnector, etc.):
    ✅ PERMITIDO (Exchange-Specific Implementation):
        - Comunicación con el exchange (REST + WebSocket)
        - Normalización de datos del exchange
        - Manejo de errores específicos del exchange
        - Rate limiting específico del exchange
        - Implementación de TP/SL según particularidades del exchange
        - Tipos de órdenes específicos (take_profit, stop, etc.)
        - Parámetros específicos (reduceOnly, triggerPrice, etc.)

================================================================================

🔄 FLUJO DE EJECUCIÓN DE ÓRDENES CON TP/SL:

    1. CCXTAdapter.execute_order(order):
       ├── Validar orden (balance, límites) ← Business logic
       ├── Calcular precios TP/SL absolutos ← Business logic
       │   tp_price = current_price * tp_multiplier
       │   sl_price = current_price * sl_multiplier
       └── Delegar a conector ↓

    2. Connector.create_order_with_tpsl(tp_price, sl_price):
       ├── Kraken: Crear órdenes separadas (take_profit, stop)
       ├── Binance: Agregar TP/SL como params en orden principal
       └── Hyperliquid: Usar su propio mecanismo de TP/SL

    Resultado: Adaptador agnóstico, cada conector maneja sus particularidades

================================================================================

📚 REFERENCIAS:
    - Análisis completo: docs/ARQUITECTURA_MODULARIDAD_ANALISIS.md
    - Interface de conectores: exchanges/connectors/connector_base.py
    - Ejemplo de implementación: exchanges/connectors/kraken/kraken_connector.py

⚠️  ANTES DE MODIFICAR ESTE ARCHIVO:
    1. Pregúntate: ¿Esta lógica es específica de un exchange?
    2. Si SÍ → Debe ir en el conector, NO aquí
    3. Si NO → Puede ir aquí (es business logic)
    4. En duda → Consultar docs/ARQUITECTURA_MODULARIDAD_ANALISIS.md

================================================================================

Usage:
    ```python
    from exchanges.connectors import KrakenConnector
    from exchanges.adapters import CCXTAdapter

    # Create connector (exchange-specific driver)
    connector = KrakenConnector(testnet=True)

    # Create adapter (exchange-agnostic business logic)
    adapter = CCXTAdapter(
        connector=connector,
        symbol="BTC/USD",
        timeframe="1m"
    )

    # Connect and use
    await adapter.connect()
    candle = await adapter.next_candle()
    result = await adapter.execute_order(order)
    await adapter.close()
    ```
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from exchanges.connectors.connector_base import BaseConnector

from .table_base import BaseTable


class CCXTAdapter(BaseTable):
    async def fetch_positions(self, symbols: list = None) -> list:
        """
        Fetch open positions, preferring WS if enabled and available.
        """
        cond1 = self.prefer_ws
        cond2 = hasattr(self.connector, "watch_positions")
        cond3 = getattr(self.connector, "enable_websocket", False)
        self.logger.debug(f"prefer_ws={self.prefer_ws} (type={type(self.prefer_ws)})")
        self.logger.debug(f"cond1 (prefer_ws): {cond1}")
        self.logger.debug(f"cond2 (has_watch_positions): {cond2}")
        self.logger.debug(f"cond3 (enable_websocket): {cond3}")
        self.logger.debug(f"connector.watch_positions={self.connector.watch_positions}")
        # Detect WebSocket availability: prefer_ws flag + connector support
        has_ws_api = cond2 and cond3
        ws_available = bool(cond1 and has_ws_api)
        self.logger.debug(
            f"has_ws_api={has_ws_api} (watch_positions and enable_websocket) | ws_available={ws_available}"
        )

        # If symbols is a list of one, pass as string (ccxt.pro expects symbol: str)
        ws_arg = symbols
        if isinstance(symbols, list) and len(symbols) == 1:
            ws_arg = symbols[0]

        self.logger.debug(f"fetch_positions called with symbols={symbols}")
        self.logger.debug(f"ws_arg computed as: {ws_arg} (type={type(ws_arg)})")

        if ws_available:
            try:
                self.logger.debug("Trying WS positions...")
                self.logger.info("Trying WS positions...")
                if ws_arg is None:
                    self.logger.debug("Calling connector.watch_positions() with no symbols")
                    result = await self.connector.watch_positions()
                else:
                    self.logger.debug(f"Calling connector.watch_positions({ws_arg})")
                    result = await self.connector.watch_positions(ws_arg)
                self.logger.debug(f"Result from WS: {result}")
                return result
            except NotImplementedError:
                self.logger.debug("NotImplementedError in WS positions, falling back to REST")
                self.logger.info("WS positions not available, falling back to REST.")
                self.logger.debug(f"Calling connector.fetch_positions({symbols or [self.symbol]})")
                result = await self.connector.fetch_positions(symbols or [self.symbol])
                self.logger.debug(f"Result from REST: {result}")
                return result
            except Exception as e:
                self.logger.debug(f"Exception in WS positions: {e}")
                self.logger.error(f"WS positions error (no fallback): {e}")
                raise
        self.logger.debug("Using REST positions.")
        self.logger.info("Using REST positions.")
        self.logger.debug(f"Calling connector.fetch_positions({symbols or [self.symbol]})")
        result = await self.connector.fetch_positions(symbols or [self.symbol])
        self.logger.debug(f"Result from REST: {result}")
        return result

    """
    Adaptador CCXT que envuelve lógica de negocio y delega comunicación a conectores.

    Este adaptador es usado internamente por TestingDataSource y LiveDataSource
    para manejar la lógica de trading (balance, posiciones, TP/SL) mientras
    delega la comunicación con el exchange a conectores específicos (KrakenConnector, etc.).

    Arquitectura:
        DataSource (Mesa) usa -> CCXTAdapter (este) usa -> Conector (KrakenConnector)
    """

    async def fetch_balance(self) -> dict:
        """
        Fetch account balance, preferring WS if enabled and available.
        """
        if self.prefer_ws and hasattr(self.connector, "watch_balance"):
            try:
                return await self.connector.watch_balance()
            except NotImplementedError:
                self.logger.info("WS balance not available, falling back to REST.")
            except Exception as e:
                self.logger.error(f"WS balance error: {e}, falling back to REST.")
        return await self.connector.fetch_balance()

    def __init__(
        self,
        connector: BaseConnector,
        symbol: str,
        timeframe: str = "1m",
        prefer_ws: bool = False,
    ):
        """
        Inicializa el adaptador CCXT con el conector y configuración.
        """
        super().__init__()
        # El conector es la única dependencia.
        self.connector = connector

        # Configuración básica de operación
        self.symbol = symbol
        self.timeframe = timeframe
        self.prefer_ws = prefer_ws

        # Logger setup
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info(f"Stateless CCXTAdapter initialized | Symbol: {self.symbol} | Timeframe: {self.timeframe}")

        # El adapter es sin estado, solo delega. La instancia de exchange se obtiene del conector.
        self.exchange = getattr(self.connector, "exchange", None)
        if not self.exchange:
            raise ValueError("El conector debe tener una instancia `exchange` de ccxt inicializada.")

    async def connect(self) -> None:
        """Connect the underlying connector if it provides a connect method.

        This method should be called before any data fetching operations.
        """
        if hasattr(self.connector, "connect"):
            await self.connector.connect()
        else:
            self.logger.warning("Connector does not implement async connect().")

    # duplicate fetch_positions block removed

    async def fetch_order_book(self, symbol: str = None, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch order book, preferring WS if enabled and available.
        """
        symbol = symbol or self.symbol
        if self.prefer_ws and hasattr(self.connector, "watch_order_book"):
            try:
                return await self.connector.watch_order_book(symbol, limit)
            except NotImplementedError:
                self.logger.info("WS order book not available, falling back to REST.")
            except Exception as e:
                self.logger.error(f"WS order book error: {e}, falling back to REST.")
        return await self.connector.fetch_order_book(symbol, limit)

    async def get_current_price(self, symbol: str = None) -> float:
        """
        Get current market price for a symbol (async).

        Args:
            symbol: Trading symbol (uses self.symbol if not provided)

        Returns:
            Current price as float

        Raises:
            RuntimeError: If not connected
            ValueError: If price cannot be obtained
        """
        symbol = symbol or self.symbol
        self.logger.info(f"🔍 get_current_price | requested_symbol={symbol} | adapter_symbol={self.symbol}")

        try:
            # Obtener ticker del exchange (async)
            ticker = await self.connector.fetch_ticker(symbol)
            current_price = ticker.get("last")

            # Validar que el precio sea válido (no None, no 0, no negativo)
            if current_price is None or current_price == 0 or current_price < 0:
                # Intentar con "close" como fallback
                current_price = ticker.get("close")
                if current_price is None or current_price == 0 or current_price < 0:
                    # Intentar con "bid" como último recurso
                    current_price = ticker.get("bid")
                    if current_price is None or current_price == 0 or current_price < 0:
                        raise ValueError(f"No valid price data available for {symbol}. Ticker: {ticker}")

            current_price = float(current_price)
            self.logger.info(f"💰 Current price for {symbol}: {current_price}")
            return current_price

        except Exception as e:
            self.logger.error(f"❌ Error getting current price for {symbol}: {e}")
            raise ValueError(f"Cannot get current price for {symbol}: {e}")

    async def register_oco_pair(self, symbol: str, tp_order_id: str, sl_order_id: str):
        """
        Registers an OCO pair with the underlying connector if supported.
        """
        if hasattr(self.connector, "register_oco_pair"):
            await self.connector.register_oco_pair(symbol, tp_order_id, sl_order_id)

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================

    async def next_candle(self) -> Optional[Dict]:
        """
        Obtiene la siguiente vela del exchange. No gestiona estado.
        Falla rápido si el conector no devuelve datos.
        """
        candles = await self.connector.fetch_ohlcv(self.symbol, self.timeframe, limit=1)
        if not candles:
            return None

        raw_candle = candles[0]
        candle_dict = {
            "timestamp": raw_candle[0],
            "open": raw_candle[1],
            "high": raw_candle[2],
            "low": raw_candle[3],
            "close": raw_candle[4],
            "volume": raw_candle[5],
        }
        self._last_candle = candle_dict
        return candle_dict

    # =========================================================
    # 📝 ORDER EXECUTION
    # =========================================================

    async def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta una orden en el exchange.

        Nota: OCO Manual es responsabilidad de Croupier.
        Este adapter solo crea órdenes individuales.
        """
        try:
            # Traducir formato de Croupier a CCXT si es necesario
            if order.get("side") in ["LONG", "SHORT"]:
                order = order.copy()
                order["side"] = "buy" if order["side"] == "LONG" else "sell"

            # Todas las órdenes van por el mismo camino
            # Execute order via connector
            # Note: optional WS-confirmation flags may be present in `order` but
            # are not used by the generic adapter implementation.
            result = await self.connector.create_order(**order)
            return result
        except Exception as e:
            self.logger.error(f"❌ Error executing order: {e}")
            raise

    def normalize_trade(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza un trade usando la implementación específica del connector.

        Args:
            raw_trade: Trade en formato crudo del exchange

        Returns:
            Trade normalizado con campos adicionales:
            - is_close: bool - Si es un cierre de posición
            - realized_pnl: float - PnL realizado (si es cierre)
            - close_reason: str - Razón del cierre ("TP", "SL", "MANUAL", etc.)
        """
        if hasattr(self.connector, "normalize_trade"):
            return self.connector.normalize_trade(raw_trade)
        else:
            # Fallback agnóstico si el connector no implementa normalize_trade
            return {**raw_trade, "is_close": False, "realized_pnl": 0.0, "close_reason": None}

    async def _calculate_tpsl_prices(self, order: Dict) -> tuple[Optional[float], Optional[float]]:
        """
        Calcula los precios absolutos de TP/SL a partir de multiplicadores.
        """
        if "take_profit" not in order or not order["take_profit"]:
            return None, None

        try:
            current_price = await self.get_current_price(order.get("symbol", self.symbol))
            tp_multiplier = float(order["take_profit"])
            sl_multiplier = float(order["stop_loss"])

            # Lógica corregida para LONG/SHORT con margen de seguridad
            safety_margin_factor = 0.0005  # 0.05% de margen para el SL

            if order.get("side") == "buy":  # LONG
                tp_price = current_price * tp_multiplier
                # Asegurarse de que el SL esté claramente por debajo del precio actual
                sl_price = current_price * sl_multiplier * (1 - safety_margin_factor)
            else:  # SHORT
                # Para SHORT, el TP está por debajo y el SL por encima.
                tp_price = current_price * (2.0 - tp_multiplier)
                # Asegurarse de que el SL esté claramente por encima del precio actual
                sl_price = current_price * (2.0 - sl_multiplier) * (1 + safety_margin_factor)

            return tp_price, sl_price
        except Exception as e:
            self.logger.error(f"❌ Error calculando precios TP/SL: {e}")
            raise

    # =========================================================
    # 📊 PROPERTIES
    # =========================================================

    @property
    def exchange_name(self) -> str:
        """Get exchange name."""
        return self.connector.exchange_name

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        Cancela una orden.
        """
        return await self.connector.cancel_order(order_id, symbol)

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """
        Obtiene información de una orden.
        """
        return await self.connector.fetch_order(order_id, symbol)

    async def disconnect(self) -> None:
        """
        Desconecta el adaptador y su conector subyacente.
        """
        if hasattr(self.connector, "disconnect"):
            await self.connector.disconnect()
        elif hasattr(self.connector, "close"):
            await self.connector.close()
