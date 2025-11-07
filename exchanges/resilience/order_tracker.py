"""
Order Tracker - Casino V2

Sistema de tracking de órdenes inspirado en Hummingbot.
Trackea órdenes ANTES de enviarlas al exchange para evitar pérdidas.

Características:
- Tracking antes de enviar (fail-safe)
- Estados de orden (pending, submitted, filled, cancelled, failed)
- Detección de órdenes perdidas
- Reconciliación con exchange
- Métricas y auditoría

Author: Casino V2 Team
Version: 2.0.0
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OrderStatus(Enum):
    """Estados de una orden en el tracker."""

    PENDING = "pending"  # Creada localmente, no enviada
    SUBMITTED = "submitted"  # Enviada al exchange
    PARTIALLY_FILLED = "partially_filled"  # Parcialmente ejecutada
    FILLED = "filled"  # Completamente ejecutada
    CANCELLED = "cancelled"  # Cancelada
    FAILED = "failed"  # Falló al enviar
    UNKNOWN = "unknown"  # Estado desconocido (requiere verificación)


@dataclass
class TrackedOrder:
    """
    Orden trackeada con toda su información.

    Inspirado en Hummingbot's InFlightOrder.
    """

    # Identificadores
    client_order_id: str  # ID local (generado por nosotros)
    exchange_order_id: Optional[str] = None  # ID del exchange (cuando se confirma)

    # Parámetros de la orden
    symbol: str = ""
    side: str = ""  # "buy" | "sell"
    order_type: str = "market"  # "market" | "limit"
    amount: float = 0.0
    price: Optional[float] = None
    params: Dict[str, Any] = field(default_factory=dict)

    # Estado
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    remaining_amount: float = 0.0
    average_price: float = 0.0

    # Timestamps
    created_at: float = field(default_factory=time.time)
    submitted_at: Optional[float] = None
    filled_at: Optional[float] = None
    updated_at: float = field(default_factory=time.time)

    # Metadata
    error: Optional[str] = None
    last_update_source: str = "local"  # "local" | "exchange" | "websocket"

    def update_from_exchange(self, exchange_data: Dict[str, Any]) -> None:
        """
        Actualiza orden con datos del exchange.

        Args:
            exchange_data: Respuesta del exchange (formato CCXT)
        """
        self.exchange_order_id = exchange_data.get("id") or self.exchange_order_id
        self.status = self._parse_status(exchange_data.get("status", "unknown"))
        self.filled_amount = float(exchange_data.get("filled", 0))
        self.remaining_amount = float(exchange_data.get("remaining", self.amount))
        self.average_price = float(exchange_data.get("average", 0))
        self.updated_at = time.time()
        self.last_update_source = "exchange"

    def mark_submitted(self, exchange_order_id: str) -> None:
        """Marca orden como enviada al exchange."""
        self.exchange_order_id = exchange_order_id
        self.status = OrderStatus.SUBMITTED
        self.submitted_at = time.time()
        self.updated_at = time.time()

    def mark_failed(self, error: str) -> None:
        """Marca orden como fallida."""
        self.status = OrderStatus.FAILED
        self.error = error
        self.updated_at = time.time()

    def is_done(self) -> bool:
        """Verifica si la orden está completada (filled o cancelled)."""
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED)

    def is_pending_verification(self) -> bool:
        """Verifica si la orden necesita verificación con el exchange."""
        # Si está en estado UNKNOWN o lleva mucho tiempo en PENDING
        if self.status == OrderStatus.UNKNOWN:
            return True
        if self.status == OrderStatus.PENDING and time.time() - self.created_at > 30:
            return True
        return False

    @staticmethod
    def _parse_status(status_str: str) -> OrderStatus:
        """Parsea status del exchange a OrderStatus."""
        status_map = {
            "open": OrderStatus.SUBMITTED,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
            "expired": OrderStatus.CANCELLED,
            "rejected": OrderStatus.FAILED,
        }
        return status_map.get(status_str.lower(), OrderStatus.UNKNOWN)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a dict para logging/storage."""
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "amount": self.amount,
            "price": self.price,
            "status": self.status.value,
            "filled_amount": self.filled_amount,
            "remaining_amount": self.remaining_amount,
            "average_price": self.average_price,
            "created_at": self.created_at,
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }


