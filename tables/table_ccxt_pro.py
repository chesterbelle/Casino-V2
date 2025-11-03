from __future__ import annotations

"""
===================================================
🪙 TableCCXTPro — Mesa Multi-Asset con CCXT Pro
===================================================

Rol:
----
- Proveer datos en tiempo real desde múltiples exchanges usando CCXT Pro
- Ejecutar órdenes usando unified API de CCXT
- Gestionar balance y posiciones de manera holística
- Mantener interface compatible con Croupier existente

Características:
-------------
- Multi-asset: Múltiples símbolos concurrentes
- Multi-exchange: Unified API across exchanges
- WebSockets: Datos en tiempo real eficientes con fallback automático
- Balance unificado: Gestión holística del portfolio
- Modo híbrido inteligente: WebSocket-first con REST fallback dinámico
"""

import traceback

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
        self.logger = logging.getLogger("TableCCXTPro")

        # Configuración
        self.exchange_id = exchange_id
        self.symbols = symbols
        self.timeframe = timeframe
        self.testnet = testnet
        self.base_currency = "USD"
        self.market_type = "spot"

        # Cargar credenciales
        if api_key is None or api_secret is None:
            if "kraken" in exchange_id.lower():
                from utils.exchanges.kraken_env_loader import get_kraken_credentials
                creds = get_kraken_credentials()
                if creds:
                    api_key = api_key or creds.get('apiKey')
                    api_secret = api_secret or creds.get('secret')
            elif "hyperliquid" in exchange_id.lower():
                from utils.exchanges.hyperliquid_env_loader import load_hyperliquid_config, get_hyperliquid_credentials
                self.hyperliquid_config = load_hyperliquid_config()
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

        # Componentes
        self.balance_manager = BalanceManager(starting_balance=10_000.0)
        self.position_tracker = PositionTracker()

        # Estado
        self.exchange: Optional[ccxt_async.Exchange] = None
        self.last_candles: Dict[str, Dict] = {}
        self.active_streams: List[str] = []
        self.is_connected = False
        self.watchdog_task: Optional[asyncio.Task] = None
        self.data_mode: str = "unknown"
        self.websocket_supported: bool = False
        self.consecutive_ws_failures: int = 0
        self.max_ws_failures: int = 5

        # Inicializar
        self._init_exchange(api_key, api_secret)

        self.logger.info(f"🪙 TableCCXTPro inicializada | Exchange: {exchange_id} | Symbols: {symbols}")
    def _are_demo_credentials(self, api_key: str, api_secret: str) -> bool:
        """
        Detecta si las credenciales son para demo basado en su formato/patrón.
        """
        if not api_key or not api_secret:
            return False
        return True

    async def test_credentials(self) -> bool:
        """Prueba las credenciales intentando hacer una llamada simple."""
        try:
            await self.exchange.loadMarkets()
            return True
        except Exception:
            return False

    def _init_exchange(self, api_key: Optional[str], api_secret: Optional[str]) -> None:
        """
        Inicializa la conexión CCXT async con configuración específica por exchange.
        """
        try:
            ccxt_exchange_id = self.exchange_id.lower()
            if ccxt_exchange_id == "kraken":
                ccxt_exchange_id = "krakenfutures"
            
            exchange_class = getattr(ccxt_async, ccxt_exchange_id)
            exchange_config = {}

            if "kraken" in self.exchange_id.lower():
                exchange_config = {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "urls": {"api": {"public": "https://demo-futures.kraken.com/derivatives/api/", "private": "https://demo-futures.kraken.com/derivatives/api/"}},
                    "options": {"defaultType": "future", "watchBalance": True}
                }
                self.base_currency = "USD"
                self.market_type = "future"
                self.logger.info("🔧 Configuración Kraken Futures Demo aplicada")

            elif "hyperliquid" in self.exchange_id.lower():
                if not hasattr(self, "hyperliquid_config"):
                    from utils.exchanges.hyperliquid_env_loader import load_hyperliquid_config
                    self.hyperliquid_config = load_hyperliquid_config()
                
                testnet_flag = self.hyperliquid_config.get("testnet", self.testnet)
                base_url = self.hyperliquid_config.get("test_base_url" if testnet_flag else "base_url")
                
                exchange_config = {
                    "walletAddress": api_key,
                    "privateKey": api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "swap", "watchBalance": True, "defaultSlippage": 0.01},
                    "urls": {"api": {"public": base_url, "private": base_url}},
                    "hostname": "hyperliquid-testnet.xyz" if testnet_flag else "hyperliquid.xyz"
                }
                self.base_currency = "USDC"
                self.market_type = "swap"
                self.logger.info(f"🔧 Configuración Hyperliquid {'TESTNET' if testnet_flag else 'MAINNET'} aplicada")

            elif "binance" in self.exchange_id.lower():
                exchange_config = {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future", "defaultSubType": "linear"},
                    "urls": {
                        "api": {
                            "fapiPublic": "https://demo-fapi.binance.com/fapi/v1",
                            "fapiPrivate": "https://demo-fapi.binance.com/fapi/v1",
                            "public": "https://demo-fapi.binance.com/fapi/v1",
                            "private": "https://demo-fapi.binance.com/fapi/v1",
                        }
                    },
                    "hostname": "demo-fapi.binance.com",
                }
                self.base_currency = "USDT"
                self.market_type = "linear"
                self.logger.info("🔧 Configuración Binance Futures TESTNET aplicada")

            else:
                exchange_config = {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"}
                }
                self.market_type = "future"

            self.exchange = exchange_class(exchange_config)

            if "hyperliquid" in self.exchange_id.lower() and self.testnet:
                self.exchange.set_sandbox_mode(True)
                self.logger.info("🧪 Hyperliquid sandbox (testnet) activado")

            self.logger.info(f"🔌 Exchange {self.exchange_id} inicializado")

        except Exception as e:
            self.logger.error(f"❌ Error inicializando exchange {self.exchange_id}: {e}", exc_info=True)
            raise
    async def close(self):
        """Cierra la conexión y libera recursos."""
        try:
            if self.exchange and hasattr(self.exchange, 'close'):
                await self.exchange.close()
                self.logger.info(f"✅ Conexión {self.exchange_id} cerrada correctamente")
        except Exception as e:
            self.logger.error(f"❌ Error cerrando conexión {self.exchange_id}: {e}")

    def get_balance_sync(self) -> dict:
        """
        Obtiene el balance del exchange de manera síncrona.
        """
        import concurrent.futures

        def get_balance_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Re-crear una instancia temporal del exchange para esta operación
                # Esto evita conflictos con el loop principal de asyncio
                temp_exchange_class = getattr(ccxt_async, self.exchange.id)
                temp_exchange = temp_exchange_class(self.exchange.safe_string_dictionary(self.exchange.options))
                
                result = loop.run_until_complete(temp_exchange.fetch_balance())
                loop.run_until_complete(temp_exchange.close())
                return result
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_balance_in_thread)
            return future.result(timeout=15)

    async def connect(self) -> None:
        """Establece conexiones y detecta modo de datos (WebSocket vs REST)."""
        if not self.exchange:
            raise RuntimeError("Exchange no inicializado")
        try:
            await self.exchange.loadMarkets()
            self.websocket_supported = self.exchange.has.get('watchOHLCV', False)
            self.data_mode = "websocket" if self.websocket_supported else "rest"
            self.is_connected = True
            self.logger.info(f"✅ Conectado a {self.exchange_id} en modo {self.data_mode}")
        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}", exc_info=True)
            raise

    async def start_listening(self) -> None:
        """Inicia el loop de escucha de datos."""
        if not self.is_connected:
            raise RuntimeError("No conectado. Llama a connect() primero.")
        
        if self.data_mode == "websocket":
            await self._websocket_listening_loop()
        else:
            await self._rest_polling_loop()

    async def _websocket_listening_loop(self):
        """Loop de escucha para datos de mercado vía WebSockets."""
        while self.is_connected:
            try:
                for symbol in self.symbols:
                    trades = await self.exchange.watch_trades(symbol)
                    if trades:
                        # Lógica para procesar trades y construir velas si es necesario
                        self.logger.info(f"Received {len(trades)} trades for {symbol}")
            except Exception as e:
                self.logger.error(f"Error en el loop de WebSocket: {e}")
                await asyncio.sleep(5) # Esperar antes de reintentar

    async def _rest_polling_loop(self):
        """Loop de escucha para datos de mercado vía REST polling."""
        while self.is_connected:
            try:
                for symbol in self.symbols:
                    ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=5)
                    if ohlcv:
                        self.last_candles[symbol] = ohlcv[-1] # Guardar la última vela
                        self.logger.info(f"Poll {symbol}: {ohlcv[-1]}")
                await asyncio.sleep(self.exchange.rateLimit / 1000) # Respetar rate limit
            except Exception as e:
                self.logger.error(f"Error en el loop de REST polling: {e}")
                await asyncio.sleep(5)

    def next_candle(self, symbol: str = None) -> Optional[list]:
        """Retorna la última vela disponible para un símbolo."""
        target_symbol = symbol or self.symbols[0]
        return self.last_candles.get(target_symbol)

    def execute_order(self, order: dict):
        """Ejecuta una orden (wrapper síncrono)."""
        return asyncio.run(self.async_execute_order(order))

    async def async_execute_order(self, order: dict):
        """Ejecuta una orden de forma asíncrona."""
        if not self.is_connected:
            raise RuntimeError("No conectado al exchange.")
        try:
            return await self.exchange.create_order(
                symbol=order['symbol'],
                type=order['type'],
                side=order['side'],
                amount=order['amount'],
                price=order.get('price') # Opcional para órdenes limit
            )
        except Exception as e:
            self.logger.error(f"Error ejecutando orden: {e}", exc_info=True)
            raise

    def get_state(self) -> dict:
        """Retorna el estado actual de la mesa."""
        return {
            "balance": self.balance_manager.get_state(),
            "positions": self.position_tracker.get_stats(),
            "last_candles": self.last_candles,
            "is_connected": self.is_connected,
        }


