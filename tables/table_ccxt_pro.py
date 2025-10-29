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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import ccxt
import ccxt.async_support as ccxt_async

from .balance_manager import BalanceManager
from .position_tracker import PositionTracker

class TableCCXTPro:
    """
    Mesa multi-asset usando CCXT Pro para live trading.

    Arquitectura:
    - CCXT Pro: WebSockets y unified API
    - PositionTracker: Gestión de posiciones abiertas
    - BalanceManager: Estado de capital
    - Interface compatible: Mantiene API existente
    """

    def __init__(self,
                 exchange_id: str,
                 symbols: List[str],
                 timeframe: str = '1m',
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 testnet: bool = True):
        """
        Inicializa mesa CCXT Pro multi-asset.

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

        # Inicializar exchange
        self._init_exchange(api_key, api_secret)

        self.logger.info(f"🪙 TableCCXTPro inicializada | Exchange: {exchange_id} | Symbols: {symbols}")

    def _init_exchange(self, api_key: Optional[str], api_secret: Optional[str]) -> None:
        """Inicializa la conexión CCXT async con WebSockets."""
        try:
            # Usar CCXT async support para WebSockets
            exchange_class = getattr(ccxt_async, self.exchange_id)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Para futures trading
                    'watchOrderBook': False,  # Solo necesitamos OHLCV
                    'watchTrades': False,
                    'watchBalance': True,    # Para actualizar balance
                }
            })

            self.logger.info(f"🔌 Exchange {self.exchange_id} inicializado (CCXT async con WebSockets)")

        except Exception as e:
            self.logger.error(f"❌ Error inicializando exchange {self.exchange_id}: {e}")
            raise

    async def connect(self) -> None:
        """Establece conexiones WebSocket para todos los símbolos."""
        if not self.exchange:
            raise RuntimeError("Exchange no inicializado")

        try:
            # Conectar al exchange
            await self.exchange.loadMarkets()

            # Crear streams para cada símbolo
            for symbol in self.symbols:
                stream_id = f"{symbol.lower()}@{self.timeframe}"
                self.active_streams.append(stream_id)

                self.logger.info(f"📡 Stream preparado: {stream_id}")

            self.is_connected = True
            self.logger.info(f"✅ Conectado a {len(self.symbols)} símbolos")

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
        if hasattr(self, 'watchdog_task') and self.watchdog_task and not self.watchdog_task.done():
            tasks_to_cancel.append(self.watchdog_task)
        if hasattr(self, 'listener_task') and self.listener_task and not self.listener_task.done():
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
                        last_update = self.last_candles[symbol].get('timestamp', 0)
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
                self.logger.debug(f"📊 Watchdog: {len(self.symbols)} símbolos, "
                                f"{len(self.last_candles)} con datos, "
                                f"{len(self.active_streams)} streams activos")

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
            symbol = order.get('symbol', '')
            side = order.get('side', '').upper()
            size_fraction = order.get('size', 0.0)
            order_type = order.get('type', 'market')

            # Validaciones básicas
            if not symbol or not side:
                raise ValueError(f"Orden inválida: symbol={symbol}, side={side}")

            if side not in ['BUY', 'SELL']:
                raise ValueError(f"Side inválido: {side}")

            # Obtener estado actual del balance
            balance_state = self.balance_manager.get_state()
            equity = balance_state.get('equity', 0.0)

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
                'symbol': symbol,
                'type': order_type.lower(),
                'side': side.lower(),
                'amount': quantity,
            }

            # Agregar precio si es limit order
            if order_type.lower() == 'limit' and 'price' in order:
                ccxt_order['price'] = order.get('price')

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

        # Incluir estado de WebSocket y datos recientes
        websocket_status = {
            'connected': self.is_connected,
            'active_streams': len(self.active_streams),
            'symbols_with_data': len([s for s in self.symbols if s in self.last_candles]),
            'last_update': max([c.get('timestamp', 0) for c in self.last_candles.values()] or [0])
        }

        return {
            'balance': balance_state.get('balance', 0.0),
            'equity': balance_state.get('equity', 0.0),
            'positions': position_state,
            'exchange': self.exchange_id,
            'symbols': self.symbols,
            'websocket': websocket_status,
            'last_candles': {symbol: self.last_candles.get(symbol, {}) for symbol in self.symbols}
        }

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Obtiene precio actual para un símbolo."""
        candle = self.last_candles.get(symbol)
        if candle:
            return float(candle.get('close', 0.0))
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
            precision = market.get('precision', {}).get('amount', 1)
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
            order_id = ccxt_result.get('id', '')
            status = ccxt_result.get('status', 'unknown')
            filled = ccxt_result.get('filled', 0.0)
            cost = ccxt_result.get('cost', 0.0)
            fee = ccxt_result.get('fee', {}).get('cost', 0.0)

            # Determinar resultado
            if status == 'closed' and filled > 0:
                result = 'WIN' if cost > 0 else 'LOSS'  # Simplificado
            else:
                result = 'PENDING'

            # Calcular PnL (simplificado)
            pnl = cost - fee if cost > 0 else -fee

            return {
                'trade_id': original_order.get('trade_id', order_id),
                'result': result,
                'pnl': pnl,
                'fee': fee,
                'symbol': original_order.get('symbol', ''),
                'balance': self.balance_manager.get_state().get('balance', 0.0),
                'status': status,
                'order_id': order_id,
                'filled': filled,
                'cost': cost,
                'timestamp': datetime.now().isoformat(),
                'market': f"{original_order.get('symbol', '')}@{self.timeframe}",
                'timeframe': self.timeframe,
                'side': original_order.get('side', ''),
                'action': 'BET',  # Siempre BET en live trading
                'ghost': False
            }

        except Exception as e:
            self.logger.error(f"Error procesando resultado CCXT: {e}")
            return self._create_error_result(original_order, str(e))

    def _update_state_after_execution(self, result: Dict) -> None:
        """Actualiza estado interno después de ejecución."""
        try:
            # Actualizar balance
            pnl = result.get('pnl', 0.0)
            fee = result.get('fee', 0.0)

            if pnl != 0.0 or fee != 0.0:
                # Aplicar cambios al balance
                current_balance = self.balance_manager.get_state().get('balance', 0.0)
                new_balance = current_balance + pnl - fee

                # En producción, usar método apropiado del BalanceManager
                if hasattr(self.balance_manager, 'set_balance'):
                    self.balance_manager.set_balance(new_balance)

            # Actualizar posiciones (simplificado)
            # En producción, integrar con PositionTracker

        except Exception as e:
            self.logger.error(f"Error actualizando estado: {e}")

    def _create_error_result(self, order: Dict, error: str) -> Dict:
        """Crea resultado de error estandarizado."""
        return {
            'trade_id': order.get('trade_id', 'error'),
            'result': 'ERROR',
            'pnl': 0.0,
            'fee': 0.0,
            'symbol': order.get('symbol', ''),
            'balance': self.balance_manager.get_state().get('balance', 0.0),
            'status': 'error',
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'market': f"{order.get('symbol', '')}@{self.timeframe}",
            'timeframe': self.timeframe,
            'side': order.get('side', ''),
            'action': 'ERROR',
            'ghost': False
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
                'timestamp': int(ohlcv[0]),
                'open': float(ohlcv[1]),
                'high': float(ohlcv[2]),
                'low': float(ohlcv[3]),
                'close': float(ohlcv[4]),
                'volume': float(ohlcv[5])
            }

            # Validar datos básicos
            if candle['close'] <= 0 or candle['volume'] < 0:
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
                        free = float(data.get('free', 0))
                        used = float(data.get('used', 0))
                        total = float(data.get('total', 0))

                        balance_details[currency] = {
                            'free': free,
                            'used': used,
                            'total': total
                        }

                        # Contar balance en monedas base (USDT, USD, BUSD)
                        if currency in ['USDT', 'USD', 'BUSD']:
                            total_balance += total

                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"⚠️ Error procesando balance para {currency}: {e}")
                        continue

            if total_balance > 0:
                # Actualizar balance manager
                if hasattr(self.balance_manager, 'set_balance'):
                    self.balance_manager.set_balance(total_balance)
                self.logger.debug(f"💰 Balance actualizado: {total_balance} | Detalles: {balance_details}")

        except Exception as e:
            self.logger.error(f"❌ Error procesando balance update: {e}")

    async def start_listening(self) -> None:
        """Inicia el loop de escucha de WebSocket messages."""
        if not self.is_connected or not self.exchange:
            raise RuntimeError("Exchange no conectado")

        try:
            while self.is_connected:
                try:
                    # Verificar si el exchange soporta WebSockets
                    if not hasattr(self.exchange, 'watch_ohlcv'):
                        self.logger.warning(f"⚠️ Exchange {self.exchange_id} no soporta WebSockets watch_ohlcv - usando modo simulado")
                        await asyncio.sleep(5)  # Esperar antes de reintentar
                        continue

                    # Usar watch_ohlcv individual para cada símbolo (más compatible)
                    for symbol in self.symbols:
                        try:
                            # Intentar obtener datos OHLCV para este símbolo
                            ohlcv_data = await asyncio.wait_for(
                                self.exchange.watch_ohlcv(symbol, self.timeframe),
                                timeout=1.0
                            )

                            if ohlcv_data and len(ohlcv_data) > 0:
                                # Procesar la última vela
                                await self._handle_ohlcv_update(symbol, ohlcv_data[-1])

                        except asyncio.TimeoutError:
                            # No hay datos nuevos para este símbolo, continuar
                            continue
                        except Exception as e:
                            # Log error but don't crash the entire loop
                            error_msg = str(e)
                            if "not supported yet" in error_msg:
                                self.logger.warning(f"⚠️ WebSocket OHLCV no soportado por {self.exchange_id}")
                                # Si no está soportado, salir del loop para evitar spam
                                await asyncio.sleep(5)
                                continue
                            else:
                                self.logger.debug(f"⚠️ Error obteniendo datos para {symbol}: {error_msg}")
                                continue

                    # Intentar obtener balance updates (menos frecuente)
                    try:
                        balance_message = await asyncio.wait_for(
                            self.exchange.watch_balance(),
                            timeout=0.1
                        )
                        if balance_message:
                            await self._handle_balance_update(balance_message)
                    except asyncio.TimeoutError:
                        pass  # No hay balance update, continuar
                    except Exception as e:
                        self.logger.debug(f"⚠️ Error obteniendo balance: {e}")

                except Exception as e:
                    self.logger.error(f"❌ Error procesando WebSocket message: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("🛑 Loop de escucha WebSocket cancelado")
        except Exception as e:
            self.logger.error(f"❌ Error fatal en loop WebSocket: {e}")
            raise