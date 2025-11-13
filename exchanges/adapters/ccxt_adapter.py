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
from typing import Dict, Optional

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

        # Estado de conexión
        self._connected = False
        self._last_candle: Optional[Dict] = None
        self.exchange = None

        self.logger.info(f"Stateless CCXTAdapter initialized | Symbol: {self.symbol} | Timeframe: {self.timeframe}")

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================

    async def connect(self) -> None:
        """
        Conecta al exchange a través del conector.
        Falla rápido si la conexión no se puede establecer.
        """
        try:
            self.logger.info(f"🔌 Conectando a {self.connector.exchange_name}...")
            await self.connector.connect()
            self.exchange = getattr(self.connector, "exchange", None)

            # Prueba de conexión simple para asegurar que la API responde
            await self.connector.fetch_ticker(self.symbol)

            self._connected = True
            self.logger.info(f"✅ Conectado a {self.connector.exchange_name}")

        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}")
            raise  # Propaga la excepción al Croupier

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
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        symbol = symbol or self.symbol
        self.logger.info(f"🔍 get_current_price | requested_symbol={symbol} | adapter_symbol={self.symbol}")

        try:
            # Obtener ticker del exchange (async)
            ticker = await self.connector.fetch_ticker(symbol)
            current_price = ticker.get("last")

            if current_price is None:
                raise ValueError(f"No price data available for {symbol}")

            self.logger.info(f"💰 Current price for {symbol}: {current_price}")
            return float(current_price)

        except Exception as e:
            self.logger.error(f"❌ Error getting current price for {symbol}: {e}")
            raise ValueError(f"Cannot get current price for {symbol}: {e}")

    async def close(self) -> None:
        """
        Close connection to the exchange.

        Closes the connector and cleans up resources.
        """
        try:
            await self.connector.close()
            self._connected = False
            self.logger.info("🔌 Conexión cerrada")
        except Exception as e:
            self.logger.warning(f"⚠️ Error cerrando conexión: {e}")

    # =========================================================
    # 📊 MARKET DATA
    # =========================================================

    async def next_candle(self) -> Optional[Dict]:
        """
        Obtiene la siguiente vela del exchange. No gestiona estado.
        Falla rápido si el conector no devuelve datos.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

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
        Ejecuta una orden en el exchange. No valida balance ni gestiona estado.
        Simplemente traduce y delega al conector.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # 1. Traducir formato de Croupier a CCXT si es necesario
            if order.get("side") in ["LONG", "SHORT"]:
                order = order.copy()
                order["side"] = "buy" if order["side"] == "LONG" else "sell"

            # 2. Calcular precios absolutos de TP/SL (lógica de negocio que permanece aquí)
            tp_price, sl_price = await self._calculate_tpsl_prices(order)

            # 3. Delegar ejecución al conector
            result = await self.connector.create_order_with_tpsl(
                symbol=order.get("symbol", self.symbol),
                side=order["side"],
                amount=order["amount"],
                price=order.get("price"),
                order_type=order.get("type", "market"),
                tp_price=tp_price,
                sl_price=sl_price,
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

            # Lógica corregida para LONG/SHORT
            if order.get("side") == "buy":  # LONG
                # Para LONG, TP > entry, SL < entry. Multiplicadores: tp > 1, sl < 1
                tp_price = current_price * tp_multiplier
                sl_price = current_price * sl_multiplier
            else:  # SHORT
                # Para SHORT, TP < entry, SL > entry. Los multiplicadores deben ser inversos.
                # Asumimos que la orden llega con multiplicadores para LONG (tp > 1, sl < 1)
                # por lo que los invertimos aquí.
                tp_price = current_price * (1.0 / tp_multiplier)  # Invertir para que baje el precio
                sl_price = current_price * (1.0 / sl_multiplier)  # Invertir para que suba el precio

            return tp_price, sl_price
        except Exception as e:
            self.logger.error(f"❌ Error calculando precios TP/SL: {e}")
            raise

    # =========================================================
    # 📊 PROPERTIES
    # =========================================================

    @property
    def is_connected(self) -> bool:
        """Check if connected to exchange."""
        return self._connected

    @property
    def exchange_name(self) -> str:
        """Get exchange name."""
        return self.connector.exchange_name
