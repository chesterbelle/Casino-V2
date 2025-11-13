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

import asyncio
import logging
from typing import Any, Dict, Optional

from core.portfolio.balance_manager import BalanceManager
from core.portfolio.position_tracker import PositionTracker
from exchanges.connectors.connector_base import BaseConnector
from exchanges.resilience.balance_cache import BalanceCache

from .exchange_state_sync import ExchangeStateSync
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
        starting_balance: float = 10000.0,
    ):
        """
        Initialize CCXTAdapter with a connector.

        Args:
            connector: Exchange connector (e.g., KrakenConnector, BinanceConnector)
                      This is the driver that handles exchange-specific communication.
            symbol: Trading pair symbol (e.g., "BTC/USD")
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h")
            starting_balance: Initial balance for simulation (only used if real balance fails)
        """
        super().__init__()
        self.logger = logging.getLogger("CCXTAdapter")

        # Connector (dependency injection)
        self.connector = connector

        # Configuration
        self.symbol = symbol
        self.timeframe = timeframe
        self.base_currency = getattr(connector, "base_currency", "USD")

        # Components (business logic)
        self.balance_manager = BalanceManager(starting_balance=starting_balance)
        # Usar modo 'confirmed' para cerrar posiciones cuando se detecta cierre en exchange
        self.position_tracker = PositionTracker(mode="confirmed")

        # NUEVO: Sincronizador de estado real
        self.state_sync = ExchangeStateSync(connector)

        # NUEVO: Balance cache con fallback (CRÍTICO)
        self.balance_cache = BalanceCache(
            cache_ttl=30.0,  # Cache válido por 30 segundos
            max_age=300.0,  # Máximo 5 minutos de staleness
            currency=self.base_currency,
        )

        # State
        self._connected = False
        self._last_candle: Optional[Dict] = None
        self._last_balance_snapshot: Optional[Dict[str, Any]] = None
        self._last_sync_time = 0
        self.exchange = None

        self.logger.info(f"CCXTAdapter initialized | Symbol: {self.symbol} | Timeframe: {self.timeframe}")

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================

    async def connect(self) -> None:
        """
        Connect to the exchange via the connector.

        This method:
            1. Connects the connector to the exchange
            2. Waits for connector to be ready
            3. Fetches initial balance
            4. Validates connection

        Raises:
            ConnectionError: If connection fails
            RuntimeError: If balance cannot be fetched (CRITICAL SECURITY RULE)
        """
        try:
            self.logger.info("🔌 Conectando a exchange...")

            # Connect via connector
            await self.connector.connect()
            self.exchange = getattr(self.connector, "exchange", None)

            # Wait for connector to be ready (Hummingbot-inspired)
            max_wait = 10  # seconds
            waited = 0

            # Check if connector has ready property
            if hasattr(self.connector, "ready"):
                while not self.connector.ready and waited < max_wait:
                    self.logger.info(f"⏳ Esperando que conector esté listo... ({waited}s)")
                    await asyncio.sleep(1)
                    waited += 1

                if not self.connector.ready:
                    raise RuntimeError(
                        f"Connector not ready after {max_wait}s. " f"Status: {self.connector.status_dict}"
                    )

                self.logger.info(f"✅ Connector ready | Status: {self.connector.status_dict}")
            else:
                # Fallback: assume connector is ready if it doesn't have ready property
                self.logger.warning("⚠️ Connector doesn't have 'ready' property, assuming ready")
                self.logger.info(f"✅ Connector assumed ready | Type: {type(self.connector).__name__}")

            # Fetch initial balance (CRITICAL: fail-fast if this fails)
            try:
                balance_data = await self.connector.fetch_balance()
                self._update_balance(balance_data)
                self.logger.info("✅ Balance inicial obtenido del exchange")
            except Exception as e:
                # CRITICAL SECURITY RULE: Never use default balance in LIVE mode
                self.logger.error(f"❌ CRÍTICO: No se pudo obtener balance real: {e}")
                raise RuntimeError(
                    "CRITICAL: Cannot obtain real balance from exchange. "
                    "System MUST stop. Never use default/simulated balance in LIVE mode."
                )

            self._connected = True
            self.logger.info(f"✅ Conectado a {self.connector.exchange_name} | Symbol: {self.symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}")
            raise

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
        Get the next candle from the exchange + sincroniza estado real.

        REFACTORIZADO v1.9.1: Ahora retorna vela enriquecida con estado real del exchange:
        - equity: balance + unrealized_pnl (REAL)
        - balance: balance libre (REAL)
        - unrealized_pnl: PnL no realizado (REAL)
        - open_positions: número de posiciones abiertas
        - positions: lista de posiciones reales
        - recent_fills: fills confirmados desde última sync
        - state_source: "exchange_confirmed" (FLAG IMPORTANTE)

        Returns:
            Vela enriquecida con estado real o None si no hay datos

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # 1. Obtener vela (como antes)
            candles = await self.connector.fetch_ohlcv(self.symbol, self.timeframe, limit=1)

            if not candles:
                return None

            candle = candles[0]

            # 2. NUEVO: Sincronizar estado real del exchange
            try:
                equity_snapshot = await self.state_sync.sync_equity()
                positions = await self.state_sync.sync_positions()
                recent_fills = await self.state_sync.sync_fills(since=self._last_sync_time)

                # Log para debugging
                if recent_fills:
                    self.logger.info(f"🔍 Detectados {len(recent_fills)} fills desde {self._last_sync_time}")

                # 3. NUEVO: Procesar fills confirmados
                for fill in recent_fills:
                    self.logger.debug(
                        f"📊 Fill confirmado: {fill.symbol} {fill.side} "
                        f"@ {fill.price:.2f} | Amount: {fill.amount:.4f}"
                    )

                    # Si es un fill de cierre, confirmar el cierre en el position tracker
                    if fill.is_close:
                        # Buscar la posición abierta que corresponde a este fill
                        for pos in self.position_tracker.open_positions:
                            # Verificar si el fill corresponde a esta posición
                            # (mismo símbolo y dirección opuesta al fill)
                            if pos.symbol == fill.symbol:
                                # Confirmar el cierre con los datos reales del exchange
                                result = self.position_tracker.confirm_close(
                                    trade_id=pos.trade_id,
                                    exit_price=fill.price,
                                    exit_reason=fill.reason or "MANUAL",
                                    pnl=fill.realized_pnl,
                                    fee=fill.fee,
                                )
                                if result:
                                    self.logger.info(
                                        f"✅ Posición cerrada confirmada | {pos.trade_id} | "
                                        f"Exit: {fill.price:.2f} | PnL: ${fill.realized_pnl:.2f}"
                                    )
                                break

                # 4. Actualizar balance interno con equity real
                self.balance_manager.set_balance(equity_snapshot.balance)

                # 5. Retornar vela enriquecida con estado REAL
                enriched_candle = {
                    **candle,
                    # Estado real del exchange
                    "equity": equity_snapshot.equity,  # ← REAL
                    "balance": equity_snapshot.balance,  # ← REAL
                    "unrealized_pnl": equity_snapshot.unrealized_pnl,  # ← REAL
                    "margin_used": equity_snapshot.margin_used,
                    "margin_available": equity_snapshot.margin_available,
                    # Posiciones y fills
                    "open_positions": len(positions),
                    "positions": positions,
                    "recent_fills": recent_fills,
                    # Metadata
                    "sync_timestamp": equity_snapshot.timestamp,
                    "state_source": "exchange_confirmed",  # ← FLAG IMPORTANTE
                }

                self._last_candle = enriched_candle
                self._last_sync_time = equity_snapshot.timestamp

                self.logger.debug(
                    f"✅ Vela enriquecida | Equity: {equity_snapshot.equity:.2f} | "
                    f"Positions: {len(positions)} | Fills: {len(recent_fills)}"
                )

                return enriched_candle

            except Exception as sync_error:
                # Si falla la sincronización, retornar vela básica con warning
                self.logger.warning(
                    f"⚠️ Error sincronizando estado: {sync_error}. " f"Retornando vela sin estado enriquecido."
                )
                return candle

        except Exception as e:
            self.logger.error(f"❌ Error fetching candle: {e}")
            raise

    # =========================================================
    # 📝 ORDER EXECUTION
    # =========================================================

    async def execute_order(self, order: Dict) -> Dict:
        """
        Execute an order on the exchange.

        This method:
            1. Validates the order (balance, limits, etc.)
            2. Executes via connector
            3. Updates internal state (balance, positions)

        Args:
            order: Order dictionary with keys:
                - symbol: Trading pair
                - side: 'buy' or 'sell'
                - amount: Order size
                - type: 'market' or 'limit' (optional)
                - price: Limit price (optional)

        Returns:
            Order result dictionary

        Raises:
            RuntimeError: If not connected
            ValueError: If order validation fails
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            # 1. Translate Croupier format to CCXT format (if needed)
            # Croupier uses LONG/SHORT, CCXT uses buy/sell
            if order.get("side") in ["LONG", "SHORT"]:
                order = order.copy()  # Don't modify original
                order["side"] = "buy" if order["side"] == "LONG" else "sell"

            # 2. Validate order
            if not self._validate_order(order):
                return {
                    "status": "rejected",
                    "reason": "validation_failed",
                    "order": order,
                }

            # 2. Calculate TP/SL prices if configured (business logic stays in adapter)
            tp_price = None
            sl_price = None

            if "take_profit" in order and order["take_profit"]:
                # Get current price for calculation
                ticker = await self.connector.fetch_ticker(order.get("symbol", self.symbol))
                current_price = ticker.get("last")

                if current_price:
                    tp_multiplier = float(order["take_profit"])
                    sl_multiplier = float(order["stop_loss"])

                    # Calculate absolute prices
                    tp_price = current_price * tp_multiplier
                    sl_price = current_price * sl_multiplier

            # 3. Execute via connector (exchange-specific TP/SL implementation)
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
                self.logger.error(
                    "❌ El conector devolvió un resultado inválido para la orden: %s",
                    result,
                )
                raise ValueError("Connector returned invalid order result")

            # 4. Update internal state
            self._update_after_order(result)

            self.logger.info(f"✅ Orden ejecutada | {result['symbol']} {result['side'].upper()} {result['amount']}")

            return result

        except Exception as e:
            self.logger.error(f"❌ Error ejecutando orden: {e}")
            raise

    def execute_order_sync(self, order: Dict) -> Dict:
        """
        Synchronous wrapper for execute_order.

        This method is used by Croupier which operates synchronously.
        It translates from Croupier format to CCXT format and executes the order.

        Croupier format:
            - side: "LONG" or "SHORT"
            - size: fraction of equity (e.g., 0.0025 = 0.25%)
            - leverage: multiplier (e.g., 10)

        CCXT format:
            - side: "buy" or "sell"
            - amount: base currency amount (e.g., 0.001 BTC)
            - params: {"leverage": 10}

        Args:
            order: Order dictionary in Croupier format

        Returns:
            Order result dictionary
        """
        import asyncio

        import nest_asyncio

        # Allow nested event loops
        nest_asyncio.apply()

        # Get or create event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task and wait for it
            # Translate and execute in one async call
            task = loop.create_task(self._translate_and_execute(order))
            # Use asyncio.wait to get the result synchronously
            done, pending = loop.run_until_complete(asyncio.wait([task]))
            return list(done)[0].result()
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(self._translate_and_execute(order))

    async def _translate_and_execute(self, order: Dict) -> Dict:
        """
        Translate Croupier order to CCXT format and execute.

        This is async so we can fetch the current price for amount calculation.

        Args:
            order: Order in Croupier format

        Returns:
            Order result
        """
        # Translate Croupier format to CCXT format (async to get current price)
        ccxt_order = await self._translate_croupier_to_ccxt_async(order)

        # Execute the order
        return await self.execute_order(ccxt_order)

    async def _translate_croupier_to_ccxt_async(self, order: Dict) -> Dict:
        """
        Translate order from Croupier format to CCXT format (async version).

        Args:
            order: Order in Croupier format with:
                - amount: base currency amount (already calculated by BuildOrderStage)
                - leverage: multiplier (e.g., 10)
                - side: "LONG" or "SHORT"

        Returns:
            Order in CCXT format with:
                - amount: base currency amount (e.g., 0.3 ETH)
                - side: "buy" or "sell"
        """
        # Translate side: LONG/SHORT → buy/sell
        side = order["side"].lower()
        if side == "long":
            side = "buy"
        elif side == "short":
            side = "sell"

        # Use amount directly from order (already calculated)
        amount = float(order["amount"])
        leverage = order.get("leverage", 1)
        symbol = order["symbol"]

        self.logger.info(f"📊 Order translation | " f"Amount: {amount:.4f} | " f"Leverage: {leverage}x")

        # Build CCXT order
        ccxt_order = {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": order.get("type", "market"),
            "take_profit": order.get("take_profit"),
            "stop_loss": order.get("stop_loss"),
            "trade_id": order.get("trade_id"),
            "params": {
                "leverage": leverage,
            },
        }

        return ccxt_order

    # =========================================================
    # 💰 BALANCE & POSITIONS
    # =========================================================

    def get_balance(self) -> float:
        """
        Get current balance.

        Returns:
            Current balance in account currency
        """
        return self.balance_manager.get_balance()

    async def refresh_balance(self) -> float:
        """
        Refresh balance from exchange.

        Returns:
            Updated balance

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            balance_data = await self.connector.fetch_balance()
            self._update_balance(balance_data)
            return self.get_balance()
        except Exception as e:
            self.logger.error(f"❌ Error refreshing balance: {e}")
            raise

    def get_balance_safe(self) -> float:
        """
        Obtiene balance con fallback inteligente.

        CRÍTICO: Este método NUNCA falla. Usa cache/fallback si el exchange no responde.

        Estrategia:
        1. Cache fresco (< 30s)
        2. Balance calculado (si existe)
        3. Cache stale (< 5min)
        4. Último conocido (< 5min)
        5. Error crítico

        Returns:
            Balance actual o fallback

        Raises:
            RuntimeError: Solo si NO hay balance disponible (muy raro)
        """
        try:
            snapshot = self.balance_cache.get_balance_safe()

            # Advertir si está usando fallback
            if snapshot.is_stale:
                self.logger.warning(
                    f"⚠️ Using stale balance | "
                    f"Source: {snapshot.source.value} | "
                    f"Age: {snapshot.staleness_seconds:.1f}s"
                )

            return snapshot.balance

        except RuntimeError as e:
            # Sin balance disponible - error crítico
            self.logger.error(f"❌ CRITICAL: No balance available: {e}")
            raise

    async def get_positions(self) -> list:
        """
        Get open positions from exchange.

        Returns:
            List of position dictionaries

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            positions = await self.connector.fetch_positions()
            return positions
        except Exception as e:
            self.logger.error(f"❌ Error fetching positions: {e}")
            raise

    async def close_all_positions(self) -> list:
        """Fuerza el cierre de posiciones abiertas usando el último precio conocido."""

        if not hasattr(self, "position_tracker") or self.position_tracker is None:
            return []

        current_candle = self._last_candle or {}
        if not current_candle:
            # Fallback mínimo con el último balance conocido
            snapshot = self.balance_manager.get_state() if hasattr(self.balance_manager, "get_state") else {}
            current_price = snapshot.get("last_price") if isinstance(snapshot, dict) else None
            current_candle = {
                "close": current_price or 0.0,
                "timestamp": snapshot.get("timestamp") if isinstance(snapshot, dict) else None,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
            }

        results = self.position_tracker.force_close_all_positions(current_candle)

        for result in results:
            self.logger.info(
                "🔒 FORCE CLOSE (mesa) | %s %s | Exit: %s | P&L: %.6f",
                result.get("symbol"),
                result.get("side"),
                result.get("trigger_price"),
                float(result.get("pnl", 0.0)),
            )

        return results

    # =========================================================
    # 🔐 PRIVATE METHODS
    # =========================================================

    def _validate_order(self, order: Dict) -> bool:
        """
        Validate order before execution.

        Args:
            order: Order dictionary

        Returns:
            True if valid, False otherwise
        """
        # Basic validation
        if "side" not in order or "amount" not in order:
            self.logger.error("❌ Orden inválida: falta 'side' o 'amount'")
            return False

        # Validate side
        if order["side"] not in ["buy", "sell"]:
            self.logger.error(f"❌ Orden inválida: side '{order['side']}' no válido")
            return False

        # Validate amount
        if order["amount"] <= 0:
            self.logger.error(f"❌ Orden inválida: amount {order['amount']} <= 0")
            return False

        # Validate balance (for buy orders)
        if order["side"] == "buy":
            # Estimate cost (for market orders, use last price as estimate)
            estimated_cost = order["amount"]
            if order.get("price"):
                estimated_cost = order["amount"] * order["price"]
            elif self._last_candle:
                estimated_cost = order["amount"] * self._last_candle["close"]

            if estimated_cost > self.get_balance():
                self.logger.error(
                    f"❌ Orden inválida: balance insuficiente "
                    f"(necesario: {estimated_cost}, disponible: {self.get_balance()})"
                )
                return False

        return True

    def _update_balance(self, balance_data: Dict) -> None:
        """
        Update internal balance from exchange data.

        NUEVO: Usa BalanceCache para almacenar y proveer fallback.
        """
        try:
            # Actualizar cache con datos del exchange
            snapshot = self.balance_cache.update_from_exchange(balance_data)

            # Actualizar balance_manager con valor del cache
            self.balance_manager.set_balance(snapshot.balance)

            self.logger.info(
                f"💰 Balance actualizado: {snapshot.balance:.4f} {snapshot.currency} | "
                f"Source: {snapshot.source.value}"
            )

            self._last_balance_snapshot = {
                "balance": snapshot.balance,
                "currency": snapshot.currency,
                "source": snapshot.source.value,
                "timestamp": snapshot.timestamp,
                "raw": balance_data,
            }

        except ValueError as e:
            self.logger.error(f"❌ Error updating balance: {e}")
            # No actualizar balance_manager si falla la extracción

    def get_balance_sync(self) -> Optional[Dict[str, Any]]:
        """Return último snapshot de balance sin operaciones async."""

        return self._last_balance_snapshot

    def _update_after_order(self, order_result: Dict) -> None:
        """
        Update internal state after order execution.

        Args:
            order_result: Order result from connector
        """
        # Update balance based on order cost
        if not isinstance(order_result, dict):
            self.logger.warning("⚠️ No se actualizó balance: resultado de orden inválido (%s)", order_result)
            return

        if order_result.get("status") == "closed":
            raw_cost = order_result.get("cost")
            try:
                cost = float(raw_cost) if raw_cost is not None else 0.0
            except (TypeError, ValueError):
                cost = 0.0

            fee_info = order_result.get("fee") or {}
            fee = 0.0
            if isinstance(fee_info, dict):
                try:
                    fee = float(fee_info.get("cost") or 0.0)
                except (TypeError, ValueError):
                    fee = 0.0
            else:
                try:
                    fee = float(fee_info)
                except (TypeError, ValueError):
                    fee = 0.0

            side = (order_result.get("side") or "").lower()
            if side == "buy":
                # Deduct cost + fee from balance
                self.balance_manager.update_balance(-(cost + fee))
            elif side == "sell":
                # Add proceeds - fee to balance
                self.balance_manager.update_balance(cost - fee)
            else:
                self.logger.debug("⚠️ Resultado de orden sin side reconocible: %s", order_result)

            self.logger.info("💰 Balance actualizado después de orden | Costo: %.6f | Fee: %.6f", cost, fee)

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
