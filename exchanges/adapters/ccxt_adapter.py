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
    """
    Adaptador CCXT que envuelve lógica de negocio y delega comunicación a conectores.

    Este adaptador es usado internamente por TestingDataSource y LiveDataSource
    para manejar la lógica de trading (balance, posiciones, TP/SL) mientras
    delega la comunicación con el exchange a conectores específicos (KrakenConnector, etc.).

    Arquitectura:
        DataSource (Mesa) usa → CCXTAdapter (este) usa → Conector (KrakenConnector)

    Responsabilidades:
        - Balance management (BalanceManager)
        - Position tracking (PositionTracker)
        - Order validation
        - TP/SL logic
        - Exchange state sync (ExchangeStateSync)
        - Logging
    """

    def __init__(
        self,
        connector: BaseConnector,
        symbol: str,
        timeframe: str = "1m",
    ):
        """
        Inicializa el CCXTAdapter sin estado.

        Args:
            connector: Conector específico del exchange (p. ej., BinanceConnector).
            symbol: Símbolo de trading por defecto.
            timeframe: Timeframe de las velas por defecto.
        """
        super().__init__()
        self.logger = logging.getLogger("CCXTAdapter")

        # El conector es la única dependencia.
        self.connector = connector

        # Configuración básica de operación
        self.symbol = symbol
        self.timeframe = timeframe

        # El adapter es sin estado, solo delega. La instancia de exchange se obtiene del conector.
        self.exchange = getattr(self.connector, "exchange", None)
        if not self.exchange:
            raise ValueError("El conector debe tener una instancia `exchange` de ccxt inicializada.")

        self.logger.info(f"Stateless CCXTAdapter initialized | Symbol: {self.symbol} | Timeframe: {self.timeframe}")

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
            result = await self.connector.create_order(
                symbol=order.get("symbol", self.symbol),
                side=order["side"],
                amount=order["amount"],
                price=order.get("price"),
                order_type=order.get("type", "market"),
                params=order.get("params", {}),
            )

            if not isinstance(result, dict):
                raise ValueError(f"El conector devolvió un resultado inválido: {result}")

            self.logger.info(
                f"✅ Orden delegada al conector | {result.get('symbol')} {result.get('side', '').upper()} {result.get('amount')}"
            )
            return result

        except Exception as e:
            self.logger.error(f"❌ Error en la ejecución de la orden: {e}")
            raise  # Propaga la excepción al Croupier

    async def cancel_order(self, order_id: str, symbol: str = None) -> Dict:
        """Cancel an order."""
        try:
            result = await self.connector.cancel_order(order_id, symbol or self.symbol)
            self.logger.info(f"✅ Orden cancelada | ID: {order_id}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error cancelando orden {order_id}: {e}")
            raise

    async def fetch_order(self, order_id: str, symbol: str = None) -> Dict:
        """Fetch order status."""
        try:
            result = await self.connector.fetch_order(order_id, symbol or self.symbol)
            return result
        except Exception as e:
            self.logger.error(f"❌ Error fetching order {order_id}: {e}")
            raise

    async def fetch_ticker(self, symbol: str = None) -> Dict:
        """Fetch ticker data (price, volume, etc.)."""
        try:
            result = await self.connector.fetch_ticker(symbol or self.symbol)
            return result
        except Exception as e:
            self.logger.error(f"❌ Error fetching ticker for {symbol or self.symbol}: {e}")
            raise

    async def fetch_positions(self, symbols: list = None) -> list:
        """Fetch open positions."""
        try:
            result = await self.connector.fetch_positions(symbols or [self.symbol])
            return result
        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
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