class OrderTracker:
    """
    Tracker de órdenes en vuelo.

    Inspirado en Hummingbot's OrderTracker.

    Responsabilidades:
    - Trackear órdenes ANTES de enviarlas
    - Mantener estado de órdenes en vuelo
    - Detectar órdenes perdidas
    - Reconciliar con exchange
    - Proveer métricas
    """

    def __init__(self, max_tracked_orders: int = 1000):
        """
        Initialize OrderTracker.

        Args:
            max_tracked_orders: Máximo de órdenes a mantener en memoria
        """
        self.logger = logging.getLogger("OrderTracker")

        # Órdenes en vuelo (no completadas)
        self._in_flight_orders: Dict[str, TrackedOrder] = {}

        # Órdenes completadas (para auditoría)
        self._completed_orders: List[TrackedOrder] = []

        # Configuración
        self._max_tracked_orders = max_tracked_orders

        # Métricas
        self._total_orders_tracked = 0
        self._total_orders_filled = 0
        self._total_orders_failed = 0
        self._total_orders_cancelled = 0

        self.logger.info("✅ OrderTracker initialized")

    def start_tracking(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> TrackedOrder:
        """
        Inicia tracking de una orden ANTES de enviarla.

        CRÍTICO: Esto debe llamarse ANTES de enviar la orden al exchange.

        Args:
            client_order_id: ID único generado localmente
            symbol: Par de trading
            side: "buy" o "sell"
            amount: Cantidad
            order_type: Tipo de orden
            price: Precio (para limit orders)
            params: Parámetros adicionales

        Returns:
            TrackedOrder creada
        """
        order = TrackedOrder(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            params=params or {},
            status=OrderStatus.PENDING,
        )

        self._in_flight_orders[client_order_id] = order
        self._total_orders_tracked += 1

        self.logger.info(
            f"📝 Tracking started | Order: {client_order_id} | "
            f"{side.upper()} {amount} {symbol} @ {price or 'MARKET'}"
        )

        return order

    def update_order_submitted(self, client_order_id: str, exchange_order_id: str) -> bool:
        """
        Actualiza orden cuando se confirma envío al exchange.

        Args:
            client_order_id: ID local
            exchange_order_id: ID del exchange

        Returns:
            True si se actualizó correctamente
        """
        order = self._in_flight_orders.get(client_order_id)
        if not order:
            self.logger.warning(f"⚠️ Order {client_order_id} not found in tracker")
            return False

        order.mark_submitted(exchange_order_id)
        self.logger.info(f"✅ Order submitted | Local: {client_order_id} | Exchange: {exchange_order_id}")

        return True

    def update_order_failed(self, client_order_id: str, error: str) -> bool:
        """
        Marca orden como fallida.

        Args:
            client_order_id: ID local
            error: Mensaje de error

        Returns:
            True si se actualizó correctamente
        """
        order = self._in_flight_orders.get(client_order_id)
        if not order:
            self.logger.warning(f"⚠️ Order {client_order_id} not found in tracker")
            return False

        order.mark_failed(error)
        self._total_orders_failed += 1
        self.logger.error(f"❌ Order failed | {client_order_id} | Error: {error}")

        # Mover a completadas
        self._move_to_completed(client_order_id)

        return True

    def update_from_exchange(self, client_order_id: str, exchange_data: Dict[str, Any]) -> bool:
        """
        Actualiza orden con datos del exchange.

        Args:
            client_order_id: ID local
            exchange_data: Respuesta del exchange

        Returns:
            True si se actualizó correctamente
        """
        order = self._in_flight_orders.get(client_order_id)
        if not order:
            self.logger.warning(f"⚠️ Order {client_order_id} not found in tracker")
            return False

        old_status = order.status
        order.update_from_exchange(exchange_data)

        # Log si cambió el estado
        if order.status != old_status:
            self.logger.info(
                f"📊 Order status changed | {client_order_id} | " f"{old_status.value} → {order.status.value}"
            )

        # Si está completada, mover a completadas
        if order.is_done():
            if order.status == OrderStatus.FILLED:
                self._total_orders_filled += 1
            elif order.status == OrderStatus.CANCELLED:
                self._total_orders_cancelled += 1

            self._move_to_completed(client_order_id)

        return True

    def get_order(self, client_order_id: str) -> Optional[TrackedOrder]:
        """Obtiene orden trackeada."""
        return self._in_flight_orders.get(client_order_id)

    def get_all_in_flight(self) -> List[TrackedOrder]:
        """Obtiene todas las órdenes en vuelo."""
        return list(self._in_flight_orders.values())

    def get_pending_verification(self) -> List[TrackedOrder]:
        """Obtiene órdenes que necesitan verificación."""
        return [order for order in self._in_flight_orders.values() if order.is_pending_verification()]

    def stop_tracking(self, client_order_id: str) -> bool:
        """
        Detiene tracking de una orden.

        Args:
            client_order_id: ID local

        Returns:
            True si se detuvo correctamente
        """
        if client_order_id in self._in_flight_orders:
            order = self._in_flight_orders[client_order_id]
            self._move_to_completed(client_order_id)
            self.logger.info(f"🛑 Tracking stopped | {client_order_id} | Final status: {order.status.value}")
            return True
        return False

    def _move_to_completed(self, client_order_id: str) -> None:
        """Mueve orden de in_flight a completed."""
        order = self._in_flight_orders.pop(client_order_id, None)
        if order:
            self._completed_orders.append(order)

            # Limitar tamaño de completed
            if len(self._completed_orders) > self._max_tracked_orders:
                self._completed_orders = self._completed_orders[-self._max_tracked_orders :]

    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del tracker."""
        return {
            "in_flight_orders": len(self._in_flight_orders),
            "completed_orders": len(self._completed_orders),
            "total_tracked": self._total_orders_tracked,
            "total_filled": self._total_orders_filled,
            "total_failed": self._total_orders_failed,
            "total_cancelled": self._total_orders_cancelled,
            "fill_rate": (
                self._total_orders_filled / self._total_orders_tracked if self._total_orders_tracked > 0 else 0
            ),
            "pending_verification": len(self.get_pending_verification()),
        }

    def clear_completed(self) -> int:
        """Limpia órdenes completadas."""
        count = len(self._completed_orders)
        self._completed_orders.clear()
        self.logger.info(f"🧹 Cleared {count} completed orders")
        return count
