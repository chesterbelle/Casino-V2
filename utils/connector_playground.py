"""
Connector Playground - Modo interactivo para probar conectores.

Permite probar funciones individuales de un conector de forma interactiva,
ideal para debugging y exploración.

Uso:
    python -m utils.connector_playground --exchange kraken --testnet
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exchanges.connectors.connector_base import BaseConnector
from exchanges.connectors.kraken import KrakenConnector
from exchanges.connectors.resilient_connector import ResilientConnector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ConnectorPlayground:
    """
    Playground interactivo para probar conectores.

    Permite ejecutar comandos individuales para probar funcionalidades
    específicas del conector.
    """

    def __init__(self, connector: BaseConnector):
        """
        Inicializa el playground.

        Args:
            connector: Conector a usar
        """
        self.connector = connector
        self.symbol = "BTC/USD"  # Default
        self.running = True

    async def start(self):
        """Inicia el playground interactivo."""
        logger.info("=" * 80)
        logger.info(f"🎮 CONNECTOR PLAYGROUND: {self.connector.__class__.__name__}")
        logger.info("=" * 80)

        # Conectar
        try:
            await self.connector.connect()
            logger.info("✅ Conectado al exchange")
        except Exception as e:
            logger.error(f"❌ Error al conectar: {e}")
            return

        # Mostrar ayuda
        self.print_help()

        # Loop interactivo
        while self.running:
            try:
                command = input("\n🎮 > ").strip()

                if not command:
                    continue

                await self.execute_command(command)

            except KeyboardInterrupt:
                logger.info("\n👋 Saliendo...")
                self.running = False
            except Exception as e:
                logger.error(f"❌ Error: {e}", exc_info=True)

        # Desconectar
        await self.connector.disconnect()
        logger.info("🔌 Desconectado")

    async def execute_command(self, command: str):
        """
        Ejecuta un comando.

        Args:
            command: Comando a ejecutar
        """
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Comandos disponibles
        commands = {
            "help": self.cmd_help,
            "h": self.cmd_help,
            "symbol": self.cmd_symbol,
            "balance": self.cmd_balance,
            "positions": self.cmd_positions,
            "ticker": self.cmd_ticker,
            "orderbook": self.cmd_orderbook,
            "trades": self.cmd_trades,
            "mytrades": self.cmd_mytrades,
            "orders": self.cmd_orders,
            "markets": self.cmd_markets,
            "limits": self.cmd_limits,
            "fees": self.cmd_fees,
            "precision": self.cmd_precision,
            "timeframes": self.cmd_timeframes,
            "testorder": self.cmd_test_order,
            "monitor": self.cmd_monitor_position,
            "closeall": self.cmd_close_all,
            # Nuevos comandos
            "status": self.cmd_status,
            "metrics": self.cmd_metrics,
            "ws": self.cmd_websocket_status,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
        }

        if cmd in commands:
            await commands[cmd](args)
        else:
            logger.error(f"❌ Comando desconocido: {cmd}")
            logger.info("💡 Usa 'help' para ver comandos disponibles")

    def print_help(self):
        """Imprime ayuda."""
        logger.info("\n📖 COMANDOS DISPONIBLES:")
        logger.info("─" * 80)
        logger.info("  help, h              - Muestra esta ayuda")
        logger.info("  symbol <SYMBOL>      - Cambia el símbolo actual")
        logger.info("  balance              - Muestra balance")
        logger.info("  positions            - Muestra posiciones abiertas")
        logger.info("  ticker               - Muestra ticker del símbolo actual")
        logger.info("  orderbook [limit]    - Muestra order book")
        logger.info("  trades [limit]       - Muestra trades recientes")
        logger.info("  mytrades [limit]     - Muestra mis trades")
        logger.info("  orders               - Muestra órdenes abiertas")
        logger.info("  markets [search]     - Lista mercados disponibles")
        logger.info("  limits               - Muestra límites de trading")
        logger.info("  fees                 - Muestra fees")
        logger.info("  precision            - Muestra precisión de precios")
        logger.info("  timeframes           - Muestra timeframes disponibles")
        logger.info("  testorder            - Crea orden de prueba (pequeña)")
        logger.info("  monitor              - Monitorea posición actual")
        logger.info("  closeall             - Cierra todas las posiciones")
        logger.info("")
        logger.info("  🆕 NUEVOS COMANDOS:")
        logger.info("  status               - Estado del conector (WebSocket, etc.)")
        logger.info("  metrics              - Métricas (OrderTracker, ErrorClassifier)")
        logger.info("  ws                   - Estado del WebSocket")
        logger.info("")
        logger.info("  exit, quit           - Sale del playground")
        logger.info("─" * 80)
        logger.info(f"📊 Símbolo actual: {self.symbol}")

    async def cmd_help(self, args):
        """Comando: help."""
        self.print_help()

    async def cmd_symbol(self, args):
        """Comando: symbol."""
        if not args:
            logger.info(f"📊 Símbolo actual: {self.symbol}")
            return

        self.symbol = args[0]
        logger.info(f"✅ Símbolo cambiado a: {self.symbol}")

    async def cmd_balance(self, args):
        """Comando: balance."""
        logger.info("💰 Obteniendo balance...")
        balance = await self.connector.fetch_balance()

        logger.info("\n💰 BALANCE:")
        logger.info("─" * 80)

        # Mostrar solo monedas con balance > 0
        for currency, info in balance.items():
            if isinstance(info, dict):
                total = info.get("total", 0)
                if total > 0:
                    free = info.get("free", 0)
                    used = info.get("used", 0)
                    logger.info(
                        f"  {currency:8s} | Total: {total:>15.8f} | " f"Free: {free:>15.8f} | Used: {used:>15.8f}"
                    )

    async def cmd_positions(self, args):
        """Comando: positions."""
        logger.info("📊 Obteniendo posiciones...")
        positions = await self.connector.fetch_positions()

        if not positions:
            logger.info("📭 No hay posiciones abiertas")
            return

        logger.info(f"\n📊 POSICIONES ({len(positions)}):")
        logger.info("─" * 80)

        for pos in positions:
            logger.info(f"\n  Symbol: {pos.get('symbol')}")
            logger.info(f"  Side: {pos.get('side')}")
            logger.info(f"  Contracts: {pos.get('contracts')}")
            logger.info(f"  Entry Price: {pos.get('entryPrice')}")
            logger.info(f"  Mark Price: {pos.get('markPrice')}")
            logger.info(f"  Unrealized PnL: {pos.get('unrealizedPnl')}")
            logger.info(f"  Leverage: {pos.get('leverage')}")

    async def cmd_ticker(self, args):
        """Comando: ticker."""
        logger.info(f"📈 Obteniendo ticker de {self.symbol}...")
        ticker = await self.connector.fetch_ticker(self.symbol)

        logger.info(f"\n📈 TICKER: {self.symbol}")
        logger.info("─" * 80)
        logger.info(f"  Last: {ticker.get('last')}")
        logger.info(f"  Bid: {ticker.get('bid')}")
        logger.info(f"  Ask: {ticker.get('ask')}")
        logger.info(f"  High: {ticker.get('high')}")
        logger.info(f"  Low: {ticker.get('low')}")
        logger.info(f"  Volume: {ticker.get('volume')}")
        logger.info(f"  Timestamp: {ticker.get('datetime')}")

    async def cmd_orderbook(self, args):
        """Comando: orderbook."""
        limit = int(args[0]) if args else 10
        logger.info(f"📖 Obteniendo order book de {self.symbol} (limit={limit})...")
        orderbook = await self.connector.fetch_order_book(self.symbol, limit=limit)

        logger.info(f"\n📖 ORDER BOOK: {self.symbol}")
        logger.info("─" * 80)

        logger.info("\n  🟢 BIDS (compra):")
        for price, amount in orderbook["bids"][:5]:
            logger.info(f"    {price:>12.2f} | {amount:>12.8f}")

        logger.info("\n  🔴 ASKS (venta):")
        for price, amount in orderbook["asks"][:5]:
            logger.info(f"    {price:>12.2f} | {amount:>12.8f}")

        spread = orderbook["asks"][0][0] - orderbook["bids"][0][0]
        logger.info(f"\n  Spread: {spread:.2f}")

    async def cmd_trades(self, args):
        """Comando: trades."""
        limit = int(args[0]) if args else 10
        logger.info(f"📊 Obteniendo trades de {self.symbol} (limit={limit})...")
        trades = await self.connector.fetch_trades(self.symbol, limit=limit)

        logger.info(f"\n📊 TRADES RECIENTES: {self.symbol}")
        logger.info("─" * 80)

        for trade in trades[:10]:
            side_emoji = "🟢" if trade.get("side") == "buy" else "🔴"
            logger.info(
                f"  {side_emoji} {trade.get('datetime')} | "
                f"Price: {trade.get('price'):>12.2f} | "
                f"Amount: {trade.get('amount'):>12.8f} | "
                f"Side: {trade.get('side')}"
            )

    async def cmd_mytrades(self, args):
        """Comando: mytrades."""
        limit = int(args[0]) if args else 20
        logger.info(f"📊 Obteniendo mis trades de {self.symbol} (limit={limit})...")
        trades = await self.connector.fetch_my_trades(symbol=self.symbol, limit=limit)

        if not trades:
            logger.info("📭 No hay trades")
            return

        logger.info(f"\n📊 MIS TRADES: {self.symbol} ({len(trades)})")
        logger.info("─" * 80)

        for trade in trades[:10]:
            side_emoji = "🟢" if trade.get("side") == "buy" else "🔴"
            logger.info(
                f"  {side_emoji} {trade.get('datetime')} | "
                f"Price: {trade.get('price'):>12.2f} | "
                f"Amount: {trade.get('amount'):>12.8f} | "
                f"Fee: {trade.get('fee', {}).get('cost', 0):.4f}"
            )

    async def cmd_orders(self, args):
        """Comando: orders."""
        logger.info(f"📋 Obteniendo órdenes abiertas de {self.symbol}...")
        orders = await self.connector.fetch_open_orders(symbol=self.symbol)

        if not orders:
            logger.info("📭 No hay órdenes abiertas")
            return

        logger.info(f"\n📋 ÓRDENES ABIERTAS: {self.symbol} ({len(orders)})")
        logger.info("─" * 80)

        for order in orders:
            logger.info(f"\n  ID: {order.get('id')}")
            logger.info(f"  Type: {order.get('type')}")
            logger.info(f"  Side: {order.get('side')}")
            logger.info(f"  Price: {order.get('price')}")
            logger.info(f"  Amount: {order.get('amount')}")
            logger.info(f"  Filled: {order.get('filled')}")
            logger.info(f"  Status: {order.get('status')}")

    async def cmd_markets(self, args):
        """Comando: markets."""
        search = args[0].upper() if args else None
        logger.info("🌐 Cargando mercados...")
        markets = await self.connector.load_markets()

        # Filtrar por búsqueda
        if search:
            markets = {k: v for k, v in markets.items() if search in k}

        logger.info(f"\n🌐 MERCADOS ({len(markets)}):")
        logger.info("─" * 80)

        for symbol in list(markets.keys())[:20]:  # Primeros 20
            market = markets[symbol]
            active = "✅" if market.get("active") else "❌"
            logger.info(
                f"  {active} {symbol:20s} | Type: {market.get('type'):10s} | "
                f"Base: {market.get('base'):8s} | Quote: {market.get('quote')}"
            )

        if len(markets) > 20:
            logger.info(f"\n  ... y {len(markets) - 20} más")

    async def cmd_limits(self, args):
        """Comando: limits."""
        logger.info(f"📏 Obteniendo límites de {self.symbol}...")
        markets = await self.connector.load_markets()

        if self.symbol not in markets:
            logger.error(f"❌ Símbolo no encontrado: {self.symbol}")
            return

        market = markets[self.symbol]
        limits = market.get("limits", {})

        logger.info(f"\n📏 LÍMITES: {self.symbol}")
        logger.info("─" * 80)

        logger.info("\n  Amount:")
        amount = limits.get("amount", {})
        logger.info(f"    Min: {amount.get('min')}")
        logger.info(f"    Max: {amount.get('max')}")

        logger.info("\n  Price:")
        price = limits.get("price", {})
        logger.info(f"    Min: {price.get('min')}")
        logger.info(f"    Max: {price.get('max')}")

        logger.info("\n  Cost:")
        cost = limits.get("cost", {})
        logger.info(f"    Min: {cost.get('min')}")
        logger.info(f"    Max: {cost.get('max')}")

    async def cmd_fees(self, args):
        """Comando: fees."""
        logger.info(f"💸 Obteniendo fees de {self.symbol}...")
        markets = await self.connector.load_markets()

        if self.symbol not in markets:
            logger.error(f"❌ Símbolo no encontrado: {self.symbol}")
            return

        market = markets[self.symbol]

        logger.info(f"\n💸 FEES: {self.symbol}")
        logger.info("─" * 80)
        logger.info(f"  Maker: {market.get('maker', 0) * 100:.4f}%")
        logger.info(f"  Taker: {market.get('taker', 0) * 100:.4f}%")
        logger.info(f"  Percentage: {market.get('percentage')}")

    async def cmd_precision(self, args):
        """Comando: precision."""
        logger.info(f"🎯 Obteniendo precisión de {self.symbol}...")
        markets = await self.connector.load_markets()

        if self.symbol not in markets:
            logger.error(f"❌ Símbolo no encontrado: {self.symbol}")
            return

        market = markets[self.symbol]
        precision = market.get("precision", {})

        logger.info(f"\n🎯 PRECISIÓN: {self.symbol}")
        logger.info("─" * 80)
        logger.info(f"  Price: {precision.get('price')} decimales")
        logger.info(f"  Amount: {precision.get('amount')} decimales")
        logger.info(f"  Base: {precision.get('base')}")
        logger.info(f"  Quote: {precision.get('quote')}")

    async def cmd_timeframes(self, args):
        """Comando: timeframes."""
        logger.info("⏰ Obteniendo timeframes...")
        timeframes = self.connector.timeframes

        logger.info("\n⏰ TIMEFRAMES DISPONIBLES:")
        logger.info("─" * 80)

        if timeframes:
            for tf_key, tf_value in timeframes.items():
                logger.info(f"  {tf_key:8s} = {tf_value}")
        else:
            logger.info("  No hay timeframes disponibles")

    async def cmd_test_order(self, args):
        """Comando: testorder - Crea orden de prueba con TP/SL narrow."""
        side = args[0].upper() if args else "LONG"

        if side not in ["LONG", "SHORT"]:
            logger.error("❌ Side debe ser LONG o SHORT")
            return

        logger.info(f"🧪 Creando orden de prueba {side} en {self.symbol}...")
        logger.info("⚠️  Configuración: 40x leverage, TP/SL narrow para ejecución rápida")

        try:
            # Obtener precio actual
            ticker = await self.connector.fetch_ticker(self.symbol)
            current_price = ticker.get("last")

            if not current_price:
                logger.error("❌ No se pudo obtener precio actual")
                return

            # Calcular TP/SL narrow (0.5% para que se alcance rápido con 40x)
            if side == "LONG":
                tp_price = current_price * 1.005  # +0.5%
                sl_price = current_price * 0.995  # -0.5%
            else:  # SHORT
                tp_price = current_price * 0.995  # -0.5%
                sl_price = current_price * 1.005  # +0.5%

            # Calcular size mínimo (usar balance disponible / 40)
            balance = await self.connector.fetch_balance()
            available = 0

            # Buscar balance en USD o USDT
            for currency in ["USD", "USDT", "USDC"]:
                if currency in balance and isinstance(balance[currency], dict):
                    available = balance[currency].get("free", 0)
                    if available > 0:
                        break

            if available == 0:
                logger.error("❌ No hay balance disponible")
                return

            # Size = balance / (precio * 40) para usar 40x leverage
            size = (available / 40) / current_price
            size = round(size, 8)  # Redondear a 8 decimales

            logger.info(f"\n📊 PARÁMETROS DE LA ORDEN:")
            logger.info(f"  Symbol: {self.symbol}")
            logger.info(f"  Side: {side}")
            logger.info(f"  Size: {size}")
            logger.info(f"  Entry Price: {current_price:.2f}")
            logger.info(f"  Take Profit: {tp_price:.2f} ({'+0.5%' if side == 'LONG' else '-0.5%'})")
            logger.info(f"  Stop Loss: {sl_price:.2f} ({'-0.5%' if side == 'LONG' else '+0.5%'})")
            logger.info(f"  Leverage: 40x")
            logger.info(f"  Balance usado: ${available / 40:.2f} (de ${available:.2f})")

            # Confirmar
            confirm = input("\n⚠️  ¿Crear esta orden? (yes/no): ").strip().lower()
            if confirm != "yes":
                logger.info("❌ Orden cancelada")
                return

            # Crear orden market con TP/SL usando OCO bracket
            logger.info("🚀 Creando orden con OCO bracket...")

            order = await self.connector.create_order_with_tpsl(
                symbol=self.symbol,
                side="buy" if side == "LONG" else "sell",
                amount=size,
                price=None,  # Market order
                order_type="market",
                tp_price=tp_price,
                sl_price=sl_price,
                params={"leverage": 40},
            )

            logger.info(f"\n✅ ORDEN CREADA:")
            logger.info(f"  Order ID: {order.get('id')}")
            logger.info(f"  Status: {order.get('status')}")
            logger.info(f"  Filled: {order.get('filled')}")
            logger.info(f"  Average Price: {order.get('average')}")

            logger.info(f"\n💡 Usa 'monitor' para monitorear la posición hasta que cierre por TP/SL")

        except Exception as e:
            logger.error(f"❌ Error al crear orden: {e}", exc_info=True)

    async def cmd_monitor_position(self, args):
        """Comando: monitor - Monitorea posición hasta que cierre."""
        logger.info(f"👁️  Monitoreando posiciones de {self.symbol}...")
        logger.info("⏸️  Presiona Ctrl+C para detener el monitoreo")
        logger.info("─" * 80)

        try:
            last_position_count = 0
            check_count = 0

            while True:
                check_count += 1

                # Obtener posiciones
                positions = await self.connector.fetch_positions()

                # Filtrar por símbolo
                symbol_positions = [p for p in positions if p.get("symbol") == self.symbol]

                # Mostrar estado
                if len(symbol_positions) != last_position_count:
                    logger.info(f"\n📊 Check #{check_count} - {asyncio.get_event_loop().time():.0f}s")
                    logger.info(f"  Posiciones abiertas: {len(symbol_positions)}")

                    if len(symbol_positions) == 0 and last_position_count > 0:
                        logger.info("\n🎯 ¡POSICIÓN CERRADA!")
                        logger.info("─" * 80)

                        # Obtener último trade para ver el resultado
                        logger.info("📊 Obteniendo detalles del cierre...")
                        trades = await self.connector.fetch_my_trades(symbol=self.symbol, limit=5)

                        if trades:
                            last_trade = trades[0]
                            logger.info(f"\n💰 ÚLTIMO TRADE:")
                            logger.info(f"  ID: {last_trade.get('id')}")
                            logger.info(f"  Side: {last_trade.get('side')}")
                            logger.info(f"  Price: {last_trade.get('price')}")
                            logger.info(f"  Amount: {last_trade.get('amount')}")
                            logger.info(f"  Fee: {last_trade.get('fee', {}).get('cost', 0)}")

                            # Intentar obtener PnL del info
                            info = last_trade.get("info", {})
                            if "realizedPnl" in info:
                                pnl = float(info["realizedPnl"])
                                pnl_emoji = "🟢" if pnl > 0 else "🔴"
                                logger.info(f"  {pnl_emoji} Realized PnL: ${pnl:+.2f}")

                        # Mostrar balance actualizado
                        balance = await self.connector.fetch_balance()
                        for currency in ["USD", "USDT", "USDC"]:
                            if currency in balance and isinstance(balance[currency], dict):
                                total = balance[currency].get("total", 0)
                                if total > 0:
                                    logger.info(f"\n💰 Balance {currency}: ${total:.2f}")
                                    break

                        logger.info("\n✅ Monitoreo completado")
                        break

                    last_position_count = len(symbol_positions)

                # Mostrar posiciones actuales
                for pos in symbol_positions:
                    unrealized_pnl = pos.get("unrealizedPnl", 0)
                    pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴"
                    logger.info(
                        f"  {pnl_emoji} {pos.get('side'):5s} | "
                        f"Size: {pos.get('contracts'):>10.8f} | "
                        f"Entry: {pos.get('entryPrice'):>10.2f} | "
                        f"Mark: {pos.get('markPrice'):>10.2f} | "
                        f"PnL: ${unrealized_pnl:>8.2f}"
                    )

                # Esperar antes del próximo check (cada 2 segundos)
                await asyncio.sleep(2)

        except KeyboardInterrupt:
            logger.info("\n⏸️  Monitoreo detenido por usuario")
        except Exception as e:
            logger.error(f"❌ Error en monitoreo: {e}", exc_info=True)

    async def cmd_close_all(self, args):
        """Comando: closeall - Cierra todas las posiciones."""
        logger.info(f"🔴 Cerrando todas las posiciones de {self.symbol}...")

        try:
            # Obtener posiciones
            positions = await self.connector.fetch_positions()

            # Filtrar por símbolo
            symbol_positions = [p for p in positions if p.get("symbol") == self.symbol]

            if not symbol_positions:
                logger.info("📭 No hay posiciones abiertas para cerrar")
                return

            logger.info(f"  Posiciones a cerrar: {len(symbol_positions)}")

            # Confirmar
            confirm = input("\n⚠️  ¿Cerrar todas las posiciones? (yes/no): ").strip().lower()
            if confirm != "yes":
                logger.info("❌ Operación cancelada")
                return

            # Cerrar cada posición
            for pos in symbol_positions:
                side = pos.get("side")
                contracts = pos.get("contracts")

                # Para cerrar: LONG → sell, SHORT → buy
                close_side = "sell" if side == "long" else "buy"

                logger.info(f"  Cerrando {side} de {contracts} contratos...")

                order = await self.connector.create_order(
                    symbol=self.symbol,
                    type="market",
                    side=close_side,
                    amount=abs(contracts),
                    params={"reduceOnly": True},
                )

                logger.info(f"    ✅ Orden de cierre creada: {order.get('id')}")

            logger.info("\n✅ Todas las posiciones cerradas")

        except Exception as e:
            logger.error(f"❌ Error al cerrar posiciones: {e}", exc_info=True)

    async def cmd_status(self, args):
        """Muestra estado del conector."""
        logger.info("📊 Obteniendo estado del conector...")

        # Estado básico
        if hasattr(self.connector, "status_dict"):
            status = self.connector.status_dict
            logger.info("\n📊 ESTADO DEL CONECTOR:")
            logger.info("─" * 80)
            for key, value in status.items():
                logger.info(f"  {key:20s} | {value}")

        # Si es ResilientConnector, mostrar más detalles
        if isinstance(self.connector, ResilientConnector):
            logger.info("\n📊 RESILIENT CONNECTOR:")
            logger.info("─" * 80)
            logger.info(f"  Connected: {self.connector._connected}")
            logger.info(f"  Session ID: {self.connector._session_id}")

    async def cmd_metrics(self, args):
        """Muestra métricas del conector."""
        logger.info("📊 Obteniendo métricas...")

        # Si es ResilientConnector
        if isinstance(self.connector, ResilientConnector):
            logger.info("\n📊 ORDER TRACKER METRICS:")
            logger.info("─" * 80)
            metrics = self.connector.get_order_tracker_metrics()
            for key, value in metrics.items():
                logger.info(f"  {key:25s} | {value}")

            logger.info("\n📊 ERROR CLASSIFIER METRICS:")
            logger.info("─" * 80)
            metrics = self.connector.get_error_classifier_metrics()
            for key, value in metrics.items():
                if isinstance(value, dict):
                    logger.info(f"  {key}:")
                    for k, v in value.items():
                        logger.info(f"    {k}: {v}")
                else:
                    logger.info(f"  {key:25s} | {value}")
        else:
            logger.warning("⚠️ Métricas solo disponibles en ResilientConnector")

    async def cmd_websocket_status(self, args):
        """Muestra estado del WebSocket."""
        logger.info("📊 Obteniendo estado de WebSocket...")

        # Acceder al conector subyacente si es ResilientConnector
        connector = self.connector._connector if isinstance(self.connector, ResilientConnector) else self.connector

        if hasattr(connector, "_ws") and connector._ws:
            logger.info("\n📊 WEBSOCKET STATUS:")
            logger.info("─" * 80)
            logger.info(f"  Connected: {connector._ws_connected}")

            if connector._ws_connected:
                metrics = connector._ws.get_metrics()
                for key, value in metrics.items():
                    logger.info(f"  {key:25s} | {value}")
        else:
            logger.warning("⚠️ WebSocket no habilitado")

    async def cmd_exit(self, args):
        """Comando: exit."""
        self.running = False


async def start_playground(exchange: str, testnet: bool = True):
    """
    Inicia el playground.

    Args:
        exchange: Nombre del exchange
        testnet: Si usar testnet o live
    """
    logger.info(f"🚀 Iniciando playground para: {exchange}")
    logger.info(f"🌐 Modo: {'TESTNET' if testnet else 'LIVE'}")

    # Crear conector base
    if exchange.lower() == "kraken":
        base_connector = KrakenConnector(
            mode="testing" if testnet else "live",
            enable_websocket=True,  # ← Habilitar WebSocket
        )
    else:
        raise ValueError(f"Exchange no soportado: {exchange}")

    # Envolver con ResilientConnector para agregar todas las mejoras
    connector = ResilientConnector(
        connector=base_connector,
        enable_state_recovery=False,  # Deshabilitado para playground
    )

    logger.info("✅ Conector creado con:")
    logger.info("  - Order Tracking")
    logger.info("  - Error Classification")
    logger.info("  - WebSocket (si disponible)")
    logger.info("  - Balance Cache + Fallback")

    # Crear y ejecutar playground
    playground = ConnectorPlayground(connector)
    await playground.start()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Playground interactivo para conectores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Playground de Kraken en testnet
  python -m utils.connector_playground --exchange kraken --testnet

  # Playground de Kraken en live
  python -m utils.connector_playground --exchange kraken --live
        """,
    )

    parser.add_argument(
        "--exchange",
        type=str,
        required=True,
        choices=["kraken", "binance"],
        help="Exchange a usar",
    )

    parser.add_argument("--testnet", action="store_true", help="Usar testnet (default: True)")

    parser.add_argument("--live", action="store_true", help="Usar live (default: False)")

    args = parser.parse_args()

    # Determinar si usar testnet o live
    testnet = not args.live if args.live else True

    # Ejecutar playground
    asyncio.run(start_playground(args.exchange, testnet))


if __name__ == "__main__":
    main()
