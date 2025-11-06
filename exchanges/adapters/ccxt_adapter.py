"""
CCXTAdapter - Adaptador CCXT para Mesas (DataSource).

Este adaptador envuelve la lógica de negocio del trading y delega
la comunicación con exchanges a conectores modulares específicos.

Arquitectura (v1.9.2):
    Mesa (DataSource) → CCXTAdapter (Adaptador) → Conector (Driver) → CCXT → Exchange

    Ejemplo:
    LiveDataSource → CCXTAdapter → KrakenConnector → CCXT → Kraken API

Responsabilidades del Adaptador (CCXTAdapter):
    - Gestión de balance (BalanceManager)
    - Tracking de posiciones (PositionTracker)
    - Validación de órdenes
    - Lógica de TP/SL
    - Logging y auditoría
    - Sincronización de estado real (ExchangeStateSync)

Responsabilidades del Conector (KrakenConnector, etc.):
    - Comunicación con el exchange (REST + WebSocket)
    - Normalización de datos
    - Manejo de errores específicos del exchange
    - Rate limiting

Usage:
    ```python
    from tables.connectors import KrakenConnector
    from tables.ccxt_adapter import CCXTAdapter

    # Create connector (driver específico)
    connector = KrakenConnector(testnet=True)

    # Create adapter (lógica de negocio)
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

        # Components (business logic)
        self.balance_manager = BalanceManager(starting_balance=starting_balance)
        self.position_tracker = PositionTracker()

        # NUEVO: Sincronizador de estado real
        self.state_sync = ExchangeStateSync(connector)

        # State
        self._connected = False
        self._last_candle: Optional[Dict] = None
        self._last_balance_snapshot: Optional[Dict[str, Any]] = None
        self._last_sync_time = 0
        self.exchange = None
        self.base_currency = getattr(connector, "base_currency", "USD")

        self.logger.info(f"🪙 CCXTAdapter inicializada | Exchange: {connector.exchange_name} | Symbol: {symbol}")

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
            while not self.connector.ready and waited < max_wait:
                self.logger.info(f"⏳ Esperando que conector esté listo... ({waited}s)")
                await asyncio.sleep(1)
                waited += 1

            if not self.connector.ready:
                raise RuntimeError(f"Connector not ready after {max_wait}s. " f"Status: {self.connector.status_dict}")

            self.logger.info(f"✅ Connector ready | Status: {self.connector.status_dict}")

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

                # 3. NUEVO: Procesar fills confirmados
                for fill in recent_fills:
                    # TODO: Implementar lógica para detectar si fill es cierre
                    # Por ahora, solo loggeamos
                    self.logger.debug(
                        f"📊 Fill confirmado: {fill.symbol} {fill.side} "
                        f"@ {fill.price:.2f} | Amount: {fill.amount:.4f}"
                    )

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
            # 1. Validate order
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
        """Update internal balance from exchange data."""

        target_currency = balance_data.get("currency") or self.base_currency
        free_section = balance_data.get("free", {}) or {}

        balance_value = 0.0
        currency_used = target_currency

        if isinstance(free_section, dict) and free_section:
            if target_currency in free_section and free_section[target_currency]:
                balance_value = float(free_section[target_currency])
            else:
                for candidate in ("USD", "USDT", "USDC", "EUR"):
                    if candidate in free_section and free_section[candidate]:
                        balance_value = float(free_section[candidate])
                        currency_used = candidate
                        break
                else:
                    try:
                        candidate_currency, candidate_value = next(
                            (curr, value) for curr, value in free_section.items() if value
                        )
                        balance_value = float(candidate_value)
                        currency_used = candidate_currency
                    except StopIteration:
                        balance_value = 0.0

        if balance_value > 0:
            self.balance_manager.set_balance(balance_value)
            self.logger.info("💰 Balance actualizado: %.4f %s", balance_value, currency_used)
        else:
            self.logger.warning("⚠️ Balance no disponible o cero. Datos: %s", balance_data)

        self._last_balance_snapshot = {
            "balance": balance_value,
            "currency": currency_used,
            "free": free_section,
            "raw": balance_data,
        }

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
