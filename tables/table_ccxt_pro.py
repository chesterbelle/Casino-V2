"""
===================================================
🪙 TableCCXTPro — Mesa Multi-Asset con CCXT Pro
==================================================="""
import traceback

Rol:
----
- Proveer datos en tiempo real desde múltiples exchanges usando CCXT Pro
• Ejecutar órdenes usando unified API de CCXT
• Gestionar balance y posiciones de manera holística
• Mantener interface compatible con Croupier existente

Características:
-------------
• Multi-asset: Múltiples símbolos concurrentes
• Multi-exchange: Unified API across exchanges
• WebSockets: Datos en tiempo real eficientes con fallback automático
• Balance unificado: Gestión holística del portfolio
• Modo híbrido inteligente: WebSocket-first con REST fallback dinámico

Mejoras v1.7 (basadas en CCXT Pro documentation):
-------------------------------------------------
✅ Verificación de exchange.has['watchOHLCV'] antes de usar WebSocket
✅ Fallback dinámico: Cambia automáticamente a REST después de 5 fallos consecutivos
✅ Normalización de símbolos por exchange (Kraken, Binance, Hyperliquid)
✅ Manejo robusto de timeouts y errores con recuperación automática
✅ Reset de contador de fallos en operaciones exitosas
✅ Logging mejorado para debugging de transiciones WebSocket ↔ REST

