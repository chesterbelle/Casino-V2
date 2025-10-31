"""
===================================================
🪙 TableCCXTPro — Mesa Multi-Asset con CCXT Pro
===================================================

Rol:
----
• Proveer datos en tiempo real desde múltiples exchanges usando CCXT Pro
• Ejecutar órdenes usando unified API de CCXT
• Gestionar balance y posiciones de manera holística
• Mantener interface compatible con Croupier existente

Características:
-------------
• Multi-asset: Múltiples símbolos concurrentes
• Multi-exchange: Unified API across exchanges
• WebSockets: Datos en tiempo real eficientes
• Balance unificado: Gestión holística del portfolio

Interface compatible con:
-----------------------
• Croupier.route_order()
• Sistema de balance existente
• Formato de órdenes Gemini/Player
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import ccxt
import ccxt.async_support as ccxt_async

from .balance_manager import BalanceManager
from .position_tracker import PositionTracker
from .table_base import BaseTable


class TableCCXTPro(BaseTable):
    """
    Mesa multi-asset usando CCXT Pro para live trading.

    Arquitectura:
    - CCXT Pro: WebSockets y unified API
    - PositionTracker: Gestión de posiciones abiertas
    - BalanceManager: Estado de capital
    - Interface compatible: Mantiene API existente
    """

    def __init__(
        self,
        exchange_id: str,
        symbols: List[str],
        timeframe: str = "1m",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
    ):
        """
        Inicializa mesa CCXT Pro multi-asset.

        Arquitectura Híbrida:
        - WebSocket-first: Intenta usar WebSockets para baja latencia
        - REST fallback: Si WebSockets no están disponibles, usa REST API polling
        - Auto-detección: Detecta automáticamente qué método usar

        Args:
            exchange_id: ID del exchange (binance, kraken, hyperliquid, etc.)
            symbols: Lista de símbolos a operar
            timeframe: Timeframe principal
            api_key: API key (opcional, usar env vars)
            api_secret: API secret (opcional, usar env vars)
            testnet: Usar testnet si disponible
        """
        self.logger = logging.getLogger("TableCCXTPro")

        # Configuración
        self.exchange_id = exchange_id
        self.symbols = symbols
        self.timeframe = timeframe
        self.testnet = testnet

        # Componentes core
        self.balance_manager = BalanceManager(starting_balance=10_000.0)
        self.position_tracker = PositionTracker()

        # Estado interno
        self.exchange: Optional[ccxt_async.Exchange] = None
        self.last_candles: Dict[str, Dict] = {}
        self.active_streams: List[str] = []
        self.is_connected = False
        self.watchdog_task: Optional[asyncio.Task] = None

        # Modo de datos (auto-detectado)
        self.data_mode: str = "unknown"  # "websocket", "rest", or "unknown"
        self.websocket_supported: bool = False

        # Inicializar exchange
        self._init_exchange(api_key, api_secret)

        self.logger.info(f"🪙 TableCCXTPro inicializada (Modo Híbrido) | Exchange: {exchange_id} | Symbols: {symbols}")

    def _init_exchange(self, api_key: Optional[str], api_secret: Optional[str]) -> None:
        """Inicializa la conexión CCXT async con WebSockets."""
        try:
            # Usar CCXT async support para WebSockets
            exchange_class = getattr(ccxt_async, self.exchange_id)
            self.exchange = exchange_class(
                {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "future",  # Para futures trading
                        "watchOrderBook": False,  # Solo necesitamos OHLCV
                        "watchTrades": False,
                        "watchBalance": True,  # Para actualizar balance
                    },
                }
            )

            self.logger.info(f"🔌 Exchange {self.exchange_id} inicializado (CCXT async con WebSockets)")

        except Exception as e:
            self.logger.error(f"❌ Error inicializando exchange {self.exchange_id}: {e}")
            raise

    async def connect(self) -> None:
        """Establece conexiones y detecta modo de datos (WebSocket vs REST)."""
        if not self.exchange:
            raise RuntimeError("Exchange no inicializado")

        try:
            # Conectar al exchange
            await self.exchange.loadMarkets()

            # Detectar soporte WebSocket
            self.websocket_supported = await self._check_websocket_support()
            self.data_mode = "websocket" if self.websocket_supported else "rest"

            if self.websocket_supported:
                # Modo WebSocket: Crear streams para cada símbolo
                for symbol in self.symbols:
                    stream_id = f"{symbol.lower()}@{self.timeframe}"
                    self.active_streams.append(stream_id)
                    self.logger.info(f"📡 WebSocket stream preparado: {stream_id}")

                self.logger.info(f"✅ Modo WebSocket | Conectado a {len(self.symbols)} símbolos")
            else:
                # Modo REST: No necesitamos streams activos
                self.logger.info(f"✅ Modo REST Polling | Listo para {len(self.symbols)} símbolos")

            self.is_connected = True

            # Iniciar tareas de mantenimiento
            self.watchdog_task = asyncio.create_task(self._watchdog())
            self.listener_task = asyncio.create_task(self.start_listening())

        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}")
            raise

    async def disconnect(self) -> None:
        """Cierra todas las conexiones."""
        # Cancelar tareas activas
        tasks_to_cancel = []
        if hasattr(self, "watchdog_task") and self.watchdog_task and not self.watchdog_task.done():
            tasks_to_cancel.append(self.watchdog_task)
        if hasattr(self, "listener_task") and self.listener_task and not self.listener_task.done():
            tasks_to_cancel.append(self.listener_task)

        for task in tasks_to_cancel:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.exchange:
            await self.exchange.close()
            self.is_connected = False
            self.logger.info("🔌 Desconectado")

    def next_candle(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Retorna la última vela disponible para un símbolo específico o el primero por defecto.
        Interface compatible con live_session.py que espera next_candle() sin parámetros.

        Args:
            symbol: Símbolo específico (opcional, usa primer símbolo si no se especifica)

        Returns:
            Dict con datos de vela o None si no disponible
        """
        if not self.symbols:
            return None

        # Usar símbolo especificado o el primero por defecto
        target_symbol = symbol or self.symbols[0]

        # IMPORTANTE: Para live trading, necesitamos datos frescos
        # Si no hay datos en last_candles, intentar obtenerlos directamente
        if target_symbol not in self.last_candles:
            # Intentar obtener datos frescos de manera síncrona
            if self.is_connected and self.exchange:
                try:
                    # Obtener datos OHLCV de manera síncrona (para compatibilidad)
                    import asyncio

                    ohlcv_data = asyncio.run(self._get_fresh_ohlcv(target_symbol))
                    if ohlcv_data and len(ohlcv_data) > 0:
                        asyncio.run(self._handle_ohlcv_update(target_symbol, ohlcv_data[-1]))
                except Exception as e:
                    self.logger.debug(f"No se pudieron obtener datos frescos para {target_symbol}: {e}")

        candle = self.last_candles.get(target_symbol)

        if candle:
            # Formatear al estilo de otras mesas
            return {
                "timestamp": candle.get("timestamp", ""),
                "timestamp_ms": candle.get("timestamp", 0),
                "symbol": target_symbol,
                "timeframe": self.timeframe,
                "market": f"{target_symbol}@{self.timeframe}",
                "open": candle.get("open", 0.0),
                "high": candle.get("high", 0.0),
                "low": candle.get("low", 0.0),
                "close": candle.get("close", 0.0),
                "volume": candle.get("volume", 0.0),
                "equity": self.balance_manager.get_state().get("equity", 10000.0),
                "balance": self.balance_manager.get_state().get("balance", 10000.0),
            }

        # CRÍTICO: Si estamos en modo REST y no hay datos, intentar obtenerlos inmediatamente
        if self.data_mode == "rest" and self.is_connected and self.exchange:
            try:
                import asyncio

                ohlcv_data = asyncio.run(self._poll_ohlcv_rest(target_symbol))
                if ohlcv_data and len(ohlcv_data) > 0:
                    asyncio.run(self._handle_ohlcv_update(target_symbol, ohlcv_data[-1]))
                    # Reintentar obtener la vela
                    candle = self.last_candles.get(target_symbol)
                    if candle:
                        return {
                            "timestamp": candle.get("timestamp", ""),
                            "timestamp_ms": candle.get("timestamp", 0),
                            "symbol": target_symbol,
                            "timeframe": self.timeframe,
                            "market": f"{target_symbol}@{self.timeframe}",
                            "open": candle.get("open", 0.0),
                            "high": candle.get("high", 0.0),
                            "low": candle.get("low", 0.0),
                            "close": candle.get("close", 0.0),
                            "volume": candle.get("volume", 0.0),
                            "equity": self.balance_manager.get_state().get("equity", 10000.0),
                            "balance": self.balance_manager.get_state().get("balance", 10000.0),
                        }
            except Exception as e:
                self.logger.debug(f"Fallo al obtener datos REST inmediatamente para {target_symbol}: {e}")

        return None

    async def _check_websocket_support(self) -> bool:
        """Verifica si el exchange soporta WebSocket OHLCV."""
        if not self.exchange or not hasattr(self.exchange, "watch_ohlcv"):
            return False

        try:
            # Intentar un request WebSocket de prueba con timeout corto
            test_symbol = self.symbols[0]
            test_data = await asyncio.wait_for(self.exchange.watch_ohlcv(test_symbol, self.timeframe), timeout=2.0)
            return test_data is not None and len(test_data) > 0
        except Exception as e:
            self.logger.debug(f"WebSocket no soportado por {self.exchange_id}: {e}")
            return False

    async def _get_fresh_ohlcv(self, symbol: str) -> Optional[List]:
        """Obtiene datos OHLCV frescos usando el método disponible (WebSocket o REST)."""
        try:
            if self.websocket_supported and hasattr(self.exchange, "watch_ohlcv"):
                # Intentar WebSocket primero
                ohlcv_data = await asyncio.wait_for(self.exchange.watch_ohlcv(symbol, self.timeframe), timeout=0.5)
                return ohlcv_data
            else:
                # Fallback a REST API
                return await self._poll_ohlcv_rest(symbol)
        except Exception:
            # Último intento con REST
            return await self._poll_ohlcv_rest(symbol)

    async def _poll_ohlcv_rest(self, symbol: str) -> Optional[List]:
        """Obtiene datos OHLCV via REST API polling."""
        try:
            # Usar fetch_ohlcv de CCXT (REST API)
            ohlcv_data = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=1)  # Solo la vela más reciente

            if ohlcv_data and len(ohlcv_data) > 0:
                self.logger.info(f"📊 REST data received for {symbol}: {len(ohlcv_data)} candles")
                return ohlcv_data
            else:
                self.logger.warning(f"⚠️ No OHLCV data returned for {symbol} - check if symbol exists")
                return None
        except Exception as e:
            self.logger.warning(f"❌ REST polling failed for {symbol}: {e}")
            return None

    async def _watchdog(self) -> None:
        """Watchdog para mantener conexiones WebSocket vivas y monitorear salud."""
        while self.is_connected:
            try:
                # Ping cada 30 segundos para mantener conexión viva
                await asyncio.sleep(30)

                # Verificar estado de conexiones y datos
                symbols_without_data = []
                stale_data_symbols = []

                current_time = datetime.now().timestamp() * 1000  # ms

                for symbol in self.symbols:
                    if symbol not in self.last_candles:
                        symbols_without_data.append(symbol)
                    else:
                        last_update = self.last_candles[symbol].get("timestamp", 0)
                        if current_time - last_update > 60000:  # 1 minuto sin updates
                            stale_data_symbols.append(symbol)

                if symbols_without_data:
                    self.logger.warning(f"⚠️ No hay datos para símbolos: {symbols_without_data}")

                if stale_data_symbols:
                    self.logger.warning(f"⚠️ Datos stale (>1min) para: {stale_data_symbols}")

                # Reconectar streams si es necesario
                if not self.active_streams:
                    self.logger.warning("⚠️ No hay streams activos, reconectando...")
                    await self._reconnect_streams()

                # Log estado periódico
                self.logger.debug(
                    f"📊 Watchdog: {len(self.symbols)} símbolos, "
                    f"{len(self.last_candles)} con datos, "
                    f"{len(self.active_streams)} streams activos"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error en watchdog: {e}")
                await asyncio.sleep(5)

    async def _reconnect_streams(self) -> None:
        """Reconecta streams WebSocket."""
        try:
            for symbol in self.symbols:
                stream_id = f"{symbol.lower()}@{self.timeframe}"
                if stream_id not in self.active_streams:
                    await self.exchange.subscribe_ohlcv(symbol, self.timeframe)
                    self.active_streams.append(stream_id)
                    self.logger.info(f"🔄 Stream reconectado: {stream_id}")
        except Exception as e:
            self.logger.error(f"❌ Error reconectando streams: {e}")

    def execute_order(self, order: Dict) -> Dict:
        """
        Ejecuta orden usando CCXT Pro unified API.

        Interface compatible con Croupier existente.

        Args:
            order: Orden en formato estándar

        Returns:
            Resultado normalizado de la ejecución
        """
        if not self.exchange:
            raise RuntimeError("Exchange no conectado")

        try:
            # Extraer parámetros de la orden
            symbol = order.get("symbol", "")
            side = order.get("side", "").upper()
            size_fraction = order.get("size", 0.0)
            order_type = order.get("type", "market")

            # Validaciones básicas
            if not symbol or not side:
                raise ValueError(f"Orden inválida: symbol={symbol}, side={side}")

            if side not in ["BUY", "SELL"]:
                raise ValueError(f"Side inválido: {side}")

            # Obtener estado actual del balance
            balance_state = self.balance_manager.get_state()
            equity = balance_state.get("equity", 0.0)

            if equity <= 0:
                raise ValueError("No hay equity disponible")

            # Calcular tamaño de posición
            notional_size = equity * size_fraction

            # Obtener precio actual para cálculos
            current_price = self._get_current_price(symbol)
            if not current_price:
                raise ValueError(f"No hay precio disponible para {symbol}")

            # Calcular cantidad en base al símbolo
            quantity = self._calculate_quantity(notional_size, current_price, symbol)

            # Preparar orden CCXT
            ccxt_order = {
                "symbol": symbol,
                "type": order_type.lower(),
                "side": side.lower(),
                "amount": quantity,
            }

            # Agregar precio si es limit order
            if order_type.lower() == "limit" and "price" in order:
                ccxt_order["price"] = order.get("price")

            # Ejecutar orden
            self.logger.info(f"📤 Enviando orden: {ccxt_order}")
            result = asyncio.run(self.exchange.create_order(**ccxt_order))

            # Procesar resultado
            execution_result = self._process_execution_result(result, order)

            # Actualizar estado interno
            self._update_state_after_execution(execution_result)

            return execution_result

        except Exception as e:
            self.logger.error(f"❌ Error ejecutando orden: {e}")
            return self._create_error_result(order, str(e))

    def get_state(self) -> Dict:
        """
        Retorna estado unificado de la mesa.

        Interface compatible con sistema existente.
        """
        balance_state = self.balance_manager.get_state()
        position_state = self.position_tracker.get_stats()

        # Incluir estado de conectividad y datos recientes
        connection_status = {
            "connected": self.is_connected,
            "data_mode": self.data_mode,  # "websocket" or "rest"
            "websocket_supported": self.websocket_supported,
            "active_streams": len(self.active_streams),
            "symbols_with_data": len([s for s in self.symbols if s in self.last_candles]),
            "last_update": max([c.get("timestamp", 0) for c in self.last_candles.values()] or [0]),
        }

        return {
            "balance": balance_state.get("balance", 0.0),
            "equity": balance_state.get("equity", 0.0),
            "positions": position_state,
            "exchange": self.exchange_id,
            "symbols": self.symbols,
            "connection": connection_status,  # Renombrado de 'websocket' a 'connection'
            "last_candles": {symbol: self.last_candles.get(symbol, {}) for symbol in self.symbols},
        }

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Obtiene precio actual para un símbolo."""
        candle = self.last_candles.get(symbol)
        if candle:
            return float(candle.get("close", 0.0))
        return None

    def _calculate_quantity(self, notional_size: float, price: float, symbol: str) -> float:
        """
        Calcula cantidad de contratos/unidades basado en tamaño notional.

        Para futures, considera apalancamiento y contrato size.
        """
        # Para futuros, el notional es el valor en USD
        # La cantidad es notional / precio (simplificado)
        # En producción, considerar contract size del símbolo

        quantity = notional_size / price

        # Aplicar precision del símbolo
        if self.exchange and symbol in self.exchange.markets:
            market = self.exchange.markets[symbol]
            precision = market.get("precision", {}).get("amount", 1)
            quantity = round(quantity, precision)

        return quantity

    def _process_execution_result(self, ccxt_result: Dict, original_order: Dict) -> Dict:
        """
        Procesa resultado de CCXT y lo normaliza al formato esperado.

        Args:
            ccxt_result: Resultado raw de CCXT
            original_order: Orden original

        Returns:
            Resultado normalizado
        """
        try:
            # Extraer información relevante
            order_id = ccxt_result.get("id", "")
            status = ccxt_result.get("status", "unknown")
            filled = ccxt_result.get("filled", 0.0)
            cost = ccxt_result.get("cost", 0.0)
            fee = ccxt_result.get("fee", {}).get("cost", 0.0)

            # Determinar resultado
            if status == "closed" and filled > 0:
                result = "WIN" if cost > 0 else "LOSS"  # Simplificado
            else:
                result = "PENDING"

            # Calcular PnL (simplificado)
            pnl = cost - fee if cost > 0 else -fee

            return {
                "trade_id": original_order.get("trade_id", order_id),
                "result": result,
                "pnl": pnl,
                "fee": fee,
                "symbol": original_order.get("symbol", ""),
                "balance": self.balance_manager.get_state().get("balance", 0.0),
                "status": status,
                "order_id": order_id,
                "filled": filled,
                "cost": cost,
                "timestamp": datetime.now().isoformat(),
                "market": f"{original_order.get('symbol', '')}@{self.timeframe}",
                "timeframe": self.timeframe,
                "side": original_order.get("side", ""),
                "action": "BET",  # Siempre BET en live trading
                "ghost": False,
            }

        except Exception as e:
            self.logger.error(f"Error procesando resultado CCXT: {e}")
            return self._create_error_result(original_order, str(e))

    def _update_state_after_execution(self, result: Dict) -> None:
        """Actualiza estado interno después de ejecución."""
        try:
            # Actualizar balance
            pnl = result.get("pnl", 0.0)
            fee = result.get("fee", 0.0)

            if pnl != 0.0 or fee != 0.0:
                # Aplicar cambios al balance
                current_balance = self.balance_manager.get_state().get("balance", 0.0)
                new_balance = current_balance + pnl - fee

                # En producción, usar método apropiado del BalanceManager
                if hasattr(self.balance_manager, "set_balance"):
                    self.balance_manager.set_balance(new_balance)

            # Actualizar posiciones (simplificado)
            # En producción, integrar con PositionTracker

        except Exception as e:
            self.logger.error(f"Error actualizando estado: {e}")

    def _create_error_result(self, order: Dict, error: str) -> Dict:
        """Crea resultado de error estandarizado."""
        return {
            "trade_id": order.get("trade_id", "error"),
            "result": "ERROR",
            "pnl": 0.0,
            "fee": 0.0,
            "symbol": order.get("symbol", ""),
            "balance": self.balance_manager.get_state().get("balance", 0.0),
            "status": "error",
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "market": f"{order.get('symbol', '')}@{self.timeframe}",
            "timeframe": self.timeframe,
            "side": order.get("side", ""),
            "action": "ERROR",
            "ghost": False,
        }

    # Gestión de streams WebSocket
    async def _handle_ohlcv_update(self, symbol: str, ohlcv: List) -> None:
        """Maneja actualizaciones OHLCV desde WebSocket."""
        try:
            if not ohlcv or len(ohlcv) < 6:
                self.logger.warning(f"⚠️ OHLCV data inválida para {symbol}: {ohlcv}")
                return

            # Validar que el símbolo esté en nuestra lista
            if symbol not in self.symbols:
                self.logger.warning(f"⚠️ Símbolo no esperado: {symbol}")
                return

            # Convertir a formato interno
            candle = {
                "timestamp": int(ohlcv[0]),
                "open": float(ohlcv[1]),
                "high": float(ohlcv[2]),
                "low": float(ohlcv[3]),
                "close": float(ohlcv[4]),
                "volume": float(ohlcv[5]),
            }

            # Validar datos básicos
            if candle["close"] <= 0 or candle["volume"] < 0:
                self.logger.warning(f"⚠️ Datos OHLCV inválidos para {symbol}: {candle}")
                return

            self.last_candles[symbol] = candle
            self.logger.debug(f"📊 OHLCV update: {symbol} @ {candle['close']} (vol: {candle['volume']})")

        except (ValueError, IndexError) as e:
            self.logger.error(f"❌ Error procesando OHLCV para {symbol}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error inesperado en _handle_ohlcv_update: {e}")

    async def _handle_balance_update(self, balance: Dict) -> None:
        """Maneja actualizaciones de balance desde WebSocket."""
        try:
            if not balance:
                return

            # Convertir formato CCXT a nuestro formato interno
            total_balance = 0.0
            balance_details = {}

            for currency, data in balance.items():
                if isinstance(data, dict):
                    try:
                        free = float(data.get("free", 0))
                        used = float(data.get("used", 0))
                        total = float(data.get("total", 0))

                        balance_details[currency] = {"free": free, "used": used, "total": total}

                        # Contar balance en monedas base (USDT, USD, BUSD)
                        if currency in ["USDT", "USD", "BUSD"]:
                            total_balance += total

                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"⚠️ Error procesando balance para {currency}: {e}")
                        continue

            if total_balance > 0:
                # Actualizar balance manager
                if hasattr(self.balance_manager, "set_balance"):
                    self.balance_manager.set_balance(total_balance)
                self.logger.debug(f"💰 Balance actualizado: {total_balance} | Detalles: {balance_details}")

        except Exception as e:
            self.logger.error(f"❌ Error procesando balance update: {e}")

    async def start_listening(self) -> None:
        """Inicia el loop de escucha usando el método disponible (WebSocket o REST)."""
        if not self.is_connected or not self.exchange:
            raise RuntimeError("Exchange no conectado")

        try:
            if self.websocket_supported:
                # Modo WebSocket
                await self._websocket_listening_loop()
            else:
                # Modo REST polling
                await self._rest_polling_loop()

        except asyncio.CancelledError:
            self.logger.info(f"🛑 Loop de escucha {self.data_mode} cancelado")
        except Exception as e:
            self.logger.error(f"❌ Error fatal en loop {self.data_mode}: {e}")
            raise

    async def _websocket_listening_loop(self) -> None:
        """Loop de escucha usando WebSocket."""
        self.logger.info("🔄 Iniciando loop WebSocket")

        while self.is_connected:
            try:
                data_received = False
                for symbol in self.symbols:
                    try:
                        # Intentar obtener datos OHLCV para este símbolo
                        ohlcv_data = await asyncio.wait_for(
                            self.exchange.watch_ohlcv(symbol, self.timeframe), timeout=1.0
                        )

                        if ohlcv_data and len(ohlcv_data) > 0:
                            # Procesar la última vela
                            await self._handle_ohlcv_update(symbol, ohlcv_data[-1])
                            data_received = True
                            self.logger.debug(f"📊 WebSocket data received for {symbol}")

                    except asyncio.TimeoutError:
                        continue  # No hay datos nuevos
                    except Exception as e:
                        self.logger.debug(f"⚠️ WebSocket error for {symbol}: {e}")
                        continue

                # Intentar obtener balance updates
                try:
                    balance_message = await asyncio.wait_for(self.exchange.watch_balance(), timeout=0.1)
                    if balance_message:
                        await self._handle_balance_update(balance_message)
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    self.logger.debug(f"⚠️ Balance update error: {e}")

                # Log estado si no hay datos
                if not data_received:
                    self.logger.debug(f"⏳ No WebSocket data for {self.symbols}")

                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"❌ WebSocket loop error: {e}")
                await asyncio.sleep(1)

    async def _rest_polling_loop(self) -> None:
        """Loop de escucha usando REST API polling."""
        self.logger.info("🔄 Iniciando loop REST polling")

        while self.is_connected:
            try:
                data_received = False

                # Polling para cada símbolo
                for symbol in self.symbols:
                    try:
                        ohlcv_data = await self._poll_ohlcv_rest(symbol)

                        if ohlcv_data and len(ohlcv_data) > 0:
                            # Procesar la última vela
                            await self._handle_ohlcv_update(symbol, ohlcv_data[-1])
                            data_received = True
                            self.logger.info(f"📊 REST data received for {symbol}: {ohlcv_data[-1]}")

                    except Exception as e:
                        self.logger.warning(f"⚠️ REST polling error for {symbol}: {e}")
                        continue

                # Intentar obtener balance (menos frecuente en REST)
                if int(asyncio.get_event_loop().time()) % 10 == 0:  # Cada 10 segundos
                    try:
                        balance_data = await self.exchange.fetch_balance()
                        if balance_data:
                            await self._handle_balance_update(balance_data)
                    except Exception as e:
                        self.logger.debug(f"⚠️ Balance fetch error: {e}")

                # Log estado si no hay datos
                if not data_received:
                    self.logger.warning(
                        f"⏳ No REST data received for {self.symbols} - exchange may be down or symbol invalid"
                    )

                # Esperar antes del siguiente polling (no sobrecargar API)
                await asyncio.sleep(1.0)  # 1 segundo entre polls

            except Exception as e:
                self.logger.error(f"❌ REST polling loop error: {e}")
                await asyncio.sleep(5)  # Esperar más en caso de error
