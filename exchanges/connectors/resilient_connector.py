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
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.trading.clock import MasterClock

from ..resilience import ConnectionManager, SessionState, StateRecovery
from ..resilience.error_classifier import ErrorClassifier
from ..resilience.order_tracker import OrderTracker
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
        self._ready = False
        self._session_id: Optional[str] = None
        self._session_state: Optional[SessionState] = None

        # Order Tracking (CRÍTICO)
        self._order_tracker = OrderTracker(max_tracked_orders=1000)

        # Error Classification (CRÍTICO)
        self._error_classifier = ErrorClassifier()

        # Auto-save task
        self._auto_save_task: Optional[asyncio.Task] = None

        # WS health loop
        cfg = connection_config or {}
        self._ws_health_task: Optional[asyncio.Task] = None
        self._ws_backoff_base: float = float(cfg.get("ws_backoff_base", 2.0))
        self._ws_backoff_max: float = float(cfg.get("ws_backoff_max", 60.0))

        # Master Clock (Clock-Driven Architecture)
        self._clock: Optional[MasterClock] = None
        self._clock_enabled: bool = bool(cfg.get("clock_enabled", True))
        self._clock_tick: float = float(cfg.get("clock_base_tick", 1.0))
        self._clock_job_cfg: Dict[str, Any] = dict(cfg.get("clock_jobs", {}))

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
            self._ready = True  # Mark as ready after successful connection
            self.logger.info("✅ Conectado al exchange")

            # Start auto-save
            if self._state_recovery:
                self._start_auto_save()

            # Start WS maintenance via MasterClock when enabled, otherwise fallback to ws_health
            if hasattr(self._connector, "ensure_websocket") and getattr(self._connector, "enable_websocket", False):
                if self._clock_enabled:
                    # Signal connector to avoid starting its own OCO loop
                    try:
                        setattr(self._connector, "_use_clock", True)
                    except Exception:
                        pass
                    await self._start_clock()
                else:
                    self._start_ws_health()

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

        # Stop WS health loop
        if self._ws_health_task:
            self._ws_health_task.cancel()
            try:
                await self._ws_health_task
            except asyncio.CancelledError:
                pass

        # Stop Master Clock
        if self._clock is not None:
            try:
                await self._clock.stop()
            except Exception:
                pass

        # Save final state
        if self._state_recovery and self._session_state:
            await self._state_recovery.save_state(self._session_state)
            self.logger.info("💾 Estado final guardado")

        # Close underlying connector
        await self._connector.close()
        await asyncio.sleep(0.2)
        self._connected = False
        self._ready = False
        self.logger.info("✅ Conexión cerrada")

    # =========================================================
    # 📊 MARKET DATA (Delegación con resiliencia)
    # =========================================================

    async def _execute_with_smart_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """
        Ejecuta función con retry inteligente basado en clasificación de errores.

        CRÍTICO: Usa ErrorClassifier para determinar si el error es retriable.

        Args:
            func: Función a ejecutar
            max_retries: Máximo de intentos
            *args, **kwargs: Argumentos para la función

        Returns:
            Resultado de la función

        Raises:
            Exception: Si falla después de todos los intentos o error no retriable
        """
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                # Clasificar error
                classification = self._error_classifier.classify(e)

                # Si NO es retriable, fallar inmediatamente
                if not classification.is_retriable:
                    self.logger.error(
                        f"❌ Error NO retriable | "
                        f"Category: {classification.category.value} | "
                        f"Action: {classification.suggested_action.value} | "
                        f"{classification.message}"
                    )
                    raise

                # Si es retriable pero es el último intento, fallar
                if attempt >= max_retries - 1:
                    self.logger.error(
                        f"❌ Error retriable pero max retries alcanzado | "
                        f"Category: {classification.category.value} | "
                        f"{classification.message}"
                    )
                    raise

                # Retry con delay inteligente
                delay = classification.retry_delay or (2**attempt)
                self.logger.warning(
                    f"⚠️ Error retriable (intento {attempt + 1}/{max_retries}) | "
                    f"Category: {classification.category.value} | "
                    f"Retry in {delay:.1f}s | "
                    f"{classification.message}"
                )
                await asyncio.sleep(delay)

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> list:
        """
        Fetch OHLCV con retry inteligente.

        Usa ErrorClassifier para determinar si reintentar.
        """
        return await self._execute_with_smart_retry(self._connector.fetch_ohlcv, symbol, timeframe, limit)

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker con retry inteligente."""
        return await self._execute_with_smart_retry(self._connector.fetch_ticker, symbol)

    async def fetch_order_book(self, symbol: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Fetch order book con retry inteligente."""
        return await self._execute_with_smart_retry(self._connector.fetch_order_book, symbol, limit)

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

        CRÍTICO: Trackea la orden ANTES de enviarla al exchange.
        Esto garantiza que no perdemos órdenes si la API falla.

        Flow:
        1. Generar client_order_id único
        2. START tracking (estado: PENDING)
        3. Enviar al exchange
        4. UPDATE tracking con exchange_order_id (estado: SUBMITTED)
        5. Si falla, marcar como FAILED pero mantener tracking
        """
        # 1. Generar client_order_id único
        client_order_id = self._generate_client_order_id()

        # 2. START tracking ANTES de enviar
        self._order_tracker.start_tracking(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            amount=amount,
            order_type=order_type,
            price=price,
            params=params,
        )

        try:
            # 3. Enviar al exchange
            order_result = await self._connector.create_order(symbol, side, amount, price, order_type, params)

            # 4. UPDATE tracking con resultado del exchange
            exchange_order_id = order_result.get("id")
            if exchange_order_id:
                self._order_tracker.update_order_submitted(client_order_id, exchange_order_id)
            else:
                self.logger.warning(f"⚠️ Order created but no exchange_order_id: {order_result}")

            # Agregar client_order_id al resultado para referencia
            order_result["client_order_id"] = client_order_id

            # Update session state
            if self._session_state:
                self._session_state.add_order(order_result)

            return order_result

        except Exception as e:
            # 5. Si falla, marcar como FAILED pero mantener tracking
            self._order_tracker.update_order_failed(client_order_id, str(e))
            self.logger.error(f"❌ create_order falló | {client_order_id} | {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Cancela orden con tracking.

        Args:
            order_id: Puede ser client_order_id o exchange_order_id
            symbol: Par de trading
            params: Parámetros adicionales
        """
        try:
            result = await self._connector.cancel_order(order_id, symbol, params)

            # Actualizar tracking si es client_order_id
            tracked_order = self._order_tracker.get_order(order_id)
            if tracked_order:
                self._order_tracker.update_from_exchange(order_id, {"status": "cancelled"})

            return result

        except Exception as e:
            self.logger.error(f"❌ cancel_order falló | {order_id} | {e}")
            raise

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

    async def fetch_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Fetch open orders (delegación simple)."""
        return await self._connector.fetch_open_orders(symbol)

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch order status (delegación simple)."""
        return await self._connector.fetch_order(order_id, symbol)

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

        # Note: Auto-save happens in background loop, not here

    # =========================================================
    # 📊 ORDER TRACKING UTILITIES
    # =========================================================

    def _generate_client_order_id(self) -> str:
        """
        Genera client_order_id único.

        Formato: CASINO_{timestamp}_{uuid}
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        unique_id = str(uuid.uuid4())[:8]
        return f"CASINO_{timestamp}_{unique_id}"

    def get_order_tracker(self) -> OrderTracker:
        """Obtiene el OrderTracker (para debugging/monitoring)."""
        return self._order_tracker

    def get_tracked_order(self, client_order_id: str):
        """Obtiene orden trackeada por client_order_id."""
        return self._order_tracker.get_order(client_order_id)

    def get_all_in_flight_orders(self):
        """Obtiene todas las órdenes en vuelo."""
        return self._order_tracker.get_all_in_flight()

    def get_order_tracker_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del order tracker."""
        return self._order_tracker.get_metrics()

    def get_error_classifier_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del error classifier."""
        return self._error_classifier.get_metrics()

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

    def _start_ws_health(self):
        """Inicia loop de salud del WebSocket con backoff exponencial."""
        if self._ws_health_task is None or self._ws_health_task.done():
            self._ws_health_task = asyncio.create_task(self._ws_health_loop())
            self.logger.info("🔄 WS health loop iniciado")

    async def _auto_save_loop(self):
        """Loop de auto-guardado."""
        interval = self._state_recovery.auto_save_interval if self._state_recovery else 60.0

        while self._connected:
            await asyncio.sleep(interval)

            try:
                await self.save_state()
            except Exception as e:
                self.logger.error(f"❌ Error en auto-guardado: {e}")

    async def _ws_health_loop(self):
        """Loop que garantiza que el WebSocket se mantenga conectado con 'let it crash'."""
        backoff = self._ws_backoff_base
        while self._connected:
            try:
                await asyncio.sleep(0)  # yield
                await self._connector.ensure_websocket()
                # Healthy, reset backoff and sleep a bit antes de próximo check
                backoff = self._ws_backoff_base
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Fail fast up from connector, aquí decidimos reintentar con backoff
                self.logger.warning(f"⚠️ WS ensure falló (reintento en {backoff:.1f}s): {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, self._ws_backoff_max)

    async def _start_clock(self):
        """Start MasterClock and register core maintenance jobs."""
        if self._clock is None:
            self._clock = MasterClock(base_tick=self._clock_tick, logger=logging.getLogger("MasterClock"))

            async def ws_ensure_job():
                try:
                    await self._connector.ensure_websocket()
                except Exception as e:
                    # Let it crash upwards to the clock; already handled/logged there
                    raise e

            async def oco_monitor_job():
                if hasattr(self._connector, "oco_monitor_tick"):
                    try:
                        await self._connector.oco_monitor_tick()
                    except Exception as e:
                        raise e

            # Register jobs with configurable intervals/timeouts
            ws_interval = float(self._clock_job_cfg.get("ws_ensure_interval", 5.0))
            ws_timeout = float(self._clock_job_cfg.get("ws_ensure_timeout", 0.8))
            oco_interval = float(self._clock_job_cfg.get("oco_interval", 2.0))
            oco_timeout = float(self._clock_job_cfg.get("oco_timeout", 0.8))

            self._clock.register_job("ws_ensure", ws_ensure_job, interval=ws_interval, timeout=ws_timeout)
            self._clock.register_job("oco_monitor", oco_monitor_job, interval=oco_interval, timeout=oco_timeout)

        await self._clock.start()
        self.logger.info("🕒 MasterClock started with ws_ensure and oco_monitor jobs")

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
