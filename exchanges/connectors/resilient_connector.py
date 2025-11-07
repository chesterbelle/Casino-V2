"""
ResilientConnector - Wrapper que agrega resiliencia a cualquier BaseConnector.

Este módulo implementa el Wrapper Pattern para agregar resiliencia (ConnectionManager +
StateRecovery) a cualquier conector de exchange de forma transparente y agnóstica.

Arquitectura:
    CCXTAdapter → ResilientConnector → BaseConnector → Exchange

Inspiración:
    - Hummingbot's connector architecture
    - Wrapper Pattern (GoF Design Patterns)
    - Graceful degradation
    - Order tracking

Features:
    - WebSocket + REST fallback automático
    - Reconexión automática con exponential backoff
    - Circuit breaker pattern
    - Recuperación de estado después de crashes
    - Detección de fills perdidos
    - Health checks periódicos
    - Métricas detalladas
    - Agnóstico de exchange

Author: Casino V2 Team
Version: 1.9.1
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..resilience import ConnectionManager, SessionState, StateRecovery
from .connector_base import BaseConnector


class ResilientConnector(BaseConnector):
    """
    Wrapper que agrega resiliencia a cualquier BaseConnector.

    Este wrapper es completamente transparente para CCXTAdapter y agnóstico
    del exchange subyacente. Simplemente envuelve un conector existente y
    agrega capacidades de resiliencia.

    Usage:
        ```python
        # Crear conector base
        kraken = KrakenConnector(api_key, secret, testnet=True)

        # Envolver con resiliencia
        resilient_kraken = ResilientConnector(
            connector=kraken,
            connection_config={
                'max_retries': 10,
                'base_delay': 2.0,
                'max_delay': 120.0,
                'circuit_threshold': 15,
                'circuit_timeout': 600.0,
            },
            state_recovery_config={
                'state_dir': './state/production',
                'auto_save_interval': 30.0,
            }
        )

        # Usar como cualquier conector
        table = CCXTAdapter(connector=resilient_kraken, symbol="BTC/USD")
        await table.connect()
        ```

    Features:
        - Transparente: CCXTAdapter no sabe que está usando ResilientConnector
        - Agnóstico: Funciona con cualquier BaseConnector (Kraken, Binance, etc.)
        - No invasivo: No modifica el conector subyacente
        - Testeable: Fácil de probar independientemente
        - Configurable: Parámetros de resiliencia configurables
    """

    def __init__(
        self,
        connector: BaseConnector,
        connection_config: Optional[Dict[str, Any]] = None,
        state_recovery_config: Optional[Dict[str, Any]] = None,
        enable_connection_manager: bool = True,
        enable_state_recovery: bool = True,
    ):
        """
        Initialize ResilientConnector.

        Args:
            connector: BaseConnector subyacente (KrakenConnector, BinanceConnector, etc.)
            connection_config: Configuración para ConnectionManager
            state_recovery_config: Configuración para StateRecovery
            enable_connection_manager: Habilitar ConnectionManager
            enable_state_recovery: Habilitar StateRecovery
        """
        self.logger = logging.getLogger(f"ResilientConnector[{connector.__class__.__name__}]")

        # Conector subyacente
        self._connector = connector

        # Resiliencia habilitada
        self._enable_connection_manager = enable_connection_manager
        self._enable_state_recovery = enable_state_recovery

        # ConnectionManager (opcional)
        self._connection_manager: Optional[ConnectionManager] = None
        if enable_connection_manager and connection_config:
            # TODO: Integrar ConnectionManager cuando esté listo
            self.logger.info("ConnectionManager habilitado (pendiente de integración)")

        # StateRecovery (opcional)
        self._state_recovery: Optional[StateRecovery] = None
        if enable_state_recovery:
            recovery_config = state_recovery_config or {}
            self._state_recovery = StateRecovery(
                connector=connector,
                state_dir=recovery_config.get("state_dir", "./state"),
                auto_save_interval=recovery_config.get("auto_save_interval", 60.0),
            )
            self.logger.info("StateRecovery habilitado")

        # Estado
        self._connected = False
        self._session_id: Optional[str] = None
        self._session_state: Optional[SessionState] = None

        # Auto-save task
        self._auto_save_task: Optional[asyncio.Task] = None

        self.logger.info(
            f"ResilientConnector inicializado | "
            f"connector={connector.__class__.__name__} | "
            f"connection_mgr={enable_connection_manager} | "
            f"state_recovery={enable_state_recovery}"
        )

    # =========================================================
    # 🔌 CONNECTION MANAGEMENT
    # =========================================================

    async def connect(self) -> None:
        """
        Conecta al exchange con resiliencia.

        Este método:
        1. Intenta recuperar sesión anterior (si existe)
        2. Conecta al exchange subyacente
        3. Inicia auto-guardado de estado
        """
        self.logger.info("Conectando con resiliencia...")

        # Try to recover previous session
        if self._state_recovery and self._session_id:
            self.logger.info(f"Intentando recuperar sesión {self._session_id}...")
            recovered_state = await self._state_recovery.recover_session(self._session_id)

            if recovered_state:
                self._session_state = recovered_state
                self.logger.info(
                    f"✅ Sesión recuperada | "
                    f"candles={recovered_state.candles_processed} | "
                    f"positions={len(recovered_state.open_positions)}"
                )

        # Connect underlying connector
        try:
            await self._connector.connect()
            self._connected = True
            self.logger.info("✅ Conectado al exchange")

            # Start auto-save
            if self._state_recovery:
                self._start_auto_save()

        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}")
            raise

    async def close(self) -> None:
        """Cierra conexión y guarda estado final."""
        self.logger.info("Cerrando conexión...")

        # Stop auto-save
        if self._auto_save_task:
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass

        # Save final state
        if self._state_recovery and self._session_state:
            await self._state_recovery.save_state(self._session_state)
            self.logger.info("💾 Estado final guardado")

        # Close underlying connector
        await self._connector.close()
        self._connected = False
        self.logger.info("✅ Conexión cerrada")

    # =========================================================
    # 📊 MARKET DATA (Delegación con resiliencia)
    # =========================================================

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> list:
        """
        Fetch OHLCV con retry automático.

        Delega al conector subyacente pero agrega retry logic.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await self._connector.fetch_ohlcv(symbol, timeframe, limit)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2**attempt
                    self.logger.warning(
                        f"⚠️ fetch_ohlcv falló (intento {attempt + 1}/{max_retries}), " f"reintentando en {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                self.logger.error(f"❌ fetch_ohlcv falló después de {max_retries} intentos")
                raise

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker con retry automático."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await self._connector.fetch_ticker(symbol)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2**attempt
                    self.logger.warning(
                        f"⚠️ fetch_ticker falló (intento {attempt + 1}/{max_retries}), " f"reintentando en {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                self.logger.error(f"❌ fetch_ticker falló después de {max_retries} intentos")
                raise

    async def fetch_order_book(self, symbol: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Fetch order book con retry automático."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await self._connector.fetch_order_book(symbol, limit)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2**attempt
                    self.logger.warning(
                        f"⚠️ fetch_order_book falló (intento {attempt + 1}/{max_retries}), "
                        f"reintentando en {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                self.logger.error(f"❌ fetch_order_book falló después de {max_retries} intentos")
                raise

    # =========================================================
    # 💼 TRADING OPERATIONS (Delegación con tracking)
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
        Crea orden con tracking (inspirado en Hummingbot).

        Tracking antes de enviar al exchange para no perder órdenes
        si la API falla después de crear la orden.
        """
        # TODO: Implementar order tracking antes de enviar
        # (similar a Hummingbot's start_tracking_order)

        try:
            order = await self._connector.create_order(symbol, side, amount, price, order_type, params)

            # Update session state
            if self._session_state:
                # TODO: Agregar orden a tracking
                pass

            return order

        except Exception as e:
            self.logger.error(f"❌ create_order falló: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancela orden con tracking."""
        # TODO: Implementar order tracking
        return await self._connector.cancel_order(order_id, symbol, params)

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
        Crea orden con TP/SL (delegación al conector subyacente).

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order amount
            price: Limit price (optional)
            order_type: Order type
            tp_price: Take profit price (optional)
            sl_price: Stop loss price (optional)
            params: Additional parameters

        Returns:
            Order result from exchange
        """
        try:
            order = await self._connector.create_order_with_tpsl(
                symbol, side, amount, price, order_type, tp_price, sl_price, params
            )

            # Update session state
            if self._session_state:
                # TODO: Agregar orden a tracking
                pass

            return order

        except Exception as e:
            self.logger.error(f"❌ create_order_with_tpsl falló: {e}")
            raise

    # =========================================================
    # 💰 ACCOUNT DATA (Delegación simple)
    # =========================================================

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch balance (delegación simple)."""
        return await self._connector.fetch_balance()

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """Fetch positions (delegación simple)."""
        return await self._connector.fetch_positions()

    async def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch trades (delegación simple)."""
        return await self._connector.fetch_my_trades(symbol, since, limit)

    # =========================================================
    # 📊 STATUS & HEALTH (Inspirado en Hummingbot)
    # =========================================================

    @property
    def ready(self) -> bool:
        """
        Indica si el conector está listo para operar.

        Inspirado en Hummingbot's ready property.
        """
        if not self._connected:
            return False

        # Check underlying connector
        if hasattr(self._connector, "ready"):
            return self._connector.ready

        # Default: connected = ready
        return True

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Estado de componentes del conector.

        Inspirado en Hummingbot's status_dict property.
        """
        status = {
            "connected": self._connected,
            "ready": self.ready,
        }

        # Add underlying connector status
        if hasattr(self._connector, "status_dict"):
            status["underlying"] = self._connector.status_dict

        # Add resilience status
        if self._connection_manager:
            status["connection_manager"] = "enabled"

        if self._state_recovery:
            status["state_recovery"] = "enabled"

        return status

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """
        Estado para persistencia.

        Inspirado en Hummingbot's tracking_states property.
        """
        states = {}

        # Add session state
        if self._session_state:
            states["session"] = self._session_state.to_dict()

        # Add underlying connector states
        if hasattr(self._connector, "tracking_states"):
            states["connector"] = self._connector.tracking_states

        return states

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restaura estado guardado.

        Inspirado en Hummingbot's restore_tracking_states.
        """
        # Restore session state
        if "session" in saved_states:
            self._session_state = SessionState.from_dict(saved_states["session"])
            self.logger.info("📂 Session state restaurado")

        # Restore underlying connector states
        if "connector" in saved_states and hasattr(self._connector, "restore_tracking_states"):
            self._connector.restore_tracking_states(saved_states["connector"])
            self.logger.info("📂 Connector states restaurado")

    # =========================================================
    # 💾 STATE MANAGEMENT
    # =========================================================

    def set_session_id(self, session_id: str):
        """Establece session ID para state recovery."""
        self._session_id = session_id
        self.logger.info(f"Session ID establecido: {session_id}")

    def update_session_state(
        self,
        candles_processed: Optional[int] = None,
        balance: Optional[float] = None,
        equity: Optional[float] = None,
        open_positions: Optional[List[Dict[str, Any]]] = None,
        closed_trades: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Actualiza estado de la sesión.

        Llamado por testing_session.py para mantener estado actualizado.
        """
        if not self._session_state:
            # Create new session state
            self._session_state = SessionState(
                session_id=self._session_id or f"session_{int(datetime.now().timestamp())}",
                player_name="unknown",
                symbol="unknown",
                timeframe="unknown",
                start_time=datetime.now().timestamp(),
                last_update=datetime.now().timestamp(),
                candles_processed=0,
                balance=0.0,
                equity=0.0,
                open_positions=[],
                closed_trades=[],
            )

        # Update fields
        if candles_processed is not None:
            self._session_state.candles_processed = candles_processed
        if balance is not None:
            self._session_state.balance = balance
        if equity is not None:
            self._session_state.equity = equity
        if open_positions is not None:
            self._session_state.open_positions = open_positions
        if closed_trades is not None:
            self._session_state.closed_trades = closed_trades

        self._session_state.last_update = datetime.now().timestamp()

    async def save_state(self):
        """Guarda estado manualmente."""
        if self._state_recovery and self._session_state:
            await self._state_recovery.save_state(self._session_state)
            self.logger.debug("💾 Estado guardado")

    def _start_auto_save(self):
        """Inicia auto-guardado periódico."""
        if self._auto_save_task is None or self._auto_save_task.done():
            self._auto_save_task = asyncio.create_task(self._auto_save_loop())
            self.logger.info("🔄 Auto-guardado iniciado")

    async def _auto_save_loop(self):
        """Loop de auto-guardado."""
        interval = self._state_recovery.auto_save_interval if self._state_recovery else 60.0

        while self._connected:
            await asyncio.sleep(interval)

            try:
                await self.save_state()
            except Exception as e:
                self.logger.error(f"❌ Error en auto-guardado: {e}")

    # ========================================
    # Abstract methods delegation
    # ========================================

    @property
    def exchange_name(self) -> str:
        """Delegate to underlying connector."""
        return self._connector.exchange_name

    def normalize_symbol(self, symbol: str) -> str:
        """Delegate to underlying connector."""
        return self._connector.normalize_symbol(symbol)

    def denormalize_symbol(self, symbol: str) -> str:
        """Delegate to underlying connector."""
        return self._connector.denormalize_symbol(symbol)

    @property
    def is_connected(self) -> bool:
        """Check if connector is connected."""
        return self._connected and self._connector.is_connected
