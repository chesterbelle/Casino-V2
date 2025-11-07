"""
Kraken WebSocket Client - Casino V2

Cliente WebSocket para Kraken Futures con fallback automático a REST.
Inspirado en Hummingbot's WebSocket implementation.

Características:
- Trades en tiempo real
- Order updates
- Balance updates
- Reconexión automática
- Fallback a REST si falla

Author: Casino V2 Team
Version: 2.0.0
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

import websockets

from .kraken_constants import WS_CHANNELS, get_ws_url


class KrakenWebSocket:
    """
    Cliente WebSocket para Kraken Futures.

    Maneja conexión, suscripciones, y eventos en tiempo real.

    Ejemplo:
        ws = KrakenWebSocket(testnet=True)
        await ws.connect()

        # Suscribirse a trades
        await ws.subscribe_trades("BTC/USD", callback=on_trade)

        # Suscribirse a órdenes
        await ws.subscribe_orders(api_key, callback=on_order)
    """

    def __init__(
        self,
        testnet: bool = True,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        max_reconnect_attempts: int = 10,
    ):
        """
        Initialize Kraken WebSocket client.

        Args:
            testnet: Si True, usa demo; si False, usa mainnet
            ping_interval: Intervalo de ping en segundos
            ping_timeout: Timeout de ping en segundos
            max_reconnect_attempts: Máximo de intentos de reconexión
        """
        self.logger = logging.getLogger("KrakenWebSocket")

        # Configuración
        self._testnet = testnet
        self._ws_url = get_ws_url(testnet)
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._max_reconnect_attempts = max_reconnect_attempts

        # Estado
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._callbacks: Dict[str, Callable] = {}

        # Buffers para datos
        self._trades_buffer: Dict[str, deque] = {}  # symbol -> deque of trades
        self._orders_buffer: deque = deque(maxlen=1000)
        self._balance_buffer: Dict[str, float] = {}

        # Tasks
        self._listen_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

        # Métricas
        self._messages_received = 0
        self._reconnect_count = 0
        self._last_message_time = 0.0

        self.logger.info(f"✅ KrakenWebSocket initialized | URL: {self._ws_url}")

    async def connect(self) -> bool:
        """
        Conecta al WebSocket de Kraken.

        Returns:
            True si conectó exitosamente

        Raises:
            ConnectionError: Si falla después de todos los intentos
        """
        for attempt in range(self._max_reconnect_attempts):
            try:
                self.logger.info(f"🔌 Conectando a Kraken WebSocket (intento {attempt + 1})...")

                # Conectar
                self._ws = await websockets.connect(
                    self._ws_url,
                    ping_interval=self._ping_interval,
                    ping_timeout=self._ping_timeout,
                )

                self._connected = True
                self._last_message_time = time.time()

                # Iniciar listeners
                self._listen_task = asyncio.create_task(self._listen_messages())
                self._ping_task = asyncio.create_task(self._ping_loop())

                self.logger.info("✅ Conectado a Kraken WebSocket")

                # Re-suscribirse a canales si es reconexión
                if self._subscriptions:
                    await self._resubscribe_all()

                return True

            except Exception as e:
                self.logger.error(f"❌ Error conectando (intento {attempt + 1}): {e}")
                if attempt < self._max_reconnect_attempts - 1:
                    backoff = 2**attempt
                    self.logger.info(f"⏳ Reintentando en {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    raise ConnectionError(f"Failed to connect after {self._max_reconnect_attempts} attempts")

        return False

    async def disconnect(self) -> None:
        """Desconecta del WebSocket."""
        self.logger.info("🔌 Desconectando WebSocket...")

        self._connected = False

        # Cancelar tasks
        if self._listen_task:
            self._listen_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()

        # Cerrar conexión
        if self._ws:
            await self._ws.close()
            self._ws = None

        self.logger.info("✅ WebSocket desconectado")

    async def subscribe_trades(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Suscribe a trades de un símbolo.

        Args:
            symbol: Par de trading (e.g., "BTC/USD")
            callback: Función a llamar cuando llega un trade

        Returns:
            True si se suscribió exitosamente
        """
        if not self._connected:
            self.logger.error("❌ No conectado. Llama connect() primero.")
            return False

        try:
            # Mensaje de suscripción
            subscribe_msg = {
                "event": "subscribe",
                "feed": WS_CHANNELS["trade"],
                "product_ids": [symbol],
            }

            await self._ws.send(json.dumps(subscribe_msg))

            # Guardar suscripción
            sub_key = f"trade_{symbol}"
            self._subscriptions[sub_key] = {"feed": "trade", "symbol": symbol}

            if callback:
                self._callbacks[sub_key] = callback

            # Inicializar buffer
            if symbol not in self._trades_buffer:
                self._trades_buffer[symbol] = deque(maxlen=1000)

            self.logger.info(f"✅ Suscrito a trades de {symbol}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error suscribiendo a trades: {e}")
            return False

    async def subscribe_orders(self, api_key: str, callback: Optional[Callable] = None) -> bool:
        """
        Suscribe a actualizaciones de órdenes (requiere autenticación).

        Args:
            api_key: API key de Kraken
            callback: Función a llamar cuando llega una actualización

        Returns:
            True si se suscribió exitosamente
        """
        if not self._connected:
            self.logger.error("❌ No conectado. Llama connect() primero.")
            return False

        try:
            # TODO: Implementar autenticación para WebSocket privado
            # Por ahora, solo logging
            self.logger.warning("⚠️ subscribe_orders requiere autenticación (TODO)")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error suscribiendo a órdenes: {e}")
            return False

    async def _listen_messages(self) -> None:
        """Loop que escucha mensajes del WebSocket."""
        try:
            async for message in self._ws:
                self._messages_received += 1
                self._last_message_time = time.time()

                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ Error parseando mensaje: {e}")
                except Exception as e:
                    self.logger.error(f"❌ Error procesando mensaje: {e}")

        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("⚠️ WebSocket cerrado, intentando reconectar...")
            self._connected = False
            await self._reconnect()

        except Exception as e:
            self.logger.error(f"❌ Error en listen loop: {e}")
            self._connected = False

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """
        Procesa mensaje del WebSocket.

        Args:
            data: Mensaje parseado
        """
        # Eventos del sistema
        if "event" in data:
            event = data["event"]

            if event == "subscribed":
                self.logger.info(f"✅ Suscripción confirmada: {data.get('feed')}")
            elif event == "info":
                self.logger.debug(f"ℹ️ Info: {data.get('message')}")
            elif event == "error":
                self.logger.error(f"❌ Error del WS: {data.get('message')}")

            return

        # Datos de feeds
        feed = data.get("feed")

        if feed == "trade":
            await self._handle_trade(data)
        elif feed == "fills":
            await self._handle_fill(data)
        elif feed == "open_orders":
            await self._handle_order(data)
        elif feed == "balances":
            await self._handle_balance(data)
        else:
            self.logger.debug(f"📨 Mensaje no manejado: {feed}")

    async def _handle_trade(self, data: Dict[str, Any]) -> None:
        """Procesa trade del WebSocket."""
        try:
            symbol = data.get("product_id")
            trades = data.get("trades", [])

            for trade in trades:
                # Agregar a buffer
                if symbol in self._trades_buffer:
                    self._trades_buffer[symbol].append(trade)

                # Llamar callback si existe
                sub_key = f"trade_{symbol}"
                if sub_key in self._callbacks:
                    await self._callbacks[sub_key](trade)

        except Exception as e:
            self.logger.error(f"❌ Error procesando trade: {e}")

    async def _handle_fill(self, data: Dict[str, Any]) -> None:
        """Procesa fill (orden ejecutada)."""
        try:
            # Agregar a buffer
            self._orders_buffer.append(data)

            # Llamar callback si existe
            if "fills" in self._callbacks:
                await self._callbacks["fills"](data)

        except Exception as e:
            self.logger.error(f"❌ Error procesando fill: {e}")

    async def _handle_order(self, data: Dict[str, Any]) -> None:
        """Procesa actualización de orden."""
        try:
            # Llamar callback si existe
            if "orders" in self._callbacks:
                await self._callbacks["orders"](data)

        except Exception as e:
            self.logger.error(f"❌ Error procesando orden: {e}")

    async def _handle_balance(self, data: Dict[str, Any]) -> None:
        """Procesa actualización de balance."""
        try:
            balances = data.get("balances", {})
            self._balance_buffer.update(balances)

            # Llamar callback si existe
            if "balance" in self._callbacks:
                await self._callbacks["balance"](balances)

        except Exception as e:
            self.logger.error(f"❌ Error procesando balance: {e}")

    async def _ping_loop(self) -> None:
        """Loop de ping para mantener conexión viva."""
        while self._connected:
            try:
                await asyncio.sleep(self._ping_interval)

                # Verificar si recibimos mensajes recientemente
                time_since_last = time.time() - self._last_message_time
                if time_since_last > self._ping_timeout * 2:
                    self.logger.warning(f"⚠️ Sin mensajes por {time_since_last:.1f}s, reconectando...")
                    await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error en ping loop: {e}")

    async def _reconnect(self) -> None:
        """Reconecta al WebSocket."""
        self._reconnect_count += 1
        self.logger.info(f"🔄 Reconectando... (intento {self._reconnect_count})")

        await self.disconnect()
        await asyncio.sleep(2)
        await self.connect()

    async def _resubscribe_all(self) -> None:
        """Re-suscribe a todos los canales después de reconexión."""
        self.logger.info("🔄 Re-suscribiendo a canales...")

        for sub_key, sub_data in self._subscriptions.items():
            try:
                if sub_data["feed"] == "trade":
                    await self.subscribe_trades(sub_data["symbol"])
            except Exception as e:
                self.logger.error(f"❌ Error re-suscribiendo {sub_key}: {e}")

    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Obtiene trades recientes del buffer.

        Args:
            symbol: Par de trading
            limit: Número máximo de trades

        Returns:
            Lista de trades
        """
        if symbol not in self._trades_buffer:
            return []

        trades = list(self._trades_buffer[symbol])
        return trades[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del WebSocket."""
        return {
            "connected": self._connected,
            "messages_received": self._messages_received,
            "reconnect_count": self._reconnect_count,
            "subscriptions": len(self._subscriptions),
            "time_since_last_message": time.time() - self._last_message_time if self._last_message_time else None,
        }

    @property
    def is_connected(self) -> bool:
        """Verifica si está conectado."""
        return self._connected
