"""
OCO Order Monitor - Implementación manual de One Cancels the Other

Kraken Futures API no soporta OCO automático, por lo que debemos
implementar la lógica de monitoreo y cancelación manualmente.

Este monitor:
1. Vigila pares de órdenes TP/SL
2. Cuando una se ejecuta, cancela la otra automáticamente
3. Maneja errores de red y API
4. Limpia órdenes completadas

Uso:
    monitor = OCOOrderMonitor(connector)
    await monitor.start()

    # Registrar par de órdenes TP/SL
    monitor.register_oco_pair(
        symbol="BTC/USD",
        tp_order_id="tp_123",
        sl_order_id="sl_456"
    )

    # El monitor se encarga del resto automáticamente
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple


@dataclass
class OCOPair:
    """Par de órdenes OCO (TP/SL)."""

    symbol: str
    tp_order_id: Optional[str]
    sl_order_id: Optional[str]
    created_at: datetime

    def has_both_orders(self) -> bool:
        """Verifica si tiene ambas órdenes."""
        return self.tp_order_id is not None and self.sl_order_id is not None

    def get_order_ids(self) -> Tuple[Optional[str], Optional[str]]:
        """Retorna tupla (tp_id, sl_id)."""
        return (self.tp_order_id, self.sl_order_id)


class OCOOrderMonitor:
    """
    Monitor de órdenes OCO (One Cancels the Other).

    Implementa la lógica OCO manualmente para exchanges que no la soportan
    nativamente (como Kraken Futures).
    """

    def __init__(self, connector, check_interval: float = 2.0):
        """
        Inicializa el monitor.

        Args:
            connector: Conector del exchange (debe tener fetch_order y cancel_order)
            check_interval: Intervalo de verificación en segundos (default: 2s)
        """
        self.connector = connector
        self.check_interval = check_interval
        self.logger = logging.getLogger(__name__)

        # Pares de órdenes OCO activos
        self.oco_pairs: Dict[str, OCOPair] = {}  # key: pair_id

        # Control del monitor
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None

        # Métricas
        self._check_count = 0
        self._pairs_processed = 0
        self._orders_canceled = 0
        self._start_time = None

    def register_oco_pair(
        self,
        symbol: str,
        tp_order_id: Optional[str] = None,
        sl_order_id: Optional[str] = None,
        pair_id: Optional[str] = None,
    ) -> str:
        """
        Registra un par de órdenes TP/SL para monitoreo OCO.

        Args:
            symbol: Símbolo del mercado
            tp_order_id: ID de la orden Take Profit
            sl_order_id: ID de la orden Stop Loss
            pair_id: ID único del par (opcional, se genera automáticamente)

        Returns:
            ID del par registrado
        """
        if not tp_order_id and not sl_order_id:
            raise ValueError("Debe proporcionar al menos una orden (TP o SL)")

        # Generar ID si no se proporciona
        if not pair_id:
            pair_id = f"{symbol}_{tp_order_id or 'none'}_{sl_order_id or 'none'}"

        # Crear par
        pair = OCOPair(
            symbol=symbol,
            tp_order_id=tp_order_id,
            sl_order_id=sl_order_id,
            created_at=datetime.now(),
        )

        # Registrar
        self.oco_pairs[pair_id] = pair

        self.logger.info(
            f"📋 OCO pair registered | "
            f"Symbol: {symbol} | "
            f"TP: {tp_order_id or 'None'} | "
            f"SL: {sl_order_id or 'None'}"
        )

        return pair_id

    async def start(self):
        """Inicia el monitor en background."""
        if self.running:
            self.logger.warning("⚠️ Monitor already running")
            return

        self.running = True
        self._start_time = datetime.now()
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("🔄 OCO Monitor started")

    async def stop(self):
        """Detiene el monitor."""
        if not self.running:
            return

        self.running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("⏹️ OCO Monitor stopped")

    async def _monitor_loop(self):
        """Loop principal de monitoreo."""
        self.logger.info("👁️ OCO Monitor loop started")

        while self.running:
            try:
                # Verificar todos los pares activos
                await self._check_all_pairs()

                # Esperar antes del próximo check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in monitor loop: {e}", exc_info=True)
                # Continuar monitoreando a pesar del error
                await asyncio.sleep(self.check_interval)

    async def _check_all_pairs(self):
        """Verifica todos los pares OCO activos."""
        if not self.oco_pairs:
            return  # Sin pares, no logear

        self._check_count += 1

        # Log periódico del estado (cada 10 checks = ~20s)
        if self._check_count % 10 == 0:
            uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            self.logger.info(
                f"📊 OCO Monitor | "
                f"Active pairs: {len(self.oco_pairs)} | "
                f"Checks: {self._check_count} | "
                f"Uptime: {uptime:.0f}s"
            )

        pairs_to_remove = []

        for pair_id, pair in self.oco_pairs.items():
            try:
                # Log detallado de cada par (solo en DEBUG)
                self.logger.debug(
                    f"🔍 Checking pair {pair_id} | "
                    f"TP: {pair.tp_order_id[:8] if pair.tp_order_id else 'None'}... | "
                    f"SL: {pair.sl_order_id[:8] if pair.sl_order_id else 'None'}..."
                )

                should_remove = await self._check_pair(pair_id, pair)
                if should_remove:
                    pairs_to_remove.append(pair_id)
                    self._pairs_processed += 1
            except Exception as e:
                self.logger.error(f"❌ Error checking pair {pair_id}: {e}", exc_info=True)

        # Remover pares completados
        for pair_id in pairs_to_remove:
            del self.oco_pairs[pair_id]
            self.logger.info(f"🗑️ OCO pair removed: {pair_id}")

    async def _check_pair(self, pair_id: str, pair: OCOPair) -> bool:
        """
        Verifica un par OCO y ejecuta la lógica de cancelación si es necesario.

        Returns:
            True si el par debe ser removido, False si debe seguir monitoreándose
        """
        tp_id, sl_id = pair.get_order_ids()

        try:
            # Obtener estado de cada orden individualmente
            tp_status = await self._get_order_status(tp_id, pair.symbol) if tp_id else None
            sl_status = await self._get_order_status(sl_id, pair.symbol) if sl_id else None

            # Si TP ya no está abierta (se ejecutó o canceló)
            if tp_id and tp_status != "open":
                self.logger.info(f"✅ TP executed/closed | " f"Symbol: {pair.symbol} | " f"TP ID: {tp_id}")

                # Cancelar SL si sigue abierta
                if sl_id and sl_status == "open":
                    await self._cancel_order_safe(sl_id, pair.symbol, "SL")

                return True  # Remover par

            # Si SL ya no está abierta (se ejecutó o canceló)
            if sl_id and sl_status != "open":
                self.logger.info(f"🛑 SL executed/closed | " f"Symbol: {pair.symbol} | " f"SL ID: {sl_id}")

                # Cancelar TP si sigue abierta
                if tp_id and tp_status == "open":
                    await self._cancel_order_safe(tp_id, pair.symbol, "TP")

                return True  # Remover par

            # Ambas siguen abiertas, seguir monitoreando
            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking OCO pair {pair_id}: {e}")
            return False  # No remover en caso de error

    async def _get_order_status(self, order_id: str, symbol: str) -> str:
        """
        Obtiene el estado de una orden por su ID.

        Returns:
            'open' si la orden está abierta, 'closed' si está cerrada o no se encuentra.
        """
        try:
            order = await self.connector.exchange.fetch_order(order_id, symbol)
            return order.get("status", "closed")
        except Exception as e:
            # Si la orden no se encuentra, considerarla cerrada
            if "OrderNotFound" in str(e):
                return "closed"
            # Para otros errores, retornamos 'unknown'
            self.logger.error(f"❌ Error obteniendo estado de orden {order_id}: {e}")
            return "unknown"

    async def _cancel_order_safe(self, order_id: str, symbol: str, order_type: str):
        """
        Cancela una orden de forma segura (maneja errores).

        Args:
            order_id: ID de la orden a cancelar
            symbol: Símbolo del mercado
            order_type: Tipo de orden ("TP" o "SL") para logging
        """
        try:
            await self.connector.exchange.cancel_order(order_id, symbol)
            self._orders_canceled += 1
            self.logger.info(f"❌ {order_type} canceled | " f"Symbol: {symbol} | " f"ID: {order_id}")
        except Exception as e:
            # La orden puede ya estar cancelada o no existir
            if "OrderNotFound" in str(type(e).__name__):
                self.logger.debug(f"{order_type} order already canceled: {order_id}")
            else:
                self.logger.error(f"❌ Error canceling {order_type} order {order_id}: {e}")

    def get_active_pairs_count(self) -> int:
        """Retorna el número de pares OCO activos."""
        return len(self.oco_pairs)

    def get_metrics(self) -> Dict:
        """Retorna métricas del monitor."""
        uptime = 0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()

        return {
            "running": self.running,
            "active_pairs": self.get_active_pairs_count(),
            "check_interval": self.check_interval,
            "total_checks": self._check_count,
            "pairs_processed": self._pairs_processed,
            "orders_canceled": self._orders_canceled,
            "uptime_seconds": uptime,
        }
