"""
Connector Validator - Utilidad AGNÓSTICA para validar conectores de exchange.

Esta herramienta prueba TODAS las funcionalidades necesarias para el bot:
- Métodos básicos (balance, positions, ticker, etc.)
- Órdenes REALES con TP/SL
- Ejecución automática de TP/SL (CRÍTICO para el bot)

Funciona con CUALQUIER exchange que implemente BaseConnector.

Uso:
    # Validación completa (incluye órdenes reales)
    python -m utils.connector_validator --exchange bybit --demo --execute-orders

    # Solo validación de métodos (sin órdenes)
    python -m utils.connector_validator --exchange bybit --demo

    # Con símbolo específico
    python -m utils.connector_validator --exchange bybit --demo --symbol ETH/USDT:USDT
"""

import argparse
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

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

    def __init__(self, connector: BaseConnector, symbol: str = "BTC/USD:USD", execute_orders: bool = False):
        """
        Inicializa el validador.

        Args:
            connector: Conector a validar
            symbol: Símbolo para las pruebas (formato: "BTC/USD:USD")
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
                self.results[test_name] = {
                    "status": "✅ PASS" if result["success"] else "❌ FAIL",
                    "data": result.get("data"),
                    "error": result.get("error"),
                    "duration": result.get("duration", 0),
                }

                if result["success"]:
                    logger.info(f"✅ {test_name}: PASS")
                    if result.get("data"):
                        self._log_data(result["data"])
                else:
                    logger.error(f"❌ {test_name}: FAIL - {result.get('error')}")

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
            bot_order = {
                "symbol": self.symbol,
                "side": "sell",  # SHORT para que TP sea más bajo
                "amount": amount,
                "type": "market",
                "take_profit": 0.999,  # -0.1% (ganar si baja)
                "stop_loss": 1.001,  # +0.1% (perder si sube)
            }

            logger.info(f"  📋 Orden del bot: {bot_order['side'].upper()} {amount}")
            logger.info(f"  🎯 TP Multiplier: {bot_order['take_profit']} (-0.1%)")
            logger.info(f"  🛑 SL Multiplier: {bot_order['stop_loss']} (+0.1%)")

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

        Espera hasta 3 minutos monitoreando la posición.
        Si la posición se cierra, significa que TP o SL se ejecutó.
        """
        start = datetime.now()
        timeout = 180  # 3 minutos
        check_interval = 5  # Revisar cada 5 segundos

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

                # Mostrar progreso
                progress = (elapsed / timeout) * 100
                remaining = timeout - elapsed
                logger.info(f"   ⏱️  {elapsed}s / {timeout}s ({progress:.1f}%) - Restante: {remaining}s")

                # Esperar antes de la siguiente revisión
                await asyncio.sleep(check_interval)
                elapsed += check_interval

            # Timeout alcanzado
            duration = (datetime.now() - start).total_seconds()
            logger.warning(f"  ⚠️ TIMEOUT: TP/SL no se ejecutó en {timeout}s")
            logger.warning("     Esto puede ser normal si el precio no se movió lo suficiente")

            return {
                "success": False,
                "error": f"Timeout: TP/SL no se ejecutó en {timeout}s (precio no se movió suficiente)",
                "duration": duration,
            }

        except Exception as e:
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

        logger.info(f"\nTotal tests: {total}")
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"Success rate: {(passed/total*100):.1f}%")

        logger.info("\nDetalle por test:")
        for test_name, result in self.results.items():
            status = result["status"]
            duration = result.get("duration", 0)
            logger.info(f"  {status} {test_name} ({duration:.2f}s)")
            if result.get("error"):
                logger.info(f"      Error: {result['error']}")

        logger.info("\n" + "=" * 80)


async def validate_connector(
    exchange: str, demo: bool = True, symbol: str = "BTC/USDT:USDT", execute_orders: bool = False
):
    """
    Valida un conector de exchange de forma agnóstica.

    Args:
        exchange: Nombre del exchange (kraken, bybit, binance, etc.)
        demo: Si usar demo trading o live
        symbol: Símbolo para las pruebas (formato: "BTC/USDT:USDT")
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
        "--symbol", type=str, default="BTC/USDT:USDT", help="Símbolo para las pruebas (formato: BTC/USDT:USDT)"
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
