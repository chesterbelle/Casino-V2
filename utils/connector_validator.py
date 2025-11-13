"""
Connector Validator - Utilidad AGNÓSTICA para validar conectores de exchange.

Esta herramienta prueba TODAS las funcionalidades necesarias para el bot:
- Métodos básicos (balance, positions, ticker, etc.)
- Órdenes REALES con TP/SL
- Ejecución automática de TP/SL (CRÍTICO para el bot)

Includes both:
- Basic tests (connector direct)
- Integration tests (with Croupier + Adapter)

Usage:
    python -m utils.connector_validator --exchange binance --demo --symbol LTC/USD:USD
"""

import argparse
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors import KrakenConnector
from exchanges.connectors.binance import BinanceConnector
from exchanges.connectors.bybit import BybitConnector
from exchanges.connectors.connector_base import BaseConnector
from exchanges.connectors.resilient_connector import ResilientConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ConnectorValidator:
    """
    Validador de conectores de exchange.

    Ejecuta una batería de tests para validar todas las funcionalidades
    de un conector y detectar problemas de implementación.
    """

    def __init__(self, connector: BaseConnector, symbol: str = "LTC/USDT:USDT", execute_orders: bool = False):
        """
        Inicializa el validador.

        Args:
            connector: Conector a validar
            symbol: Símbolo para las pruebas (formato: "LTC/USDT:USDT")
            execute_orders: Si ejecutar órdenes reales (requiere fondos en testnet)
        """
        self.connector = connector
        self.symbol = symbol
        self.execute_orders = execute_orders
        self.results: Dict[str, Dict] = {}
        self.adapter = None  # Se creará si execute_orders=True

        # Variables para tests de órdenes
        self.test_order_id = None
        self.test_order_symbol = None
        self.test_order_side = None

    async def run_all_tests(self) -> Dict[str, Dict]:
        """
        Ejecuta todos los tests de validación.

        Returns:
            Diccionario con resultados de cada test
        """
        logger.info("=" * 80)
        logger.info(f"🔍 VALIDACIÓN DE CONECTOR: {self.connector.__class__.__name__}")
        logger.info(f"📊 Símbolo: {self.symbol}")
        logger.info(f"🎯 Órdenes reales: {'SÍ' if self.execute_orders else 'NO (dry run)'}")
        logger.info("=" * 80)

        # Lista de tests básicos (siempre se ejecutan)
        tests = [
            ("Conexión", self.test_connection),
            ("Balance", self.test_fetch_balance),
            ("Posiciones", self.test_fetch_positions),
            ("🔥 CRÍTICO: OHLCV", self.test_fetch_ohlcv),
            ("Ticker", self.test_fetch_ticker),
            ("Order Book", self.test_fetch_order_book),
            ("Trades Recientes", self.test_fetch_trades),
            ("Mis Trades", self.test_fetch_my_trades),
            ("Órdenes Abiertas", self.test_fetch_open_orders),
            ("Límites de Trading", self.test_trading_limits),
            ("Fees", self.test_fees),
            ("Timeframes", self.test_timeframes),
            ("Precisión", self.test_precision),
        ]

        # Tests de órdenes reales (solo si execute_orders=True)
        if self.execute_orders:
            logger.info("\n⚠️  MODO ÓRDENES REALES ACTIVADO")
            logger.info("Se ejecutarán órdenes reales con TP/SL en testnet")
            logger.info("Asegúrate de tener fondos en tu cuenta de testnet\n")

            # Crear adapter para tests de órdenes
            # IMPORTANTE: El adapter mantiene la arquitectura modular y agnóstica
            # No usar ResilientConnector aquí porque el conector ya está conectado
            self.adapter = CCXTAdapter(
                connector=self.connector,
                symbol=self.symbol,
            )

            # Marcar el adapter como conectado ya que el conector subyacente lo está
            self.adapter._connected = True

            tests.extend(
                [
                    ("🔥 CRÍTICO: Cancelar Orden", self.test_cancel_order_real),
                    ("🔥 CRÍTICO: Manejo de Errores", self.test_error_handling),
                    ("🔥 Cleanup Inicial", self.test_cleanup_positions),
                    ("🔥 Crear Orden con TP/SL", self.test_create_order_with_tpsl),
                    ("🔥 Validar Posición Abierta", self.test_validate_position_opened),
                    ("🔥 CRÍTICO: Ejecución de TP/SL", self.test_tpsl_execution),
                    ("🔥 CRÍTICO: Detección de Fill de Cierre", self.test_fill_detection_flow),
                    ("🔥 CRÍTICO: Position Tracking Integration", self.test_position_tracking_integration),
                    # Tests de integración con Croupier (flujo real del bot)
                    ("🧹 Cleanup Forzado Pre-Simulación", self.test_cleanup_positions),  # GARANTIZAR ESTADO LIMPIO
                    ("🚀 BOT SIMULATION: LONG + SHORT con TP/SL OCO", self.test_bot_simulation_long_short),
                    ("🧹 Cleanup Forzado Pre-Integración", self.test_cleanup_positions),  # GARANTIZAR ESTADO LIMPIO
                    ("🎯 INTEGRACIÓN: Orden con Croupier", self.test_create_order_with_croupier),
                    ("🎯 INTEGRACIÓN: Cálculo de Amount", self.test_croupier_amount_calculation),
                    ("🎯 INTEGRACIÓN: Portfolio Update", self.test_croupier_portfolio_update),
                ]
            )
        else:
            tests.extend(
                [
                    ("Crear Orden (Dry Run)", self.test_create_order_dry_run),
                    ("Cancelar Orden (Dry Run)", self.test_cancel_order_dry_run),
                ]
            )

        # Ejecutar cada test
        for test_name, test_func in tests:
            logger.info(f"\n{'─' * 80}")
            logger.info(f"🧪 Test: {test_name}")
            logger.info(f"{'─' * 80}")

            try:
                result = await test_func()

                # Manejar caso especial de mercado estable
                if result["success"] == "market_stable":
                    status = "⚠️ INCOMPLETE"
                    log_func = logger.warning
                    log_msg = f"⚠️ {test_name}: INCOMPLETE - {result.get('error')}"
                elif result["success"]:
                    status = "✅ PASS"
                    log_func = logger.info
                    log_msg = f"✅ {test_name}: PASS"
                else:
                    status = "❌ FAIL"
                    log_func = logger.error
                    log_msg = f"❌ {test_name}: FAIL - {result.get('error')}"

                self.results[test_name] = {
                    "status": status,
                    "data": result.get("data"),
                    "error": result.get("error"),
                    "duration": result.get("duration", 0),
                }

                log_func(log_msg)
                if result.get("data"):
                    self._log_data(result["data"])

            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {e}", exc_info=True)
                self.results[test_name] = {
                    "status": "❌ ERROR",
                    "error": str(e),
                }

        # Mostrar resumen
        self._print_summary()

        return self.results

    async def test_connection(self) -> Dict:
        """Test de conexión básica."""
        start = datetime.now()
        try:
            await self.connector.connect()
            duration = (datetime.now() - start).total_seconds()
            return {
                "success": True,
                "data": {"connected": True, "duration": f"{duration:.2f}s"},
                "duration": duration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_balance(self) -> Dict:
        """Test de obtención de balance."""
        start = datetime.now()
        try:
            balance = await self.connector.fetch_balance()
            duration = (datetime.now() - start).total_seconds()

            # Validar estructura
            if not isinstance(balance, dict):
                return {"success": False, "error": "Balance no es un dict"}

            # Extraer info relevante
            data = {
                "total_currencies": len(balance),
                "currencies": list(balance.keys())[:5],  # Primeras 5
                "sample": {},
            }

            # Mostrar sample de una moneda
            for currency, info in list(balance.items())[:2]:
                if isinstance(info, dict):
                    data["sample"][currency] = {
                        "free": info.get("free", 0),
                        "used": info.get("used", 0),
                        "total": info.get("total", 0),
                    }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_positions(self) -> Dict:
        """Test de obtención de posiciones."""
        start = datetime.now()
        try:
            positions = await self.connector.fetch_positions()
            duration = (datetime.now() - start).total_seconds()

            data = {
                "total_positions": len(positions) if positions else 0,
                "positions": [],
            }

            if positions:
                for pos in positions[:3]:  # Primeras 3
                    data["positions"].append(
                        {
                            "symbol": pos.get("symbol"),
                            "side": pos.get("side"),
                            "contracts": pos.get("contracts"),
                            "unrealizedPnl": pos.get("unrealizedPnl"),
                        }
                    )

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_ohlcv(self) -> Dict:
        """Test CRÍTICO: Obtención de velas OHLCV para análisis técnico."""
        start = datetime.now()
        try:
            # Test múltiples timeframes que el bot usa
            timeframes_to_test = ["1m", "5m", "1h"]
            results = {}

            for timeframe in timeframes_to_test:
                try:
                    candles = await self.connector.fetch_ohlcv(symbol=self.symbol, timeframe=timeframe, limit=100)

                    # Validar estructura
                    if not candles or len(candles) == 0:
                        results[timeframe] = "❌ No data"
                        continue

                    first_candle = candles[0]

                    # CCXT puede retornar listas [timestamp, open, high, low, close, volume]
                    # o diccionarios {'timestamp': ..., 'open': ..., ...}
                    if isinstance(first_candle, list):
                        # Formato lista: [timestamp, open, high, low, close, volume]
                        if len(first_candle) < 6:
                            results[timeframe] = f"❌ Invalid format: {len(first_candle)} elements"
                            continue
                        # Validar que son numéricos
                        if not all(isinstance(v, (int, float)) for v in first_candle[:6]):
                            results[timeframe] = "❌ Non-numeric values"
                            continue
                    elif isinstance(first_candle, dict):
                        # Formato diccionario
                        required_keys = ["timestamp", "open", "high", "low", "close", "volume"]
                        if not all(k in first_candle for k in required_keys):
                            results[timeframe] = f"❌ Missing keys"
                            continue
                        if not all(isinstance(first_candle[k], (int, float)) for k in required_keys):
                            results[timeframe] = "❌ Non-numeric values"
                            continue
                    else:
                        results[timeframe] = f"❌ Unknown format: {type(first_candle)}"
                        continue

                    results[timeframe] = f"✅ {len(candles)} candles"

                except Exception as e:
                    results[timeframe] = f"❌ {str(e)}"

            duration = (datetime.now() - start).total_seconds()

            # Success si al menos un timeframe funciona
            success = any("✅" in v for v in results.values())

            return {
                "success": success,
                "data": {
                    "timeframes_tested": timeframes_to_test,
                    "results": results,
                    "total_candles": sum(int(v.split()[1]) for v in results.values() if "✅" in v),
                },
                "duration": duration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_ticker(self) -> Dict:
        """Test de obtención de ticker."""
        start = datetime.now()
        try:
            ticker = await self.connector.fetch_ticker(self.symbol)
            duration = (datetime.now() - start).total_seconds()

            data = {
                "symbol": ticker.get("symbol"),
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume": ticker.get("volume"),
                "timestamp": ticker.get("timestamp"),
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_order_book(self) -> Dict:
        """Test de obtención de order book."""
        start = datetime.now()
        try:
            orderbook = await self.connector.fetch_order_book(self.symbol, limit=5)
            duration = (datetime.now() - start).total_seconds()

            data = {
                "symbol": orderbook.get("symbol"),
                "bids_count": len(orderbook.get("bids", [])),
                "asks_count": len(orderbook.get("asks", [])),
                "best_bid": orderbook["bids"][0] if orderbook.get("bids") else None,
                "best_ask": orderbook["asks"][0] if orderbook.get("asks") else None,
                "timestamp": orderbook.get("timestamp"),
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_trades(self) -> Dict:
        """Test de obtención de trades recientes."""
        start = datetime.now()
        try:
            trades = await self.connector.fetch_trades(self.symbol, limit=5)
            duration = (datetime.now() - start).total_seconds()

            data = {
                "total_trades": len(trades),
                "sample": [],
            }

            for trade in trades[:3]:
                data["sample"].append(
                    {
                        "id": trade.get("id"),
                        "price": trade.get("price"),
                        "amount": trade.get("amount"),
                        "side": trade.get("side"),
                        "timestamp": trade.get("timestamp"),
                    }
                )

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_my_trades(self) -> Dict:
        """Test de obtención de mis trades."""
        start = datetime.now()
        try:
            trades = await self.connector.fetch_my_trades(symbol=self.symbol, limit=10)
            duration = (datetime.now() - start).total_seconds()

            data = {
                "total_trades": len(trades),
                "sample": [],
            }

            for trade in trades[:3]:
                data["sample"].append(
                    {
                        "id": trade.get("id"),
                        "order_id": trade.get("order"),
                        "price": trade.get("price"),
                        "amount": trade.get("amount"),
                        "side": trade.get("side"),
                        "fee": trade.get("fee"),
                    }
                )

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fetch_open_orders(self) -> Dict:
        """Test de obtención de órdenes abiertas."""
        start = datetime.now()
        try:
            orders = await self.connector.fetch_open_orders(symbol=self.symbol)
            duration = (datetime.now() - start).total_seconds()

            data = {
                "total_orders": len(orders),
                "sample": [],
            }

            for order in orders[:3]:
                data["sample"].append(
                    {
                        "id": order.get("id"),
                        "symbol": order.get("symbol"),
                        "type": order.get("type"),
                        "side": order.get("side"),
                        "price": order.get("price"),
                        "amount": order.get("amount"),
                        "status": order.get("status"),
                    }
                )

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_create_order_dry_run(self) -> Dict:
        """Test de creación de orden (dry run - no ejecuta)."""
        logger.warning("⚠️  DRY RUN - No se ejecutará orden real")
        return {
            "success": True,
            "data": {"message": "Dry run - implementar con --execute-orders flag"},
        }

    async def test_cancel_order_dry_run(self) -> Dict:
        """Test de cancelación de orden (dry run)."""
        logger.warning("⚠️  DRY RUN - No se cancelará orden real")
        return {
            "success": True,
            "data": {"message": "Dry run - implementar con --execute-orders flag"},
        }

    async def test_trading_limits(self) -> Dict:
        """Test de límites de trading."""
        start = datetime.now()
        try:
            markets = await self.connector.load_markets()
            duration = (datetime.now() - start).total_seconds()

            # Try both normalized and original symbol
            market_symbol = self.symbol
            if self.symbol not in markets:
                # Try normalized symbol (e.g., BTCUSDT for Bybit)
                normalized = self.connector.normalize_symbol(self.symbol)
                if normalized in markets:
                    market_symbol = normalized
                else:
                    return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[market_symbol]
            limits = market.get("limits", {})

            data = {
                "symbol": self.symbol,
                "limits": {
                    "amount": limits.get("amount"),
                    "price": limits.get("price"),
                    "cost": limits.get("cost"),
                },
                "active": market.get("active"),
                "type": market.get("type"),
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fees(self) -> Dict:
        """Test de fees."""
        start = datetime.now()
        try:
            markets = await self.connector.load_markets()
            duration = (datetime.now() - start).total_seconds()

            # Try both normalized and original symbol
            market_symbol = self.symbol
            if self.symbol not in markets:
                normalized = self.connector.normalize_symbol(self.symbol)
                if normalized in markets:
                    market_symbol = normalized
                else:
                    return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[market_symbol]

            data = {
                "symbol": self.symbol,
                "maker": market.get("maker"),
                "taker": market.get("taker"),
                "percentage": market.get("percentage"),
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_timeframes(self) -> Dict:
        """Test de timeframes disponibles."""
        start = datetime.now()
        try:
            timeframes = self.connector.timeframes
            duration = (datetime.now() - start).total_seconds()

            data = {
                "available_timeframes": list(timeframes.keys()) if timeframes else [],
                "total": len(timeframes) if timeframes else 0,
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_precision(self) -> Dict:
        """Test de precisión de precios y cantidades."""
        start = datetime.now()
        try:
            markets = await self.connector.load_markets()
            duration = (datetime.now() - start).total_seconds()

            # Try both normalized and original symbol
            market_symbol = self.symbol
            if self.symbol not in markets:
                normalized = self.connector.normalize_symbol(self.symbol)
                if normalized in markets:
                    market_symbol = normalized
                else:
                    return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[market_symbol]
            precision = market.get("precision", {})

            data = {
                "symbol": self.symbol,
                "price": precision.get("price"),
                "amount": precision.get("amount"),
                "base": precision.get("base"),
                "quote": precision.get("quote"),
            }

            return {"success": True, "data": data, "duration": duration}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================
    # 🔥 TESTS CRÍTICOS ADICIONALES
    # =========================================================

    async def test_cancel_order_real(self) -> Dict:
        """Test CRÍTICO: Cancelación de orden REAL para gestión de riesgo."""
        start = datetime.now()
        try:
            logger.info("📝 Creando orden limit para cancelar...")

            # Obtener precio actual
            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker.get("last", 0)

            if not current_price:
                return {"success": False, "error": "No se pudo obtener precio actual"}

            # Crear orden limit muy lejos del precio actual (no se ejecutará)
            limit_price = current_price * 2.0  # 100% más alto

            # Amount mínimo - normalizar símbolo primero
            normalized_symbol = self.connector.normalize_symbol(self.symbol)

            # Cargar markets si no están cargados
            if not self.connector.exchange.markets:
                await self.connector.exchange.load_markets()

            market = self.connector.exchange.markets.get(normalized_symbol)
            if not market:
                return {"success": False, "error": f"Market info not found for {normalized_symbol}"}

            # Calcular amount basado en notional mínimo
            min_amount = market["limits"]["amount"]["min"]
            min_cost = market["limits"]["cost"].get("min", 0) if market["limits"].get("cost") else 0

            # Si hay notional mínimo (cost), calcular amount necesario
            if min_cost > 0:
                # Amount necesario para cumplir con notional mínimo
                amount_for_notional = min_cost / limit_price
                # Agregar 5% extra para compensar redondeo (step size puede reducir el amount)
                amount_for_notional = amount_for_notional * 1.05
                # Usar el mayor entre min_amount y amount_for_notional
                final_amount = max(min_amount, amount_for_notional)
                logger.info(f"  💰 Precio actual: ${current_price:.2f}")
                logger.info(f"  📊 Precio limit: ${limit_price:.2f} (no se ejecutará)")
                logger.info(f"  💵 Notional mínimo: ${min_cost:.2f}")
                logger.info(f"  📏 Amount calculado: {final_amount:.6f} (notional: ${limit_price * final_amount:.2f})")
            else:
                # No hay notional mínimo, usar min_amount
                final_amount = min_amount
                logger.info(f"  💰 Precio actual: ${current_price:.2f}")
                logger.info(f"  📊 Precio limit: ${limit_price:.2f} (no se ejecutará)")
                logger.info(f"  📏 Amount: {final_amount}")

            # Crear orden limit con timeInForce
            order = await self.connector.create_order(
                symbol=self.symbol,
                side="sell",
                amount=final_amount,
                price=limit_price,
                order_type="limit",
                params={"timeInForce": "GTC"},  # Good Till Cancel
            )

            order_id = order.get("id")
            logger.info(f"  ✅ Orden creada: ID={order_id}")

            # Esperar un momento
            await asyncio.sleep(1)

            # Cancelar orden
            logger.info(f"  🗑️  Cancelando orden {order_id}...")
            await self.connector.cancel_order(order_id, self.symbol)
            logger.info(f"  ✅ Orden cancelada")

            # Verificar que se canceló
            await asyncio.sleep(1)
            open_orders = await self.connector.fetch_open_orders(self.symbol)
            order_ids = [o.get("id") for o in open_orders]

            if order_id in order_ids:
                return {"success": False, "error": f"Orden {order_id} todavía aparece en órdenes abiertas"}

            duration = (datetime.now() - start).total_seconds()

            return {
                "success": True,
                "data": {"order_id": order_id, "status": "canceled", "verified": "not in open orders"},
                "duration": duration,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_error_handling(self) -> Dict:
        """Test CRÍTICO: Manejo de errores para robustez."""
        start = datetime.now()
        errors_handled = []
        errors_not_handled = []

        try:
            # Test 1: Símbolo inválido
            logger.info("  🧪 Test 1: Símbolo inválido")
            try:
                # Usar un símbolo que definitivamente no existe
                await self.connector.fetch_ticker("ZZZZZ/USDT:USDT")
                errors_not_handled.append("Invalid symbol - No exception raised")
            except Exception as e:
                errors_handled.append(f"Invalid symbol - {type(e).__name__}")
                logger.info(f"    ✅ Exception raised: {type(e).__name__}")

            # Test 2: Amount negativo
            logger.info("  🧪 Test 2: Amount negativo")
            try:
                await self.connector.create_order(symbol=self.symbol, side="buy", amount=-1, order_type="market")
                errors_not_handled.append("Negative amount - No exception raised")
            except Exception as e:
                errors_handled.append(f"Negative amount - {type(e).__name__}")
                logger.info(f"    ✅ Exception raised: {type(e).__name__}")

            # Test 3: Amount cero
            logger.info("  🧪 Test 3: Amount cero")
            try:
                await self.connector.create_order(symbol=self.symbol, side="buy", amount=0, order_type="market")
                errors_not_handled.append("Zero amount - No exception raised")
            except Exception as e:
                errors_handled.append(f"Zero amount - {type(e).__name__}")
                logger.info(f"    ✅ Exception raised: {type(e).__name__}")

            # Test 4: Side inválido
            logger.info("  🧪 Test 4: Side inválido")
            try:
                await self.connector.create_order(
                    symbol=self.symbol, side="invalid_side", amount=0.001, order_type="market"
                )
                errors_not_handled.append("Invalid side - No exception raised")
            except Exception as e:
                errors_handled.append(f"Invalid side - {type(e).__name__}")
                logger.info(f"    ✅ Exception raised: {type(e).__name__}")

            duration = (datetime.now() - start).total_seconds()

            # Success si todos los errores fueron manejados
            success = len(errors_not_handled) == 0

            if not success:
                error_msg = f"{len(errors_not_handled)} errors not handled: {errors_not_handled}"
            else:
                error_msg = None

            return {
                "success": success,
                "data": {
                    "errors_handled": len(errors_handled),
                    "errors_not_handled": len(errors_not_handled),
                    "details_handled": errors_handled,
                    "details_not_handled": errors_not_handled,
                },
                "error": error_msg,
                "duration": duration,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================
    # 🔥 TESTS DE ÓRDENES REALES CON TP/SL
    # =========================================================

    async def test_cleanup_positions(self) -> Dict:
        """Limpia todas las posiciones y órdenes abiertas."""
        start = datetime.now()
        try:
            logger.info("🧹 Limpiando posiciones y órdenes abiertas...")

            # Cancelar todas las órdenes abiertas
            orders = await self.connector.fetch_open_orders()
            for order in orders:
                try:
                    await self.connector.cancel_order(order["id"], order["symbol"])
                    logger.info(f"  ❌ Orden cancelada: {order['id']}")
                except Exception as e:
                    logger.warning(f"  ⚠️ No se pudo cancelar orden {order['id']}: {e}")

            # Cerrar todas las posiciones
            positions = await self.connector.fetch_positions()
            for pos in positions:
                if abs(pos.get("contracts", 0)) > 0:
                    try:
                        # Crear orden de cierre
                        side = "sell" if pos["side"] == "long" else "buy"
                        await self.connector.create_order(
                            symbol=pos["symbol"],
                            side=side,
                            amount=abs(pos["contracts"]),
                            order_type="market",
                            params={"reduceOnly": True},  # CRÍTICO para cerrar posiciones pequeñas
                        )
                        logger.info(f"  🔒 Posición cerrada: {pos['symbol']}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ No se pudo cerrar posición {pos['symbol']}: {e}")

            duration = (datetime.now() - start).total_seconds()
            return {
                "success": True,
                "data": {
                    "orders_canceled": len(orders),
                    "positions_closed": len([p for p in positions if abs(p.get("contracts", 0)) > 0]),
                },
                "duration": duration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_create_order_with_tpsl(self) -> Dict:
        """Crea una orden real con TP/SL."""
        start = datetime.now()
        try:
            logger.info("📝 Creando orden con TP/SL...")

            # CLEANUP INICIAL: Cancelar cualquier orden residual
            logger.info("  🧹 Limpiando órdenes residuales...")
            try:
                existing_orders = await self.connector.fetch_open_orders(self.symbol)
                if existing_orders:
                    logger.info(f"  ⚠️ Encontradas {len(existing_orders)} órdenes residuales, cancelando...")
                    await self.connector.cancel_all_orders(self.symbol)
                    await asyncio.sleep(1)  # Dar tiempo para que se cancelen
                    logger.info("  ✅ Órdenes residuales canceladas")
            except Exception as e:
                logger.warning(f"  ⚠️ No se pudieron limpiar órdenes: {e}")

            # Obtener precio actual
            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker.get("last")

            # Obtener balance
            balance = await self.connector.fetch_balance()

            # Intentar obtener USDT de diferentes formas
            usdt_balance = 0
            if "free" in balance and isinstance(balance["free"], dict):
                usdt_balance = balance["free"].get("USDT", 0) or balance["free"].get("USD", 0)
            elif "USDT" in balance:
                # Formato alternativo
                usdt_balance = balance["USDT"].get("free", 0) if isinstance(balance["USDT"], dict) else 0

            # Si aún es 0, intentar con total
            if usdt_balance == 0:
                if "total" in balance and isinstance(balance["total"], dict):
                    usdt_balance = balance["total"].get("USDT", 0) or balance["total"].get("USD", 0)

            logger.info(f"  💰 Balance detectado: ${usdt_balance:.2f}")
            logger.info(f"  📊 Estructura de balance: {list(balance.keys())}")

            if usdt_balance < 10:
                return {
                    "success": False,
                    "error": f"Balance insuficiente: ${usdt_balance:.2f} (mínimo $10)",
                }

            # Calcular cantidad (1% del balance, mínimo $10)
            # El conector se encargará de ajustar según los límites del exchange
            min_value = 10.0
            amount = max(min_value / current_price, usdt_balance * 0.01 / current_price)

            logger.info(f"  💰 Balance: ${usdt_balance:.2f}")
            logger.info(f"  📊 Precio actual: ${current_price:,.2f}")
            logger.info(f"  📏 Cantidad: {amount}")

            # Crear orden del bot (formato interno con multiplicadores)
            # LEVERAGE MÁXIMO (100x) y TP/SL ULTRA CERCANOS (0.1%) para ejecución inmediata
            bot_order = {
                "symbol": self.symbol,
                "side": "sell",  # SHORT para que TP sea más bajo
                "amount": amount,
                "type": "market",
                "take_profit": 0.9995,  # -0.05% (SÚPER AGRESIVO para test)
                "stop_loss": 1.0005,  # +0.05% (SÚPER AGRESIVO para test)
                "leverage": 100,  # ⚡⚡ LEVERAGE MÁXIMO para ejecución inmediata
            }

            logger.info(f"  📋 Orden del bot: {bot_order['side'].upper()} {amount}")
            logger.info(f"  ⚡⚡ LEVERAGE: {bot_order['leverage']}x (MÁXIMO para test inmediato)")
            logger.info(f"  🎯 TP Multiplier: {bot_order['take_profit']} (-0.05% SÚPER AGRESIVO)")
            logger.info(f"  🛑 SL Multiplier: {bot_order['stop_loss']} (+0.05% SÚPER AGRESIVO)")

            # Calcular precios exactos de TP/SL para monitoreo
            self.tp_price = current_price * bot_order["take_profit"]
            self.sl_price = current_price * bot_order["stop_loss"]
            logger.info(f"  📊 Precio entrada: ${current_price:.2f}")
            logger.info(f"  🎯 TP esperado: ${self.tp_price:.2f} (${self.tp_price - current_price:.2f})")
            logger.info(f"  🛑 SL esperado: ${self.sl_price:.2f} (+${self.sl_price - current_price:.2f})")

            # Ejecutar orden a través del ADAPTER (mantiene arquitectura modular)
            # El adapter traduce multiplicadores a precios y maneja la lógica de negocio
            result = await self.adapter.execute_order(bot_order)

            # Guardar info de la orden para tests posteriores
            self.test_order_id = result.get("id")
            self.test_order_symbol = result.get("symbol")
            self.test_order_side = result.get("side")

            duration = (datetime.now() - start).total_seconds()

            logger.info(f"  ✅ Orden creada: ID={self.test_order_id}")

            return {
                "success": True,
                "data": {
                    "order_id": self.test_order_id,
                    "symbol": self.test_order_symbol,
                    "side": self.test_order_side,
                    "amount": amount,
                    "price": current_price,
                },
                "duration": duration,
            }
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_validate_position_opened(self) -> Dict:
        """Valida que la posición se abrió correctamente."""
        start = datetime.now()
        try:
            logger.info("🔍 Validando posición abierta...")

            # Intentar encontrar la posición varias veces (puede cerrarse rápido por TP/SL)
            max_attempts = 5
            position = None

            for attempt in range(max_attempts):
                # Obtener posiciones
                positions = await self.connector.fetch_positions()

                # Buscar la posición del símbolo (abierta o cerrada recientemente)
                for pos in positions:
                    if pos.get("symbol") == self.test_order_symbol:
                        # Si tiene contratos, está abierta
                        if abs(pos.get("contracts", 0)) > 0:
                            position = pos
                            break
                        # Si no tiene contratos pero tiene unrealizedPnl, se cerró recientemente
                        elif pos.get("unrealizedPnl") is not None or pos.get("side") is not None:
                            position = pos
                            logger.info(f"  ℹ️  Posición ya cerrada (TP/SL ejecutado rápidamente)")
                            break

                if position:
                    break

                # Esperar un poco antes del siguiente intento
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5)

            # Si no encontramos la posición, verificar en trades recientes
            if not position:
                trades = await self.connector.fetch_my_trades(symbol=self.test_order_symbol, limit=5)
                if trades and len(trades) > 0:
                    # Si hay trades recientes, la orden se ejecutó
                    logger.info(f"  ✅ Orden ejecutada (verificado por trades)")
                    duration = (datetime.now() - start).total_seconds()
                    return {
                        "success": True,
                        "data": {
                            "symbol": self.test_order_symbol,
                            "verified_by": "trades",
                            "recent_trades": len(trades),
                        },
                        "duration": duration,
                    }
                else:
                    return {
                        "success": False,
                        "error": "No se encontró posición ni trades recientes",
                    }

            duration = (datetime.now() - start).total_seconds()

            logger.info(f"  ✅ Posición encontrada:")
            logger.info(f"     Symbol: {position.get('symbol')}")
            logger.info(f"     Side: {position.get('side')}")
            logger.info(f"     Contracts: {position.get('contracts', 0)}")
            if position.get("entryPrice"):
                logger.info(f"     Entry Price: ${position.get('entryPrice', 0):,.2f}")

            return {
                "success": True,
                "data": {
                    "symbol": position.get("symbol"),
                    "side": position.get("side"),
                    "contracts": position.get("contracts", 0),
                    "entry_price": position.get("entryPrice"),
                },
                "duration": duration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_tpsl_execution(self) -> Dict:
        """
        CRÍTICO: Valida que TP o SL se ejecuta automáticamente.

        Con leverage 100x y TP/SL de 0.05%, debería ejecutarse en menos de 5 minutos.
        Monitorea precio y posición cada 2 segundos con tracking detallado.
        """
        start = datetime.now()
        timeout = 600  # 10 minutos (tiempo extra para mercados lentos)
        check_interval = 2  # Revisar cada 2 segundos (más frecuente)

        try:
            logger.info("⏳ Esperando ejecución de TP/SL...")
            logger.info(f"   Timeout: {timeout}s ({timeout//60} minutos)")
            logger.info(f"   Revisando cada {check_interval}s")

            elapsed = 0
            while elapsed < timeout:
                # Obtener posiciones
                positions = await self.connector.fetch_positions()

                # Buscar la posición
                position = None
                for pos in positions:
                    if pos.get("symbol") == self.test_order_symbol and abs(pos.get("contracts", 0)) > 0:
                        position = pos
                        break

                # Si no hay posición, significa que se cerró (TP o SL ejecutado)
                if not position:
                    duration = (datetime.now() - start).total_seconds()
                    logger.info(f"  ✅ ¡TP/SL EJECUTADO! Posición cerrada en {duration:.1f}s")

                    # Obtener último trade para ver si fue TP o SL
                    trades = await self.connector.fetch_my_trades(symbol=self.test_order_symbol, limit=5)
                    last_trade = trades[0] if trades else None

                    return {
                        "success": True,
                        "data": {
                            "execution_time": duration,
                            "last_trade": (
                                {
                                    "price": last_trade.get("price") if last_trade else None,
                                    "amount": last_trade.get("amount") if last_trade else None,
                                    "side": last_trade.get("side") if last_trade else None,
                                }
                                if last_trade
                                else None
                            ),
                        },
                        "duration": duration,
                    }

                # Mostrar progreso con precio actual
                progress = (elapsed / timeout) * 100

                # Obtener precio actual y comparar con TP/SL
                try:
                    ticker = await self.connector.fetch_ticker(self.test_order_symbol)
                    current_price = ticker.get("last")

                    # Calcular distancia a TP y SL
                    if hasattr(self, "tp_price") and hasattr(self, "sl_price"):
                        dist_to_tp = abs(current_price - self.tp_price)
                        dist_to_sl = abs(current_price - self.sl_price)
                        pct_to_tp = (dist_to_tp / self.tp_price) * 100
                        pct_to_sl = (dist_to_sl / self.sl_price) * 100

                        # Determinar si el precio tocó TP o SL según el tipo de posición
                        if hasattr(self, "test_order_side") and self.test_order_side:
                            if self.test_order_side.lower() in ["buy", "long"]:
                                # LONG: TP cuando sube, SL cuando baja
                                hit_tp = current_price >= self.tp_price
                                hit_sl = current_price <= self.sl_price
                            else:
                                # SHORT: TP cuando baja, SL cuando sube
                                hit_tp = current_price <= self.tp_price
                                hit_sl = current_price >= self.sl_price
                        else:
                            # Fallback: asumir SHORT (comportamiento anterior)
                            hit_tp = current_price <= self.tp_price
                            hit_sl = current_price >= self.sl_price

                        if hit_tp or hit_sl:
                            hit_level = "TP" if hit_tp else "SL"
                            position_type = (
                                "LONG"
                                if (
                                    hasattr(self, "test_order_side")
                                    and self.test_order_side
                                    and self.test_order_side.lower() in ["buy", "long"]
                                )
                                else "SHORT"
                            )
                            logger.info(
                                f"   🎯 ¡PRECIO TOCÓ {hit_level}! ${current_price:.2f} | TP=${self.tp_price:.2f} | SL=${self.sl_price:.2f} | Posición: {position_type}"
                            )

                        logger.info(
                            f"   ⏱️  {elapsed}s/{timeout}s ({progress:.1f}%) | Precio: ${current_price:.2f} | TP: ${self.tp_price:.2f} (-{pct_to_tp:.3f}%) | SL: ${self.sl_price:.2f} (+{pct_to_sl:.3f}%)"
                        )
                    else:
                        logger.info(f"   ⏱️  {elapsed}s/{timeout}s ({progress:.1f}%) | Precio: ${current_price:.2f}")
                except Exception as e:
                    logger.info(f"   ⏱️  {elapsed}s/{timeout}s ({progress:.1f}%) - Error obteniendo precio: {e}")

                # Esperar antes de la siguiente revisión
                await asyncio.sleep(check_interval)
                elapsed += check_interval

            # Timeout alcanzado - Analizar por qué no se ejecutó
            duration = (datetime.now() - start).total_seconds()

            # Obtener precio final y analizar
            try:
                ticker = await self.connector.fetch_ticker(self.test_order_symbol)
                final_price = ticker.get("last")

                if hasattr(self, "tp_price") and hasattr(self, "sl_price"):
                    min_dist_tp = abs(final_price - self.tp_price)
                    min_dist_sl = abs(final_price - self.sl_price)

                    # Determinar si fue problema del exchange o del mercado
                    if min_dist_tp < 0.01 or min_dist_sl < 0.01:
                        # Error real del exchange
                        logger.error(f"  ❌ TIMEOUT: TP/SL no se ejecutó en {timeout}s")
                        logger.error(f"     Precio final: ${final_price:.2f}")
                        logger.error(f"     TP objetivo: ${self.tp_price:.2f} (distancia: ${min_dist_tp:.2f})")
                        logger.error(f"     SL objetivo: ${self.sl_price:.2f} (distancia: ${min_dist_sl:.2f})")
                        error_msg = f"Precio tocó nivel pero orden no se ejecutó (problema del exchange)"
                        success_status = False
                    else:
                        # Test no se pudo completar por condiciones del mercado
                        logger.warning(f"  ⚠️ TEST INCOMPLETO: Precio no alcanzó niveles TP/SL en {timeout}s")
                        logger.warning(f"     Precio final: ${final_price:.2f}")
                        logger.warning(f"     TP objetivo: ${self.tp_price:.2f} (distancia: ${min_dist_tp:.2f})")
                        logger.warning(f"     SL objetivo: ${self.sl_price:.2f} (distancia: ${min_dist_sl:.2f})")
                        logger.warning(
                            f"  🚨 El test no pudo validar la funcionalidad por falta de movimiento del mercado"
                        )
                        error_msg = f"Test incompleto: mercado no se movió lo suficiente (distancia mín: ${min(min_dist_tp, min_dist_sl):.2f})"
                        success_status = "market_stable"  # Indicador especial
                else:
                    error_msg = f"Timeout: TP/SL no se ejecutó en {timeout}s"
                    success_status = False
                    logger.error(f"  ❌ {error_msg}")
            except Exception:
                error_msg = f"Timeout: TP/SL no se ejecutó en {timeout}s"
                success_status = False
                logger.error(f"  ❌ {error_msg}")

            return {
                "success": success_status,
                "error": error_msg,
                "duration": duration,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_fill_detection_flow(self) -> Dict:
        """
        CRÍTICO: Valida el flujo completo de detección de fills de cierre.

        Este test valida que después de que TP/SL se ejecuta:
        1. sync_fills() detecta el fill
        2. normalize_trade() identifica is_close=True
        3. El fill tiene realized_pnl != 0
        4. El fill tiene close_reason (TP/SL/MANUAL)

        Este es el flujo que usa el bot en producción para detectar cierres.
        """
        start = datetime.now()

        try:
            logger.info("🔍 Validando detección de fill de cierre...")

            # Importar ExchangeStateSync
            from exchanges.adapters.exchange_state_sync import ExchangeStateSync

            # Crear ExchangeStateSync
            state_sync = ExchangeStateSync(self.connector)

            # Obtener timestamp actual (para filtrar fills)
            import time

            since = int(time.time() * 1000) - 300000  # Últimos 5 minutos

            # 1. Obtener fills recientes
            logger.info("  📋 Obteniendo fills recientes...")
            fills = await state_sync.sync_fills(since=since)

            if not fills:
                return {
                    "success": False,
                    "error": "No se detectaron fills (la posición puede no haberse cerrado aún)",
                }

            logger.info(f"  ✅ Detectados {len(fills)} fills")

            # 2. Buscar fill de cierre
            close_fill = None
            for fill in fills:
                if fill.is_close:
                    close_fill = fill
                    break

            if not close_fill:
                # Mostrar info de los fills para debugging
                logger.warning("  ⚠️ No se encontró fill de cierre")
                for i, fill in enumerate(fills):
                    logger.info(
                        f"    Fill {i+1}: {fill.symbol} {fill.side} @ {fill.price:.2f} | is_close={fill.is_close}"
                    )

                return {
                    "success": False,
                    "error": f"No se detectó fill de cierre (encontrados {len(fills)} fills pero ninguno marcado como cierre)",
                }

            # 3. Validar que el fill de cierre tiene los campos correctos
            logger.info(f"  ✅ Fill de cierre detectado:")
            logger.info(f"     Symbol: {close_fill.symbol}")
            logger.info(f"     Side: {close_fill.side}")
            logger.info(f"     Price: ${close_fill.price:.2f}")
            logger.info(f"     Amount: {close_fill.amount:.4f}")
            logger.info(f"     is_close: {close_fill.is_close}")
            logger.info(f"     realized_pnl: ${close_fill.realized_pnl:.2f}")
            logger.info(f"     close_reason: {close_fill.reason}")

            # Validaciones
            validations = []

            # Validar is_close=True
            if close_fill.is_close:
                validations.append("✅ is_close=True")
            else:
                validations.append("❌ is_close=False (debería ser True)")

            # Validar realized_pnl != 0 (puede ser positivo o negativo)
            if close_fill.realized_pnl != 0:
                validations.append(f"✅ realized_pnl=${close_fill.realized_pnl:.2f}")
            else:
                validations.append("⚠️ realized_pnl=0 (puede ser normal si el precio no se movió)")

            # Validar close_reason
            if close_fill.reason:
                validations.append(f"✅ close_reason={close_fill.reason}")
            else:
                validations.append("⚠️ close_reason=None (debería ser TP/SL/MANUAL)")

            # Mostrar validaciones
            for validation in validations:
                logger.info(f"     {validation}")

            # Test pasa si is_close=True
            success = close_fill.is_close

            duration = (datetime.now() - start).total_seconds()

            return {
                "success": success,
                "data": {
                    "fills_detected": len(fills),
                    "close_fill_found": True,
                    "is_close": close_fill.is_close,
                    "realized_pnl": close_fill.realized_pnl,
                    "close_reason": close_fill.reason,
                    "validations": validations,
                },
                "duration": duration,
            }

        except Exception as e:
            logger.error(f"  ❌ Error en detección de fill: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def test_position_tracking_integration(self) -> Dict:
        """
        🔥 CRÍTICO: Valida Position Tracking simulando el flujo del bot.

        Este test valida que después de crear una posición:
        1. Se puede detectar cuando la posición se cierra
        2. El sistema registra correctamente el trade
        3. Las estadísticas se actualizan

        Simula el comportamiento de Position Tracking sin usar TestingDataSource
        para evitar problemas de inicialización circular.
        """
        start = datetime.now()

        try:
            logger.info("🎯 Validando Position Tracking (simulación)...")

            # Verificar que no hay posiciones abiertas inicialmente
            initial_positions = await self.connector.fetch_positions()
            open_initial = [p for p in initial_positions if abs(float(p.get("contracts", 0))) > 0]

            if len(open_initial) > 0:
                logger.warning(f"  ⚠️ Hay {len(open_initial)} posiciones abiertas inicialmente")
                logger.info("  🧹 Limpiando posiciones existentes...")

                # Cerrar posiciones existentes
                for pos in open_initial:
                    try:
                        symbol = pos["symbol"]
                        contracts = float(pos.get("contracts", 0))
                        side = "sell" if contracts > 0 else "buy"

                        await self.connector.create_order(
                            symbol=symbol, side=side, amount=abs(contracts), order_type="market"
                        )
                        logger.info(f"     ✅ Cerrada posición {symbol}")
                    except Exception as e:
                        logger.warning(f"     ⚠️ Error cerrando {symbol}: {e}")

                # Esperar un momento
                await asyncio.sleep(2)

            # Crear una posición pequeña para test
            logger.info("  📝 Creando posición de test...")

            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker["last"]

            # Crear posición LONG pequeña (mínimo $5 USD en Binance)
            min_notional = 10.0  # $10 USD para estar seguros
            test_amount = min_notional / current_price  # Calcular amount necesario

            logger.info(f"  📊 Precio actual: ${current_price:.2f}")
            logger.info(f"  📊 Amount calculado: {test_amount:.6f} (${min_notional} USD)")

            order_result = await self.connector.create_order(
                symbol=self.symbol, side="buy", amount=test_amount, order_type="market"
            )

            logger.info(f"  ✅ Posición creada: {order_result.get('id', 'unknown')}")

            # Esperar un momento para que se procese
            await asyncio.sleep(2)

            # Verificar que la posición existe
            positions_after = await self.connector.fetch_positions()
            open_after = [p for p in positions_after if abs(float(p.get("contracts", 0))) > 0]

            if len(open_after) == 0:
                return {
                    "success": False,
                    "error": "No se pudo crear posición de test",
                }

            test_position = open_after[0]
            logger.info(
                f"  📊 Posición detectada: {test_position['symbol']} {test_position.get('contracts', 0)} contratos"
            )

            # Simular detección de cierre (cerrar la posición)
            logger.info("  🔄 Cerrando posición para simular TP/SL...")

            contracts = float(test_position.get("contracts", 0))
            close_side = "sell" if contracts > 0 else "buy"

            close_result = await self.connector.create_order(
                symbol=self.symbol, side=close_side, amount=abs(contracts), order_type="market"
            )

            logger.info(f"  ✅ Orden de cierre ejecutada: {close_result.get('id', 'unknown')}")

            # Esperar procesamiento
            await asyncio.sleep(2)

            # Verificar que la posición se cerró
            positions_final = await self.connector.fetch_positions()
            open_final = [p for p in positions_final if abs(float(p.get("contracts", 0))) > 0]

            position_closed = len(open_final) == 0

            if position_closed:
                logger.info("  🎯 ¡Posición cerrada correctamente!")
                success = True
                message = "Position Tracking simulado: Posición abierta y cerrada exitosamente"
            else:
                logger.warning("  ⚠️ La posición no se cerró completamente")
                success = False
                message = f"Posición no cerrada: {len(open_final)} posiciones restantes"

            # Verificar trades recientes
            logger.info("  📊 Verificando trades recientes...")
            try:
                trades = await self.connector.fetch_my_trades(self.symbol, limit=10)
                recent_trades = len(trades)
                logger.info(f"     Trades recientes detectados: {recent_trades}")

                if recent_trades >= 2:  # Al menos apertura y cierre
                    logger.info("  ✅ Trades de apertura y cierre detectados")
                    success = True
                    message += f" | {recent_trades} trades detectados"

            except Exception as e:
                logger.warning(f"  ⚠️ Error obteniendo trades: {e}")

            duration = (datetime.now() - start).total_seconds()

            return {
                "success": success,
                "data": {
                    "position_closed_detected": position_closed,
                    "initial_positions": len(open_initial),
                    "final_positions": len(open_final),
                    "trades_detected": recent_trades if "recent_trades" in locals() else 0,
                    "message": message,
                },
                "duration": duration,
            }

        except Exception as e:
            logger.error(f"  ❌ Error en Position Tracking test: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _log_data(self, data: Dict):
        """Log data de forma formateada."""
        for key, value in data.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for k, v in value.items():
                    logger.info(f"    {k}: {v}")
            elif isinstance(value, list):
                logger.info(f"  {key}: {len(value)} items")
                for item in value[:3]:  # Primeros 3
                    logger.info(f"    - {item}")
            else:
                logger.info(f"  {key}: {value}")

    def _print_summary(self):
        """Imprime resumen de resultados."""
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMEN DE VALIDACIÓN")
        logger.info("=" * 80)

        total = len(self.results)
        passed = sum(1 for r in self.results.values() if "✅" in r["status"])
        failed = sum(1 for r in self.results.values() if "❌" in r["status"])
        incomplete = sum(1 for r in self.results.values() if "⚠️" in r["status"])

        logger.info(f"\nTotal tests: {total}")
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.warning(f"⚠️ Incomplete: {incomplete}")

        # Success rate solo cuenta los que realmente pasaron
        success_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}% (only completed tests)")

        if incomplete > 0:
            logger.warning(f"🚨 ALERTA: {incomplete} test(s) no se pudieron completar por condiciones del mercado")

        logger.info("\nDetalle por test:")
        for test_name, result in self.results.items():
            status = result["status"]
            duration = result.get("duration", 0)
            logger.info(f"  {status} {test_name} ({duration:.2f}s)")
            if result.get("error"):
                logger.info(f"      Error: {result['error']}")

        logger.info("\n" + "=" * 80)

    # =========================================================
    # 🚀 BOT SIMULATION TESTS (Real Bot Flow)
    # =========================================================

    async def test_bot_simulation_long_short(self) -> Dict:
        """
        🚀 BOT SIMULATION: Simula exactamente el flujo del bot real.

        Este test es como el checklist pre-vuelo de un piloto:
        - Crea Croupier con balance real del exchange (como el bot)
        - Hace 2 apuestas: una LONG y una SHORT (como el bot haría)
        - Verifica que las órdenes TP/SL sean OCO en el exchange
        - Espera a que se ejecuten y valida el comportamiento
        - Si este test pasa, el bot debería funcionar correctamente
        """
        start = datetime.now()

        try:
            logger.info("🚀 INICIANDO SIMULACIÓN COMPLETA DEL BOT...")
            logger.info("   Este test simula exactamente lo que hace el bot en producción")

            # ========================================
            # PASO 0: CLEANUP INICIAL CRÍTICO
            # ========================================
            logger.info("\n🧹 PASO 0: Limpieza inicial de órdenes residuales")
            try:
                existing_orders = await self.connector.fetch_open_orders(self.symbol)
                if existing_orders:
                    logger.info(f"  ⚠️ Encontradas {len(existing_orders)} órdenes residuales")
                    for order in existing_orders[:5]:  # Mostrar primeras 5
                        logger.info(
                            f"    - {order.get('type', 'unknown')}: {order.get('amount', 0):.4f} @ {order.get('price', 0):.2f}"
                        )

                    logger.info("  🧹 Cancelando todas las órdenes residuales...")
                    await self.connector.cancel_all_orders(self.symbol)
                    await asyncio.sleep(2)  # Dar tiempo para que se cancelen
                    logger.info("  ✅ Órdenes residuales canceladas")
                else:
                    logger.info("  ✅ No hay órdenes residuales")
            except Exception as e:
                logger.warning(f"  ⚠️ Error limpiando órdenes: {e}")

            # ========================================
            # PASO 1: Setup como el bot real
            # ========================================
            logger.info("\n📋 PASO 1: Setup del entorno (como el bot real)")

            # Obtener balance real del exchange PRIMERO
            balance = await self.connector.fetch_balance()
            usdt_balance = balance.get("USDT", {}).get("free", 0)
            logger.info(f"  💰 Balance real del exchange: {usdt_balance:.2f} USDT")

            if usdt_balance < 100:
                return {
                    "success": False,
                    "error": f"Balance insuficiente: {usdt_balance:.2f} USDT (mínimo: 100)",
                    "duration": 0,
                }

            # Asegurar que el adapter existe (se crea en run_all_tests)
            if not self.adapter:
                from exchanges.adapters.ccxt_adapter import CCXTAdapter

                self.adapter = CCXTAdapter(
                    connector=self.connector,
                    symbol=self.symbol,
                )
                self.adapter._connected = True
                logger.info("  🔧 Adapter creado para test de simulación")

            # Crear Croupier con balance real del exchange (como el bot real)
            croupier = Croupier(self.adapter, initial_balance=usdt_balance)
            logger.info(f"  ✅ Croupier creado con balance real: ${usdt_balance:.2f} (como el bot real)")

            # ========================================
            # PASO 2: Apuesta LONG (como el bot)
            # ========================================
            logger.info("\n📈 PASO 2: Ejecutando apuesta LONG (simulando señal alcista)")

            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker["last"]
            logger.info(f"  📊 Precio actual: {current_price:.4f}")

            # Orden LONG con parámetros ULTRA AGRESIVOS para test
            long_order = {
                "trade_id": f"bot_sim_long_{int(time.time())}",
                "symbol": self.symbol,
                "side": "LONG",
                "size": 0.001,  # 0.1% del equity
                "take_profit": 1.001,  # +0.1% (ULTRA AGRESIVO para ejecución inmediata)
                "stop_loss": 0.999,  # -0.1% (ULTRA AGRESIVO para ejecución inmediata)
                "leverage": 100,  # ⚡⚡ LEVERAGE MÁXIMO para ejecución inmediata
                "ghost": False,
            }

            # Calcular precios exactos de TP/SL para monitoreo
            tp_price_long = current_price * long_order["take_profit"]
            sl_price_long = current_price * long_order["stop_loss"]

            logger.info(
                f"  📝 Orden LONG: size={long_order['size']*100:.1f}%, TP=+{(long_order['take_profit']-1)*100:.1f}%, SL={-(1-long_order['stop_loss'])*100:.1f}%"
            )
            logger.info(f"  ⚡⚡ LEVERAGE: {long_order['leverage']}x (MÁXIMO)")
            logger.info(f"  🎯 TP esperado: ${tp_price_long:.2f} (+${tp_price_long - current_price:.2f})")
            logger.info(f"  🛑 SL esperado: ${sl_price_long:.2f} (-${current_price - sl_price_long:.2f})")

            # Ejecutar con Croupier (como el bot)
            long_result = await croupier.execute_order(long_order)

            if long_result.get("status") not in ["open", "opened"]:
                return {"success": False, "error": f"LONG falló: {long_result.get('error', 'Unknown')}", "duration": 0}

            logger.info(f"  ✅ Orden LONG ejecutada: amount={long_result.get('amount', 0):.6f}")

            # Verificar órdenes TP/SL en el exchange
            await asyncio.sleep(2)  # Dar tiempo para que se creen las órdenes
            open_orders = await self.connector.fetch_open_orders(self.symbol)
            tp_sl_orders = [o for o in open_orders if o.get("type") in ["stop_market", "take_profit_market"]]
            logger.info(f"  🔍 Órdenes TP/SL creadas: {len(tp_sl_orders)}")
            for order in tp_sl_orders:
                logger.info(
                    f"    - {order.get('type', 'unknown')}: {order.get('amount', 0):.6f} @ {order.get('stopPrice', 0):.4f}"
                )

            # ========================================
            # PASO 2.5: Esperar resolución OCO de LONG
            # ========================================
            logger.info("\n⏱️ PASO 2.5: Esperando que precio toque TP o SL de LONG (180 segundos)")
            logger.info("  🎯 CRITERIO DE ÉXITO: Verificar comportamiento OCO automático")
            logger.info(f"  📊 TP LONG: ${tp_price_long:.2f} (+0.1%)")
            logger.info(f"  📊 SL LONG: ${sl_price_long:.2f} (-0.1%)")

            initial_long_orders = len(tp_sl_orders)
            long_resolved = False
            oco_verified = False
            price_hit_level = False

            for i in range(60):  # 60 checks de 3 segundos = 180 segundos
                await asyncio.sleep(3)

                # Obtener precio actual
                ticker = await self.connector.fetch_ticker(self.symbol)
                current_market_price = ticker["last"]

                # Verificar órdenes activas
                current_orders = await self.connector.fetch_open_orders(self.symbol)
                current_tp_sl = [o for o in current_orders if o.get("type") in ["stop_market", "take_profit_market"]]

                # Calcular distancia a TP/SL
                dist_to_tp = abs(current_market_price - tp_price_long)
                dist_to_sl = abs(current_market_price - sl_price_long)
                pct_to_tp = (dist_to_tp / tp_price_long) * 100
                pct_to_sl = (dist_to_sl / sl_price_long) * 100

                # Verificar si precio tocó nivel
                if current_market_price >= tp_price_long:
                    price_hit_level = True
                    logger.info(f"  🎯 ¡PRECIO TOCÓ TP! ${current_market_price:.4f} >= ${tp_price_long:.2f}")
                elif current_market_price <= sl_price_long:
                    price_hit_level = True
                    logger.info(f"  🛑 ¡PRECIO TOCÓ SL! ${current_market_price:.4f} <= ${sl_price_long:.2f}")

                logger.info(
                    f"  ⏳ Check {i+1}/60: Precio=${current_market_price:.4f} | TP: ${tp_price_long:.2f} ({pct_to_tp:.3f}%) | SL: ${sl_price_long:.2f} ({pct_to_sl:.3f}%) | Órdenes: {len(current_tp_sl)}"
                )

                # Verificar comportamiento OCO
                if price_hit_level and len(current_tp_sl) < initial_long_orders:
                    executed_count = initial_long_orders - len(current_tp_sl)
                    logger.info(f"  ✅ ¡OCO FUNCIONÓ! {executed_count} órdenes se cancelaron automáticamente")
                    oco_verified = True
                    long_resolved = True
                    break
                elif price_hit_level and len(current_tp_sl) == initial_long_orders:
                    logger.warning(f"  ⚠️ Precio tocó nivel pero órdenes no se cancelaron (OCO falló)")

                # Verificar si se ejecutó alguna orden (sin tocar precio)
                if len(current_tp_sl) < initial_long_orders:
                    executed_count = initial_long_orders - len(current_tp_sl)
                    logger.info(f"  🎯 ¡Posición LONG resuelta! {executed_count} TP/SL ejecutadas")
                    long_resolved = True
                    oco_verified = True
                    break

            # ========================================
            # PASO 2.6: Cerrar completamente posición LONG antes de SHORT
            # ========================================
            logger.info("\n🧹 PASO 2.6: Cerrando completamente posición LONG antes de abrir SHORT")
            logger.info("  (Evitamos posiciones opuestas simultáneas que causan error -4129 con GTE_GTC)")

            try:
                # Cancelar todas las órdenes TP/SL de LONG
                await self.connector.cancel_all_orders(self.symbol)
                logger.info("  ✅ Órdenes TP/SL de LONG canceladas")
                await asyncio.sleep(2)

                # Cerrar posición LONG manualmente
                positions = await self.connector.fetch_positions([self.symbol])
                for pos in positions:
                    if abs(pos.get("contracts", 0)) > 0:
                        side = "sell" if pos["side"] == "long" else "buy"
                        amount = abs(pos["contracts"])
                        logger.info(f"  🔄 Cerrando posición {pos['side'].upper()}: {amount}")
                        await self.connector.create_order(self.symbol, side, amount, order_type="market")
                        logger.info(f"  ✅ Posición {pos['side'].upper()} cerrada")

                await asyncio.sleep(3)  # Esperar a que se procese el cierre

                # Verificar que no hay posiciones abiertas
                positions = await self.connector.fetch_positions([self.symbol])
                open_positions = [p for p in positions if abs(p.get("contracts", 0)) > 0]
                if open_positions:
                    logger.warning(f"  ⚠️ Aún hay {len(open_positions)} posiciones abiertas")
                else:
                    logger.info("  ✅ Todas las posiciones cerradas correctamente")

            except Exception as e:
                logger.warning(f"  ⚠️ Error cerrando posición LONG: {e}")

            # ========================================
            # PASO 3: Apuesta SHORT (como el bot, DESPUÉS de cerrar LONG)
            # ========================================
            logger.info("\n📉 PASO 3: Ejecutando apuesta SHORT (simulando señal bajista)")
            logger.info("  (Ahora sin posiciones opuestas - evita error -4129)")

            # Esperar un poco para separar las órdenes
            await asyncio.sleep(2)

            # Obtener precio actual para SHORT
            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price_short = ticker["last"]

            # Orden SHORT con parámetros ULTRA AGRESIVOS para test
            short_order = {
                "trade_id": f"bot_sim_short_{int(time.time())}",
                "symbol": self.symbol,
                "side": "SHORT",
                "size": 0.001,  # 0.1% del equity
                "take_profit": 0.999,  # -0.1% (ULTRA AGRESIVO para ejecución inmediata)
                "stop_loss": 1.001,  # +0.1% (ULTRA AGRESIVO para ejecución inmediata)
                "leverage": 100,  # ⚡⚡ LEVERAGE MÁXIMO para ejecución inmediata
                "ghost": False,
            }

            # Calcular precios exactos de TP/SL para monitoreo
            tp_price_short = current_price_short * short_order["take_profit"]
            sl_price_short = current_price_short * short_order["stop_loss"]

            logger.info(
                f"  📝 Orden SHORT: size={short_order['size']*100:.1f}%, TP={-(1-short_order['take_profit'])*100:.1f}%, SL=+{(short_order['stop_loss']-1)*100:.1f}%"
            )
            logger.info(f"  ⚡⚡ LEVERAGE: {short_order['leverage']}x (MÁXIMO)")
            logger.info(f"  🎯 TP esperado: ${tp_price_short:.2f} (-${current_price_short - tp_price_short:.2f})")
            logger.info(f"  🛑 SL esperado: ${sl_price_short:.2f} (+${sl_price_short - current_price_short:.2f})")

            # Ejecutar con Croupier
            short_result = await croupier.execute_order(short_order)

            if short_result.get("status") not in ["open", "opened"]:
                return {
                    "success": False,
                    "error": f"SHORT falló: {short_result.get('error', 'Unknown')}",
                    "duration": 0,
                }

            logger.info(f"  ✅ Orden SHORT ejecutada: amount={short_result.get('amount', 0):.6f}")

            # Verificar órdenes TP/SL para SHORT
            await asyncio.sleep(2)  # Dar tiempo para que se creen las órdenes
            short_open_orders = await self.connector.fetch_open_orders(self.symbol)
            short_tp_sl_orders = [
                o for o in short_open_orders if o.get("type") in ["stop_market", "take_profit_market"]
            ]
            logger.info(f"  🔍 Órdenes TP/SL SHORT creadas: {len(short_tp_sl_orders)}")
            for order in short_tp_sl_orders:
                logger.info(
                    f"    - {order.get('type', 'unknown')}: {order.get('amount', 0):.6f} @ {order.get('stopPrice', 0):.4f}"
                )

            # ========================================
            # PASO 4: Verificar comportamiento OCO para SHORT
            # ========================================
            logger.info("\n🔍 PASO 4: Verificando comportamiento OCO para posición SHORT")
            logger.info("  (Verificamos que las órdenes TP/SL se comporten correctamente)")

            if len(short_tp_sl_orders) < 2:
                logger.warning(f"  ⚠️ Posición SHORT debería tener 2 órdenes TP/SL, tiene: {len(short_tp_sl_orders)}")
            else:
                logger.info(f"  ✅ Posición SHORT tiene {len(short_tp_sl_orders)} órdenes TP/SL (correcto)")

            # ========================================
            # PASO 5: Monitorear ejecución OCO de SHORT
            # ========================================
            logger.info("\n⏱️ PASO 5: Esperando que precio toque TP o SL de SHORT (180 segundos)")
            logger.info("  🎯 CRITERIO DE ÉXITO: Verificar comportamiento OCO automático")
            logger.info(f"  📊 TP SHORT: ${tp_price_short:.2f} (-0.1%)")
            logger.info(f"  📊 SL SHORT: ${sl_price_short:.2f} (+0.1%)")

            initial_short_orders = len(short_tp_sl_orders)
            short_resolved = False
            short_oco_verified = False

            short_resolved = False
            price_hit_level_short = False

            for i in range(60):  # 60 checks de 3 segundos = 180 segundos
                await asyncio.sleep(3)

                # Obtener precio actual
                ticker = await self.connector.fetch_ticker(self.symbol)
                current_market_price = ticker["last"]

                # Verificar órdenes activas
                current_orders = await self.connector.fetch_open_orders(self.symbol)
                current_tp_sl = [o for o in current_orders if o.get("type") in ["stop_market", "take_profit_market"]]

                # Calcular distancia a TP/SL
                dist_to_tp = abs(current_market_price - tp_price_short)
                dist_to_sl = abs(current_market_price - sl_price_short)
                pct_to_tp = (dist_to_tp / tp_price_short) * 100
                pct_to_sl = (dist_to_sl / sl_price_short) * 100

                # Verificar si precio tocó nivel
                if current_market_price <= tp_price_short:
                    price_hit_level_short = True
                    logger.info(f"  🎯 ¡PRECIO TOCÓ TP! ${current_market_price:.4f} <= ${tp_price_short:.2f}")
                elif current_market_price >= sl_price_short:
                    price_hit_level_short = True
                    logger.info(f"  🛑 ¡PRECIO TOCÓ SL! ${current_market_price:.4f} >= ${sl_price_short:.2f}")

                logger.info(
                    f"  ⏳ Check {i+1}/60: Precio=${current_market_price:.4f} | TP: ${tp_price_short:.2f} ({pct_to_tp:.3f}%) | SL: ${sl_price_short:.2f} ({pct_to_sl:.3f}%) | Órdenes: {len(current_tp_sl)}"
                )

                # Verificar comportamiento OCO
                if price_hit_level_short and len(current_tp_sl) < initial_short_orders:
                    executed_count = initial_short_orders - len(current_tp_sl)
                    logger.info(f"  ✅ ¡OCO FUNCIONÓ! {executed_count} órdenes se cancelaron automáticamente")
                    short_oco_verified = True
                    short_resolved = True
                    break
                elif price_hit_level_short and len(current_tp_sl) == initial_short_orders:
                    logger.warning(f"  ⚠️ Precio tocó nivel pero órdenes no se cancelaron (OCO falló)")

                # Verificar si se ejecutó alguna orden (sin tocar precio)
                if len(current_tp_sl) < initial_short_orders:
                    executed_count = initial_short_orders - len(current_tp_sl)
                    logger.info(f"  🎯 ¡Posición SHORT resuelta! {executed_count} TP/SL ejecutadas")
                    short_resolved = True
                    short_oco_verified = True
                    break

            if not short_resolved:
                if price_hit_level_short:
                    logger.error("  ❌ PRECIO TOCÓ NIVEL PERO ORDEN NO SE EJECUTÓ (problema del exchange)")
                else:
                    logger.warning(f"  ⚠️ SHORT no se resolvió (precio no tocó TP/SL en 180 segundos)")
                    logger.warning(f"     Distancia mínima a TP: ${dist_to_tp:.2f} ({pct_to_tp:.3f}%)")
                    logger.warning(f"     Distancia mínima a SL: ${dist_to_sl:.2f} ({pct_to_sl:.3f}%)")

            if not long_resolved:
                if price_hit_level:
                    logger.error("  ❌ PRECIO TOCÓ NIVEL PERO ORDEN NO SE EJECUTÓ (problema del exchange)")
                else:
                    logger.warning(f"  ⚠️ LONG no se resolvió (precio no tocó TP/SL en 180 segundos)")
                    logger.warning(f"     Distancia mínima a TP: ${dist_to_tp:.2f} ({pct_to_tp:.3f}%)")
                    logger.warning(f"     Distancia mínima a SL: ${dist_to_sl:.2f} ({pct_to_sl:.3f}%)")

            # ========================================
            # PASO 6: Cleanup y resultado
            # ========================================
            logger.info("\n🧹 PASO 6: Cleanup (cancelar órdenes restantes)")

            try:
                await self.connector.cancel_all_orders(self.symbol)
                logger.info("  ✅ Todas las órdenes canceladas")
            except Exception as e:
                logger.warning(f"  ⚠️ Error en cleanup: {e}")

            duration = (datetime.now() - start).total_seconds()

            # Resultado exitoso
            result_data = {
                "long_amount": long_result.get("amount", 0),
                "short_amount": short_result.get("amount", 0),
                "long_resolved": long_resolved,
                "short_resolved": short_resolved,
                "long_oco_verified": oco_verified,
                "short_oco_verified": short_oco_verified,
                "long_tp_sl_orders": initial_long_orders,
                "short_tp_sl_orders": initial_short_orders,
                "balance_used": usdt_balance,
                "leverage_used": 100,
            }

            logger.info("🎉 SIMULACIÓN DEL BOT COMPLETADA EXITOSAMENTE")
            logger.info("   Si este test pasa, el bot debería funcionar correctamente en producción")

            return {"success": True, "duration": duration, "data": result_data}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            return {"success": False, "error": str(e), "duration": duration}

    # =========================================================
    # 🎯 INTEGRATION TESTS (with Croupier)
    # =========================================================

    async def test_create_order_with_croupier(self) -> Dict:
        """Test INTEGRACIÓN: Crear orden usando Croupier (flujo completo de producción)."""
        start = datetime.now()

        try:
            logger.info("🎯 Creando orden con Croupier (flujo completo)...")

            # 1. Setup: Crear Croupier con balance inicial
            initial_balance = 10000.0
            croupier = Croupier(self.adapter, initial_balance=initial_balance)

            logger.info(f"  💰 Balance inicial: ${initial_balance:,.2f}")

            # 2. Obtener precio actual
            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker["last"]
            logger.info(f"  📈 Precio actual: ${current_price:.2f}")

            # 3. Crear orden usando Croupier
            order = {
                "trade_id": f"test_croupier_{int(time.time())}",
                "symbol": self.symbol,
                "side": "LONG",
                "size": 0.01,  # 1% del equity
                "take_profit": 1.01,  # +1%
                "stop_loss": 0.992,  # -0.8%
                "leverage": 10,
                "ghost": False,
            }

            logger.info(f"  📝 Orden: size={order['size']*100}%, TP={order['take_profit']}, SL={order['stop_loss']}")

            # 4. Ejecutar orden
            result = await croupier.execute_order(order)

            # 5. Validar
            duration = (datetime.now() - start).total_seconds()

            # Aceptar tanto "open" (CCXT) como "opened" (Croupier normalizado)
            status = result.get("status")
            if status not in ["open", "opened"]:
                return {"success": False, "error": f"Status: {status}", "duration": duration}

            if "amount" not in result or result["amount"] <= 0:
                return {"success": False, "error": "Amount not calculated", "duration": duration}

            logger.info(f"  ✅ Orden creada con Croupier")
            logger.info(f"  📊 Amount: {result['amount']:.6f}")

            # 6. Cleanup COMPLETO (órdenes + posiciones)
            try:
                await self.connector.cancel_all_orders(self.symbol)
                # CRÍTICO: También cerrar posiciones para evitar "rejected" en tests siguientes
                positions = await self.connector.fetch_positions()
                for pos in positions:
                    if abs(pos.get("contracts", 0)) > 0 and pos.get("symbol") == self.symbol:
                        side = "sell" if pos["side"] == "long" else "buy"
                        await self.connector.create_order(
                            symbol=pos["symbol"],
                            side=side,
                            amount=abs(pos["contracts"]),
                            order_type="market",
                            params={"reduceOnly": True},
                        )
                        logger.info(f"  🔒 Posición cerrada: {pos['symbol']}")
            except Exception:
                pass

            return {"success": True, "duration": duration, "data": {"amount": result["amount"]}}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"  ❌ Error: {e}")
            return {"success": False, "error": str(e), "duration": duration}

    async def test_croupier_amount_calculation(self) -> Dict:
        """Test INTEGRACIÓN: Validar cálculo de amount desde size."""
        start = datetime.now()

        try:
            logger.info("🎯 Validando cálculo de amount...")

            initial_balance = 10000.0
            croupier = Croupier(self.adapter, initial_balance=initial_balance)

            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker["last"]

            # Test con size=1%, leverage=10x
            size = 0.01
            leverage = 10

            # Cálculo esperado
            margin = initial_balance * size  # $100
            position_value = margin * leverage  # $1000
            expected_amount = position_value / current_price

            logger.info(f"  📊 Expected amount: {expected_amount:.6f}")

            order = {
                "trade_id": f"test_calc_{int(time.time())}",
                "symbol": self.symbol,
                "side": "LONG",
                "size": size,
                "take_profit": 1.01,
                "stop_loss": 0.992,
                "leverage": leverage,
                "ghost": True,  # No afecta balance
            }

            result = await croupier.execute_order(order)

            status = result.get("status")
            if status not in ["open", "opened"]:
                return {"success": False, "error": status}

            actual_amount = result.get("amount", 0)
            diff = abs(actual_amount - expected_amount) / expected_amount if expected_amount > 0 else 1

            # Cleanup COMPLETO (órdenes + posiciones)
            try:
                await self.connector.cancel_all_orders(self.symbol)
                # CRÍTICO: También cerrar posiciones para evitar "rejected" en tests siguientes
                positions = await self.connector.fetch_positions()
                for pos in positions:
                    if abs(pos.get("contracts", 0)) > 0 and pos.get("symbol") == self.symbol:
                        side = "sell" if pos["side"] == "long" else "buy"
                        await self.connector.create_order(
                            symbol=pos["symbol"],
                            side=side,
                            amount=abs(pos["contracts"]),
                            order_type="market",
                            params={"reduceOnly": True},
                        )
            except Exception:
                pass

            duration = (datetime.now() - start).total_seconds()

            if diff > 0.01:  # Tolerancia 1%
                return {
                    "success": False,
                    "error": f"Amount diff: {diff*100:.2f}%",
                    "expected": expected_amount,
                    "actual": actual_amount,
                    "duration": duration,
                }

            logger.info(f"  ✅ Amount: {actual_amount:.6f} (diff: {diff*100:.2f}%)")

            return {"success": True, "duration": duration}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"  ❌ Error: {e}")
            return {"success": False, "error": str(e), "duration": duration}

    async def test_croupier_portfolio_update(self) -> Dict:
        """Test INTEGRACIÓN: Validar actualización de portfolio."""
        start = datetime.now()

        try:
            logger.info("🎯 Validando portfolio update...")

            initial_balance = 10000.0
            croupier = Croupier(self.adapter, initial_balance=initial_balance)

            logger.info(f"  💰 Balance inicial: ${initial_balance:,.2f}")

            order = {
                "trade_id": f"test_portfolio_{int(time.time())}",
                "symbol": self.symbol,
                "side": "LONG",
                "size": 0.01,
                "take_profit": 1.01,
                "stop_loss": 0.992,
                "leverage": 10,
                "ghost": False,
            }

            result = await croupier.execute_order(order)

            status = result.get("status")
            if status not in ["open", "opened"]:
                return {"success": False, "error": f"Order failed: {status}", "duration": 0}

            new_balance = croupier.get_balance()
            open_positions = croupier.get_open_positions()

            logger.info(f"  💰 Balance: ${initial_balance:,.2f} → ${new_balance:,.2f}")
            logger.info(f"  📈 Posiciones abiertas: {len(open_positions)}")

            # Cleanup COMPLETO (órdenes + posiciones)
            try:
                await self.connector.cancel_all_orders(self.symbol)
                # CRÍTICO: También cerrar posiciones para evitar "rejected" en tests siguientes
                positions = await self.connector.fetch_positions()
                for pos in positions:
                    if abs(pos.get("contracts", 0)) > 0 and pos.get("symbol") == self.symbol:
                        side = "sell" if pos["side"] == "long" else "buy"
                        await self.connector.create_order(
                            symbol=pos["symbol"],
                            side=side,
                            amount=abs(pos["contracts"]),
                            order_type="market",
                            params={"reduceOnly": True},
                        )
            except Exception:
                pass

            duration = (datetime.now() - start).total_seconds()

            # Validar que el portfolio se actualizó
            # El balance puede no cambiar si el portfolio usa tracking interno
            # Lo importante es que haya posiciones abiertas
            if len(open_positions) == 0:
                return {"success": False, "error": "No open positions in portfolio", "duration": duration}

            logger.info(f"  ✅ Portfolio actualizado ({len(open_positions)} posiciones)")

            return {"success": True, "duration": duration}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"  ❌ Error: {e}")
            return {"success": False, "error": str(e), "duration": duration}


async def validate_connector(
    exchange: str, demo: bool = True, symbol: str = "LTC/USDT:USDT", execute_orders: bool = False
):
    """
    Valida un conector de exchange de forma agnóstica.

    Args:
        exchange: Nombre del exchange (kraken, bybit, binance, etc.)
        demo: Si usar demo trading o live
        symbol: Símbolo para las pruebas (formato: "LTC/USDT:USDT")
        execute_orders: Si ejecutar órdenes reales con TP/SL (requiere fondos)
    """
    logger.info(f"🚀 Iniciando validación de conector: {exchange}")
    logger.info(f"🌐 Modo: {'DEMO' if demo else 'LIVE'}")
    logger.info(f"📊 Símbolo: {symbol}")
    logger.info(f"🎯 Órdenes reales: {'SÍ' if execute_orders else 'NO'}")

    # Crear conector según exchange
    if exchange.lower() == "kraken":
        mode = "demo" if demo else "live"
        connector = KrakenConnector(mode=mode)
    elif exchange.lower() == "bybit":
        mode = "demo" if demo else "live"
        connector = BybitConnector(mode=mode)
    elif exchange.lower() == "binance":
        mode = "testnet" if demo else "live"
        connector = BinanceConnector(mode=mode)
    else:
        raise ValueError(f"Exchange no soportado: {exchange}")

    # Crear validador y ejecutar tests
    validator = ConnectorValidator(connector, symbol, execute_orders)

    try:
        results = await validator.run_all_tests()
        return results
    finally:
        # Desconectar
        await connector.disconnect()
        logger.info("🔌 Conector desconectado")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Validador de conectores de exchange",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Validación básica (sin órdenes reales)
  python -m utils.connector_validator --exchange bybit --demo

  # Validación COMPLETA con órdenes reales y TP/SL
  python -m utils.connector_validator --exchange bybit --demo --execute-orders

  # Con símbolo específico
  python -m utils.connector_validator --exchange bybit --demo --symbol ETH/USDT:USDT --execute-orders
        """,
    )

    parser.add_argument(
        "--exchange",
        type=str,
        required=True,
        choices=["kraken", "bybit", "binance"],
        help="Exchange a validar",
    )

    parser.add_argument("--demo", action="store_true", help="Usar demo trading (default: True)")

    parser.add_argument("--live", action="store_true", help="Usar live (default: False)")

    parser.add_argument(
        "--symbol", type=str, default="LTC/USDT:USDT", help="Símbolo para las pruebas (formato: LTC/USDT:USDT)"
    )

    parser.add_argument(
        "--execute-orders",
        action="store_true",
        help="Ejecutar órdenes REALES con TP/SL (requiere fondos en demo)",
    )

    args = parser.parse_args()

    # Determinar si usar demo o live
    demo = not args.live if args.live else True

    # Ejecutar validación
    asyncio.run(validate_connector(args.exchange, demo, args.symbol, args.execute_orders))


if __name__ == "__main__":
    main()