Formatos de símbolos por exchange:
----------------------------------
• Kraken Futures: 'BTC/USD:USD' (perpetual futures)
• Binance Futures: 'BTC/USDT' o 'BTCUSDT'
• Hyperliquid: 'BTC' (símbolo simple)

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
        self.base_currency = "USD"  # Moneda base para balance (USD, USDT, etc.)

        # Cargar credenciales desde .env si no se proporcionan
        if api_key is None or api_secret is None:
            if "kraken" in exchange_id.lower():
                from utils.exchanges.kraken_env_loader import get_kraken_credentials
                creds = get_kraken_credentials()
                if creds:
                    api_key = api_key or creds.get('apiKey')
                    api_secret = api_secret or creds.get('secret')
            elif "hyperliquid" in exchange_id.lower():
                from utils.exchanges.hyperliquid_env_loader import get_hyperliquid_credentials
                creds = get_hyperliquid_credentials()
                if creds:
                    api_key = api_key or creds.get('walletAddress')
                    api_secret = api_secret or creds.get('privateKey')
            elif "binance" in exchange_id.lower():
                from utils.exchanges.binance_env_loader import get_binance_credentials
                creds = get_binance_credentials()
                if creds:
                    api_key = api_key or creds.get('apiKey')
                    api_secret = api_secret or creds.get('secret')

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
        self.consecutive_ws_failures: int = 0
        self.max_ws_failures: int = 5  # Cambiar a REST después de 5 fallos consecutivos

        # Inicializar exchange
        self._init_exchange(api_key, api_secret)

        self.logger.info(f"🪙 TableCCXTPro inicializada (Modo Híbrido) | Exchange: {exchange_id} | Symbols: {symbols}")

    def _are_demo_credentials(self, api_key: str, api_secret: str) -> bool:
        """
        Detecta si las credenciales son para demo basado en su formato/patrón.
        Las credenciales demo de Kraken suelen tener características específicas.
        """
        if not api_key or not api_secret:
            return False

        # Las credenciales demo suelen ser más cortas o tener patrones específicos
        # También podemos intentar detectar por el comportamiento de autenticación
        # Por ahora, asumimos que si son credenciales que fallan en producción, son demo
        return True  # Por defecto asumir demo para ser seguro

    async def test_credentials(self) -> bool:
        """Prueba las credenciales intentando hacer una llamada simple."""
        try:
            # Intentar una llamada que no requiera permisos especiales
            await self.exchange.loadMarkets()
            # Si llega aquí, las credenciales son válidas para este entorno
            return True
        except Exception:
            return False

    def _init_exchange(self, api_key: Optional[str], api_secret: Optional[str]) -> None:
        """Inicializa la conexión CCXT async con WebSockets."""
        try:
            # Usar CCXT async support para WebSockets
            exchange_class = getattr(ccxt_async, self.exchange_id)

            # Configuración específica para Kraken Demo
            if "kraken" in self.exchange_id.lower():
                exchange_config = {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "future",
                        "watchBalance": True
                    },
                    # NO configurar URLs - dejar que CCXT use las por defecto
                    # y cambiar solo el hostname con sandbox=True
                    "sandbox": True  # Esto hace que CCXT use demo-futures.kraken.com automáticamente
                }
                self.logger.info("🔧 Configuración Kraken Futures DEMO aplicada (sandbox mode)")

            # Configuración específica para Hyperliquid
            elif "hyperliquid" in self.exchange_id.lower():
                exchange_config = {
                    "walletAddress": api_key,      # Hyperliquid usa wallet address
                    "privateKey": api_secret,      # Y private key para firmar
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "swap",     # Hyperliquid usa perpetual swaps
                        "watchBalance": True,
                        "defaultSlippage": 0.01,  # 1% slippage
                    },
                }
                self.logger.info(f"🔧 Configuración Hyperliquid {'TESTNET' if self.testnet else 'MAINNET'} aplicada")

            else:
                exchange_config = {
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

            self.exchange = exchange_class(exchange_config)

            # Configurar sandbox mode para Hyperliquid testnet
            if "hyperliquid" in self.exchange_id.lower() and self.testnet:
                self.exchange.set_sandbox_mode(True)
                self.logger.info("🧪 Hyperliquid sandbox mode activado")

            self.logger.info(f"🔌 Exchange {self.exchange_id} inicializado (CCXT async con WebSockets)")

        except Exception as e:
            self.logger.error(f"❌ Error inicializando exchange {self.exchange_id}: {e}")
            raise

    def get_balance_sync(self) -> dict:
        """
        Obtiene el balance del exchange de manera síncrona.
        Usa el mismo event loop que el exchange para evitar cerrarlo.
        """
        import concurrent.futures

        def get_balance_in_thread():
            # Crear un nuevo event loop para este thread
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Crear una nueva instancia del exchange con la misma configuración
                exchange_class = getattr(ccxt_async, self.exchange_id)

                # Copiar configuración incluyendo credenciales
                # Hyperliquid usa walletAddress/privateKey, otros usan apiKey/secret
                if "hyperliquid" in self.exchange_id.lower():
                    config = {
                        'walletAddress': getattr(self.exchange, 'walletAddress', None),
                        'privateKey': getattr(self.exchange, 'privateKey', None),
                        'enableRateLimit': True,
                        'options': self.exchange.options.copy() if hasattr(self.exchange, 'options') else {},
                    }
                else:
                    config = {
                        'apiKey': self.exchange.apiKey,
                        'secret': self.exchange.secret,
                        'enableRateLimit': True,
                        'options': self.exchange.options.copy() if hasattr(self.exchange, 'options') else {},
                        'sandbox': getattr(self.exchange, 'sandbox', False)
                    }

                temp_exchange = exchange_class(config)

                # Configurar sandbox mode para Hyperliquid testnet
                if "hyperliquid" in self.exchange_id.lower() and self.testnet:
                    temp_exchange.set_sandbox_mode(True)

                result = loop.run_until_complete(temp_exchange.fetch_balance())
                loop.run_until_complete(temp_exchange.close())
                return result
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_balance_in_thread)
            return future.result(timeout=10)

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

            # Iniciar tareas de mantenimiento - pero NO iniciar listener_task aquí
            # El listener se iniciará externamente para evitar problemas con asyncio.run()
            self.watchdog_task = asyncio.create_task(self._watchdog())
            # self.listener_task = asyncio.create_task(self.start_listening())  # REMOVIDO

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

    async def close_all_positions(self) -> None:
        """
        Cierra todas las posiciones abiertas en el exchange al finalizar la sesión.

        CRÍTICO: Debe llamarse antes de disconnect() para asegurar que no quedan
        posiciones abiertas cuando el bot se detiene.

        Maneja correctamente Hyperliquid usando órdenes limit con ajuste de precio,
        y otros exchanges usando su implementación nativa.
        """
        try:
            if not self.exchange:
                self.logger.warning("⚠️ Exchange no disponible para cerrar posiciones")
                return

            # Obtener posiciones abiertas del exchange
            positions = await self.exchange.fetch_positions()

            closed_count = 0
            for position in positions:
                # Verificar si la posición está realmente abierta
                contracts = float(position.get('contracts', 0))
                if contracts == 0:
                    continue

                symbol = position.get('symbol')
                side = position.get('side')  # 'long' o 'short'

                self.logger.info(f"🔒 Cerrando posición {side.upper()} en {symbol}: {contracts} contratos")

                # Para cerrar una posición, hacemos una orden en el lado opuesto
                close_side = 'sell' if side == 'long' else 'buy'

                try:
                    # Manejo especial para Hyperliquid - Usar market order con reduceOnly
                    if "hyperliquid" in self.exchange_id.lower():
                        # Para Hyperliquid, usamos market order con reduceOnly
                        # Esto asegura que la orden se ejecute al mejor precio disponible
                        close_order = await self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=close_side,
                            amount=abs(contracts),
                            params={
                                'reduceOnly': True  # Asegura que solo cierra posición existente
                            }
                        )
                    else:
                        # Para otros exchanges, usar market order
                        close_order = await self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=close_side,
                            amount=abs(contracts),
                            params={'reduceOnly': True}
                        )

                    self.logger.info(f"✅ Posición cerrada: {symbol} | Order ID: {close_order.get('id')}")
                    closed_count += 1

                    # Cerrar también en el tracker local
                    if hasattr(self.position_tracker, 'close_position'):
                        self.position_tracker.close_position()

                except Exception as e:
                    self.logger.error(f"❌ Error cerrando posición {symbol}: {e}")
                    self.logger.debug(f"Detalles del error: {str(e)}\n{traceback.format_exc()}")

            if closed_count > 0:
                self.logger.info(f"✅ Total de posiciones cerradas: {closed_count}")
                # Refrescar balance después de cerrar posiciones
                await self._refresh_balance_from_exchange()
            else:
                self.logger.info("ℹ️ No hay posiciones abiertas para cerrar")

        except Exception as e:
            self.logger.error(f"❌ Error en close_all_positions: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")

    async def _refresh_balance_from_exchange(self) -> None:
        """
        Refresca el balance desde el exchange después de un trade.

        CRÍTICO: Según CCXT best practices, el balance DEBE refrescarse
        después de cada trade para obtener el estado real del exchange.
        """
        try:
            if not self.exchange:
                return

            # Fetch balance real desde el exchange
            balance_data = await self.exchange.fetch_balance()

            # Extraer balance en la moneda base
            if self.base_currency in balance_data.get("total", {}):
                new_balance = float(balance_data["total"][self.base_currency])

                # Actualizar BalanceManager con el balance real
                if hasattr(self.balance_manager, "set_balance"):
                    self.balance_manager.set_balance(new_balance)
                    self.logger.info(f"💰 Balance actualizado desde exchange: {new_balance} {self.base_currency}")
                else:
                    self.logger.warning("⚠️ BalanceManager no tiene método set_balance")
            else:
                self.logger.warning(f"⚠️ No se encontró balance para {self.base_currency}")

        except Exception as e:
            self.logger.error(f"❌ Error refrescando balance: {e}")
            # No lanzar excepción, solo loguear - el trade ya se ejecutó

    def next_candle(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Retorna la última vela disponible para un símbolo específico o el primero por defecto.
        Interface compatible con live_session.py que espera next_candle() sin parámetros.

        Modo Híbrido: WebSocket-first con REST fallback automático.
        Maneja llamadas async internamente para mantener interface síncrona.

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
            # Usar sync wrapper para llamadas async
            if self.is_connected and self.exchange:
                try:
                    # Obtener datos frescos usando el método disponible (WebSocket o REST)
                    ohlcv_data = self._run_async_sync(self._get_fresh_ohlcv(target_symbol))
                    if ohlcv_data and len(ohlcv_data) > 0:
                        self._run_async_sync(self._handle_ohlcv_update(target_symbol, ohlcv_data[-1]))
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
                ohlcv_data = self._run_async_sync(self._poll_ohlcv_rest(target_symbol))
                if ohlcv_data and len(ohlcv_data) > 0:
                    self._run_async_sync(self._handle_ohlcv_update(target_symbol, ohlcv_data[-1]))
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

    def _run_async_sync(self, coro) -> Any:
        """
        Sync wrapper para ejecutar funciones async desde contexto síncrono.
        Maneja el event loop de manera segura para compatibilidad con live_session.py.

        Args:
            coro: Coroutine a ejecutar

        Returns:
            Resultado de la coroutine
        """
        try:
            # Intentar obtener el loop actual
            loop = asyncio.get_running_loop()
            # Si llegamos aquí, hay un loop corriendo
            # Usar thread pool para ejecutar en un loop separado
            import concurrent.futures
            import threading

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=10)  # Timeout de 10 segundos

        except RuntimeError:
            # No hay loop running, podemos crear uno nuevo
            try:
                # Intentar obtener el event loop actual
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    # Loop está cerrado, crear uno nuevo
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            except Exception:
                # Último recurso: crear loop completamente nuevo
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

    async def _check_websocket_support(self) -> bool:
        """Verifica si el exchange soporta WebSocket OHLCV según documentación CCXT Pro."""
        if not self.exchange:
            return False

        # Verificar exchange.has['watchOHLCV'] como recomienda la documentación
        if not self.exchange.has.get('watchOHLCV', False):
            self.logger.info(f"ℹ️ Exchange {self.exchange_id} no soporta watchOHLCV según has['watchOHLCV']")
            return False

        if not hasattr(self.exchange, "watch_ohlcv"):
            self.logger.info(f"ℹ️ Exchange {self.exchange_id} no tiene método watch_ohlcv")
            return False

        try:
            # Intentar un request WebSocket de prueba con timeout reducido
            test_symbol = self.symbols[0]
            self.logger.info(f"🔍 Probando soporte WebSocket para {test_symbol}...")
            test_data = await asyncio.wait_for(
                self.exchange.watch_ohlcv(test_symbol, self.timeframe),
                timeout=3.0  # Reducido de 5s a 3s
            )
            if test_data is not None and len(test_data) > 0:
                self.logger.info(f"✅ WebSocket soportado - datos recibidos: {len(test_data)} velas")
                return True
            else:
                self.logger.warning(f"⚠️ WebSocket retornó datos vacíos para {test_symbol}")
                return False
        except asyncio.TimeoutError:
            self.logger.warning(f"⏱️ Timeout verificando WebSocket para {self.exchange_id}")
            return False
        except Exception as e:
            self.logger.warning(f"❌ WebSocket no soportado por {self.exchange_id}: {e}")
            return False

    async def _get_fresh_ohlcv(self, symbol: str) -> Optional[List]:
        """Obtiene datos OHLCV frescos usando el método disponible (WebSocket o REST) con fallback automático."""
        try:
            if self.websocket_supported and hasattr(self.exchange, "watch_ohlcv"):
                # Intentar WebSocket primero
                ohlcv_data = await asyncio.wait_for(
                    self.exchange.watch_ohlcv(symbol, self.timeframe),
                    timeout=0.5
                )
                # Reset contador de fallos en éxito
                self.consecutive_ws_failures = 0
                return ohlcv_data
            else:
                # Fallback a REST API
                return await self._poll_ohlcv_rest(symbol)
        except asyncio.TimeoutError:
            self.logger.debug(f"⏱️ WebSocket timeout para {symbol}, usando REST")
            return await self._poll_ohlcv_rest(symbol)
        except Exception as e:
            self.logger.debug(f"⚠️ WebSocket error para {symbol}: {e}, usando REST")
            # Incrementar contador de fallos
            self.consecutive_ws_failures += 1
            if self.consecutive_ws_failures >= self.max_ws_failures:
                self.logger.warning(
                    f"🔄 WebSocket fallando consistentemente ({self.consecutive_ws_failures} veces), "
                    f"cambiando permanentemente a REST"
                )
                self.websocket_supported = False
                self.data_mode = "rest"
            return await self._poll_ohlcv_rest(symbol)

    async def _poll_ohlcv_rest(self, symbol: str) -> Optional[List]:
        """Obtiene datos OHLCV via REST API polling con validación de símbolos por exchange."""
        try:
            # Verificar que el exchange esté disponible
            if not self.exchange:
                self.logger.error("Exchange no disponible")
                return None

            # Normalizar símbolo según exchange
            normalized_symbol = self._normalize_symbol(symbol)

            # Usar fetch_ohlcv de CCXT (REST API)
            ohlcv_data = await self.exchange.fetch_ohlcv(
                normalized_symbol,
                self.timeframe,
                limit=1  # Solo la vela más reciente
            )

            if ohlcv_data and len(ohlcv_data) > 0:
                self.logger.info(f"📊 REST data received for {normalized_symbol}: {len(ohlcv_data)} candles")
                return ohlcv_data
            else:
                self.logger.warning(f"⚠️ No OHLCV data returned for {normalized_symbol}")
                return None
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                self.logger.error(f"❌ Event loop cerrado - exchange necesita reinicializarse")
                # El exchange se cerró, necesitamos reinicializarlo
                # Por ahora, retornar None y el sistema intentará reconectar
                return None
            else:
                raise
        except Exception as e:
            self.logger.warning(f"❌ REST polling failed for {symbol}: {e}")
            # Log detallado del error para debugging
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return None

    def _normalize_symbol(self, symbol: str) -> str:
        """Normaliza el formato del símbolo según el exchange.

        Formatos por exchange:
        - Kraken: 'BTC/USD:USD' (perpetual futures)
        - Binance: 'BTC/USDT' o 'BTCUSDT'
        - Hyperliquid: 'BTC'
        """
        # Si el exchange ya tiene el símbolo en markets, usarlo directamente
        if self.exchange and hasattr(self.exchange, 'markets') and symbol in self.exchange.markets:
            return symbol

        # Normalización específica por exchange
        exchange_lower = self.exchange_id.lower()

        if 'kraken' in exchange_lower:
            # Kraken Futures usa formato BTC/USD:USD para perpetuals
            if '/' not in symbol:
                # Si es solo 'BTC', convertir a 'BTC/USD:USD'
                return f"{symbol}/USD:USD"
            elif ':' not in symbol and '/' in symbol:
                # Si es 'BTC/USD', convertir a 'BTC/USD:USD'
                return f"{symbol}:USD"
            return symbol

        elif 'binance' in exchange_lower:
            # Binance acepta ambos formatos, preferir con /
            if '/' not in symbol:
                # 'BTCUSDT' -> 'BTC/USDT'
                if symbol.endswith('USDT'):
                    base = symbol[:-4]
                    return f"{base}/USDT"
            return symbol

        elif 'hyperliquid' in exchange_lower:
            # Hyperliquid usa formato BASE/USDC:USDC para perpetuos
            if '/' in symbol and ':' in symbol:
                # Ya tiene formato correcto (e.g., 'BTC/USDC:USDC')
                return symbol
            elif '/' not in symbol:
                # Solo base symbol (e.g., 'BTC') -> convertir a formato perpetuo
                return f"{symbol}/USDC:USDC"
            elif '/' in symbol and ':' not in symbol:
                # Tiene / pero no : (e.g., 'BTC/USD') -> convertir a formato perpetuo
                base = symbol.split('/')[0]
                return f"{base}/USDC:USDC"
            return symbol

        # Default: retornar sin cambios
        return symbol

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
        """
        Reconecta streams WebSocket después de desconexión.

        Implementa retry con backoff exponencial según CCXT best practices.
        """
        max_retries = 3
        retry_delay = 1  # segundos

        for attempt in range(max_retries):
            try:
                self.logger.info(f"🔄 Intentando reconectar streams (intento {attempt + 1}/{max_retries})...")

                # Verificar que el exchange esté disponible
                if not self.exchange:
                    self.logger.error("❌ Exchange no disponible para reconexión")
                    return

                # Recargar markets para asegurar datos frescos
                await self.exchange.load_markets(reload=True)

                # Recrear streams
                self.active_streams.clear()
                for symbol in self.symbols:
                    stream_id = f"{symbol.lower()}@{self.timeframe}"
                    if stream_id not in self.active_streams:
                        if hasattr(self.exchange, 'subscribe_ohlcv'):
                            await self.exchange.subscribe_ohlcv(symbol, self.timeframe)
                        self.active_streams.append(stream_id)
                        self.logger.info(f"🔄 Stream reconectado: {stream_id}")

                self.logger.info("✅ Streams reconectados exitosamente")
                return  # Éxito, salir del loop de reintentos

            except Exception as e:
                self.logger.error(f"❌ Error reconectando streams (intento {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Backoff exponencial
                    wait_time = retry_delay * (2 ** attempt)
                    self.logger.info(f"⏳ Esperando {wait_time}s antes de reintentar...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error("❌ Máximo de reintentos alcanzado, streams no reconectados")

    def execute_order_sync(self, order: Dict) -> Dict:
        """
        Wrapper síncrono para execute_order (para compatibilidad con Croupier).
        """
        return self._run_async_sync(self.execute_order(order))

    async def execute_order(self, order: Dict) -> Dict:
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

            self.logger.debug(f"🔍 execute_order recibió: size={size_fraction}, symbol={symbol}, side={side}")

            # Validaciones básicas
            if not symbol or not side:
                raise ValueError(f"Orden inválida: symbol={symbol}, side={side}")

            # Convertir LONG/SHORT a BUY/SELL para Kraken Futures
            if side == "LONG":
                side = "BUY"
            elif side == "SHORT":
                side = "SELL"

            if side not in ["BUY", "SELL"]:
                raise ValueError(f"Side inválido: {side}")

            # Obtener estado actual del balance
            balance_state = self.balance_manager.get_state()
            equity = balance_state.get("equity", 0.0)

            if equity <= 0:
                raise ValueError("No hay equity disponible")

            # Calcular tamaño nocional
            notional_size = equity * size_fraction
            self.logger.info(f"🔍 Cálculo: equity={equity}, size_fraction={size_fraction}, notional={notional_size}")

            # Obtener precio actual para cálculos
            current_price = self._get_current_price(symbol)
            if not current_price:
                raise ValueError(f"No hay precio disponible para {symbol}")

            self.logger.debug(f"🔍 Precio actual: {current_price}")

            # Calcular cantidad en base al símbolo
            quantity = self._calculate_quantity(notional_size, current_price, symbol)
            self.logger.info(f"🔍 Cantidad calculada: {quantity}")

            # Validar cantidad mínima
            if quantity <= 0:
                self.logger.warning(f"⚠️ Cantidad calculada es 0 o negativa: {quantity}. Rechazando orden.")
                return self._create_error_result(order, f"Cantidad inválida: {quantity}")

            # Verificar contra los límites del exchange (min, max, precision)
            if self.exchange and symbol in self.exchange.markets:
                market = self.exchange.markets[symbol]
                limits = market.get("limits", {})
                amount_limits = limits.get("amount", {})
                cost_limits = limits.get("cost", {})

                # Validar cantidad mínima
                min_amount = amount_limits.get("min")
                if min_amount is not None and quantity < min_amount:
                    self.logger.warning(f"⚠️ Cantidad {quantity} menor que mínimo {min_amount}. Rechazando orden.")
                    return self._create_error_result(order, f"Cantidad {quantity} menor que mínimo {min_amount}")

                # Validar cantidad máxima
                max_amount = amount_limits.get("max")
                if max_amount is not None and quantity > max_amount:
                    self.logger.warning(f"⚠️ Cantidad {quantity} mayor que máximo {max_amount}. Rechazando orden.")
                    return self._create_error_result(order, f"Cantidad {quantity} mayor que máximo {max_amount}")

                # Validar costo mínimo (notional)
                min_cost = cost_limits.get("min")
                if min_cost is not None and notional_size < min_cost:
                    self.logger.warning(f"⚠️ Costo {notional_size} menor que mínimo {min_cost}. Rechazando orden.")
                    return self._create_error_result(order, f"Costo {notional_size} menor que mínimo {min_cost}")

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

            # Solución especial para Hyperliquid market orders
            if "hyperliquid" in self.exchange_id.lower() and ccxt_order["type"] == "market":
                self.logger.info("🔧 Aplicando solución Hyperliquid para market orders")
                ticker = await self.exchange.fetch_ticker(ccxt_order["symbol"])
                current_price = ticker["last"]
                price_adjustment = 0.001  # 0.1%

                if ccxt_order["side"] == "buy":
                    ccxt_order["price"] = current_price * (1 + price_adjustment)
                else:
                    ccxt_order["price"] = current_price * (1 - price_adjustment)

                ccxt_order["type"] = "limit"

            # Enviar orden
            result = await self.exchange.create_order(**ccxt_order)
            self.logger.info(f"✅ Respuesta de exchange: {result}")

            # Procesar resultado
            execution_result = self._process_execution_result(result, order)
            self.logger.info(f"📊 Resultado procesado: {execution_result}")

            # CRÍTICO: Refrescar balance desde el exchange después del trade
            # Esto es necesario porque el balance cambia después de cada ejecución
            await self._refresh_balance_from_exchange()

            return execution_result

        except Exception as order_error:
            self.logger.error(f"❌ Error en create_order: {order_error}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

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
        self.logger.debug(f"🔍 Cantidad antes de precision: {quantity}")

        # Aplicar precision del símbolo
        if self.exchange and symbol in self.exchange.markets:
            market = self.exchange.markets[symbol]
            precision = market.get("precision", {}).get("amount", None)
            self.logger.debug(f"🔍 Precision del mercado {symbol}: {precision}")

            if precision is not None:
                # Si precision es < 1, es un step size (ej: 0.01)
                # Si precision es >= 1, es número de decimales (ej: 2)
                if precision < 1:
                    # Es un step size, redondear al múltiplo más cercano
                    quantity = round(quantity / precision) * precision
                    self.logger.debug(f"🔍 Cantidad ajustada a step size {precision}: {quantity}")
                else:
                    # Es número de decimales
                    decimals = int(precision)
                    quantity = round(quantity, decimals)
                    self.logger.debug(f"🔍 Cantidad redondeada a {decimals} decimales: {quantity}")

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

            # Extraer fee de forma segura
            fee_data = ccxt_result.get("fee")
            if fee_data and isinstance(fee_data, dict):
                fee = fee_data.get("cost", 0.0) or 0.0
            else:
                fee = 0.0

            # Determinar resultado
            if status == "closed" and filled > 0:
                result = "EXECUTED"  # Orden ejecutada exitosamente
            else:
                result = "PENDING"

            # En live trading, NO calculamos PnL aquí
            # El PnL solo se conoce al cerrar la posición
            # El balance real viene del exchange
            pnl = 0.0  # No hay PnL hasta cerrar posición

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
                # Modo REST polling - NO CANCELAR EL LOOP
                await self._rest_polling_loop()

        except asyncio.CancelledError:
            self.logger.info(f"🛑 Loop de escucha {self.data_mode} cancelado por sistema")
            # No relanzar la excepción para evitar crash
        except Exception as e:
            self.logger.error(f"❌ Error fatal en loop {self.data_mode}: {e}")
            raise

    async def _websocket_listening_loop(self) -> None:
        """Loop de escucha usando WebSocket con fallback dinámico a REST."""
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
                            # Reset contador de fallos en éxito
                            self.consecutive_ws_failures = 0
                            self.logger.debug(f"📊 WebSocket data received for {symbol}")

                    except asyncio.TimeoutError:
                        continue  # No hay datos nuevos
                    except Exception as e:
                        self.logger.debug(f"⚠️ WebSocket error for {symbol}: {e}")
                        # Incrementar contador de fallos
                        self.consecutive_ws_failures += 1
                        if self.consecutive_ws_failures >= self.max_ws_failures:
                            self.logger.warning(
                                f"🔄 WebSocket fallando consistentemente en loop, cambiando a REST"
                            )
                            self.websocket_supported = False
                            self.data_mode = "rest"
                            # Cambiar a loop REST
                            await self._rest_polling_loop()
                            return
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
        poll_count = 0

        while self.is_connected:
            try:
                poll_count += 1
                self.logger.info(f"🔄 Poll #{poll_count} - is_connected={self.is_connected}")
                data_received = False

                # Polling para cada símbolo
                for symbol in self.symbols:
                    try:
                        self.logger.debug(f"📡 Polling {symbol}...")
                        ohlcv_data = await self._poll_ohlcv_rest(symbol)

                        if ohlcv_data and len(ohlcv_data) > 0:
                            # Procesar la última vela
                            await self._handle_ohlcv_update(symbol, ohlcv_data[-1])
                            data_received = True
                            self.logger.info(f"📊 REST data received for {symbol}: {len(ohlcv_data)} candles")
                        else:
                            self.logger.debug(f"📭 No data for {symbol}")

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
                else:
                    self.logger.info("✅ Datos REST recibidos exitosamente")

                # Esperar antes del siguiente polling (no sobrecargar API)
                self.logger.debug("😴 Sleeping 1 second before next poll...")
                await asyncio.sleep(1.0)  # 1 segundo entre polls

            except Exception as e:
                self.logger.error(f"❌ REST polling loop error: {e}")
                await asyncio.sleep(5)  # Esperar más en caso de error
