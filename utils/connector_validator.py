"""
Connector Validator - Utilidad para validar y debugear conectores de exchange.

Esta herramienta permite probar todas las funcionalidades de un conector
de forma sistemática para validar su implementación y detectar problemas.

Uso:
    python -m utils.connector_validator --exchange kraken --testnet
    python -m utils.connector_validator --exchange kraken --live --symbol BTCUSD
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from config.exchange import EXCHANGE_CONFIG
from exchanges.connectors import KrakenConnector
from exchanges.connectors.connector_base import BaseConnector

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

    def __init__(self, connector: BaseConnector, symbol: str = "BTC/USD"):
        """
        Inicializa el validador.

        Args:
            connector: Conector a validar
            symbol: Símbolo para las pruebas
        """
        self.connector = connector
        self.symbol = symbol
        self.results: Dict[str, Dict] = {}

    async def run_all_tests(self) -> Dict[str, Dict]:
        """
        Ejecuta todos los tests de validación.

        Returns:
            Diccionario con resultados de cada test
        """
        logger.info("=" * 80)
        logger.info(f"🔍 VALIDACIÓN DE CONECTOR: {self.connector.__class__.__name__}")
        logger.info(f"📊 Símbolo: {self.symbol}")
        logger.info("=" * 80)

        # Lista de tests a ejecutar
        tests = [
            ("Conexión", self.test_connection),
            ("Balance", self.test_fetch_balance),
            ("Posiciones", self.test_fetch_positions),
            ("Ticker", self.test_fetch_ticker),
            ("Order Book", self.test_fetch_order_book),
            ("Trades Recientes", self.test_fetch_trades),
            ("Mis Trades", self.test_fetch_my_trades),
            ("Órdenes Abiertas", self.test_fetch_open_orders),
            ("Crear Orden (Dry Run)", self.test_create_order_dry_run),
            ("Cancelar Orden (Dry Run)", self.test_cancel_order_dry_run),
            ("Límites de Trading", self.test_trading_limits),
            ("Fees", self.test_fees),
            ("Timeframes", self.test_timeframes),
            ("Precisión", self.test_precision),
        ]

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

            if self.symbol not in markets:
                return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[self.symbol]
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

            if self.symbol not in markets:
                return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[self.symbol]

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

            if self.symbol not in markets:
                return {"success": False, "error": f"Symbol {self.symbol} not found"}

            market = markets[self.symbol]
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


async def validate_connector(exchange: str, testnet: bool = True, symbol: str = "BTC/USD"):
    """
    Valida un conector de exchange.

    Args:
        exchange: Nombre del exchange (kraken, binance, etc.)
        testnet: Si usar testnet o live
        symbol: Símbolo para las pruebas
    """
    logger.info(f"🚀 Iniciando validación de conector: {exchange}")
    logger.info(f"🌐 Modo: {'TESTNET' if testnet else 'LIVE'}")
    logger.info(f"📊 Símbolo: {symbol}")

    # Crear conector según exchange
    if exchange.lower() == "kraken":
        connector = KrakenConnector(testnet=testnet)
    else:
        raise ValueError(f"Exchange no soportado: {exchange}")

    # Crear validador y ejecutar tests
    validator = ConnectorValidator(connector, symbol)

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
  # Validar Kraken en testnet
  python -m utils.connector_validator --exchange kraken --testnet

  # Validar Kraken en live
  python -m utils.connector_validator --exchange kraken --live

  # Validar con símbolo específico
  python -m utils.connector_validator --exchange kraken --testnet --symbol ETH/USD
        """,
    )

    parser.add_argument(
        "--exchange",
        type=str,
        required=True,
        choices=["kraken", "binance"],
        help="Exchange a validar",
    )

    parser.add_argument("--testnet", action="store_true", help="Usar testnet (default: True)")

    parser.add_argument("--live", action="store_true", help="Usar live (default: False)")

    parser.add_argument("--symbol", type=str, default="BTC/USD", help="Símbolo para las pruebas")

    args = parser.parse_args()

    # Determinar si usar testnet o live
    testnet = not args.live if args.live else True

    # Ejecutar validación
    asyncio.run(validate_connector(args.exchange, testnet, args.symbol))


if __name__ == "__main__":
    main()
