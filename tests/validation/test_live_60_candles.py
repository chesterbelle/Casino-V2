"""
Testing en Vivo - 60 Velas de 1 Minuto.

Este script ejecuta una estrategia en modo testing (Kraken testnet) durante
60 velas de 1 minuto y registra todos los datos para comparación posterior
con backtesting.

Usage:
    python tests/validation/test_live_60_candles.py
    python tests/validation/test_live_60_candles.py --strategy MyStrategy
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from exchanges.connectors import KrakenConnector
from tests.validation.validation_config import (
    COMMON_CONFIG,
    get_live_results_path,
    get_timestamp_str,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class LiveTestRunner:
    """
    Ejecuta testing en vivo y registra todos los datos.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connector: Optional[KrakenConnector] = None

        # Datos a registrar
        self.test_info: Dict[str, Any] = {}
        self.candles: List[Dict[str, Any]] = []
        self.signals: List[Dict[str, Any]] = []
        self.orders: List[Dict[str, Any]] = []
        self.balance_history: List[Dict[str, Any]] = []

        # Estado
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.initial_balance: float = 0.0
        self.current_balance: float = 0.0
        self.candle_count: int = 0

    async def connect(self):
        """Conecta al exchange."""
        logger.info("=" * 80)
        logger.info("🧪 TESTING EN VIVO - 60 VELAS DE 1 MINUTO")
        logger.info("=" * 80)

        logger.info(f"\n📊 Configuración:")
        logger.info(f"  Exchange: {self.config['exchange']}")
        logger.info(f"  Symbol: {self.config['symbol']}")
        logger.info(f"  Timeframe: {self.config['timeframe']}")
        logger.info(f"  Num Candles: {self.config['num_candles']}")
        logger.info(f"  Initial Balance: ${self.config['initial_balance']:,.2f}")

        # Conectar a Kraken testnet
        self.connector = KrakenConnector(testnet=True)
        await self.connector.connect()

        # Obtener balance inicial
        balance_data = await self.connector.fetch_balance()
        self.initial_balance = float(balance_data.get("free", {}).get("USD", 0))
        self.current_balance = self.initial_balance

        logger.info(f"\n💰 Balance inicial en testnet: ${self.initial_balance:,.2f}")

        # Registrar info del test
        self.start_time = datetime.now()
        self.test_info = {
            "exchange": self.config["exchange"],
            "symbol": self.config["symbol"],
            "timeframe": self.config["timeframe"],
            "start_time": self.start_time.isoformat(),
            "end_time": None,  # Se llenará al final
            "initial_balance": self.initial_balance,
            "final_balance": None,  # Se llenará al final
            "mode": "live",
        }

        # Registrar balance inicial
        self.balance_history.append(
            {
                "timestamp": int(self.start_time.timestamp() * 1000),
                "candle_index": 0,
                "balance": self.initial_balance,
                "equity": self.initial_balance,
            }
        )

    async def fetch_and_record_candle(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la última vela y la registra.

        Returns:
            Datos de la vela o None si hay error
        """
        try:
            # Fetch última vela
            ohlcv = await self.connector.fetch_ohlcv(
                symbol=self.config["symbol"], timeframe=self.config["timeframe"], limit=1
            )

            if not ohlcv:
                logger.warning("⚠️  No se recibieron datos de vela")
                return None

            candle_data = ohlcv[0]

            # Convertir a formato estándar
            candle = {
                "timestamp": int(candle_data["timestamp"]),
                "open": float(candle_data["open"]),
                "high": float(candle_data["high"]),
                "low": float(candle_data["low"]),
                "close": float(candle_data["close"]),
                "volume": float(candle_data["volume"]),
            }

            # Registrar vela
            self.candles.append(candle)
            self.candle_count += 1

            logger.info(
                f"[{self.candle_count:02d}/60] "
                f"O: ${candle['open']:,.2f} | "
                f"H: ${candle['high']:,.2f} | "
                f"L: ${candle['low']:,.2f} | "
                f"C: ${candle['close']:,.2f} | "
                f"V: {candle['volume']:.2f}"
            )

            return candle

        except Exception as e:
            logger.error(f"❌ Error obteniendo vela: {e}")
            return None

    def generate_signal(self, candle: Dict[str, Any]) -> Optional[str]:
        """
        Genera señal basada en estrategia simple.

        Por ahora usa una estrategia simple de ejemplo.
        TODO: Integrar con sistema de estrategias real.

        Args:
            candle: Datos de la vela actual

        Returns:
            "LONG", "SHORT", o None
        """
        # Estrategia simple de ejemplo: comprar cada 10 velas
        if self.candle_count % 10 == 0 and self.candle_count > 0:
            signal = "LONG" if self.candle_count % 20 == 0 else "SHORT"

            # Registrar señal
            signal_data = {
                "timestamp": candle["timestamp"],
                "candle_index": self.candle_count - 1,
                "signal": signal,
                "confidence": 0.75,  # Ejemplo
                "indicators": {
                    "price": candle["close"],
                    "volume": candle["volume"],
                },
            }
            self.signals.append(signal_data)

            logger.info(f"📊 SEÑAL GENERADA: {signal} @ ${candle['close']:,.2f}")

            return signal

        return None

    async def execute_order(self, signal: str, candle: Dict[str, Any]):
        """
        Ejecuta orden basada en señal.

        Args:
            signal: "LONG" o "SHORT"
            candle: Datos de la vela actual
        """
        try:
            side = "buy" if signal == "LONG" else "sell"
            amount = self.config["strategy_params"]["position_size"]

            # Calcular TP/SL
            current_price = candle["close"]
            tp_percent = self.config["strategy_params"]["tp_percent"]
            sl_percent = self.config["strategy_params"]["sl_percent"]

            if signal == "LONG":
                tp_price = current_price * (1 + tp_percent)
                sl_price = current_price * (1 - sl_percent)
            else:
                tp_price = current_price * (1 - tp_percent)
                sl_price = current_price * (1 + sl_percent)

            logger.info(f"🚀 Ejecutando orden {signal}...")
            logger.info(f"  Entry: ${current_price:,.2f}")
            logger.info(f"  TP: ${tp_price:,.2f}")
            logger.info(f"  SL: ${sl_price:,.2f}")

            # Ejecutar orden con TP/SL
            order_result = await self.connector.create_order_with_tpsl(
                symbol=self.config["symbol"],
                side=side,
                amount=amount,
                price=None,  # Market order
                order_type="market",
                tp_price=tp_price,
                sl_price=sl_price,
                params={},
            )

            # Registrar orden
            order_data = {
                "timestamp": int(datetime.now().timestamp() * 1000),
                "candle_index": self.candle_count - 1,
                "order_id": order_result.get("id"),
                "side": side,
                "amount": amount,
                "entry_price": float(order_result.get("price", current_price)),
                "exit_price": None,  # Se llenará cuando cierre
                "tp_price": tp_price,
                "sl_price": sl_price,
                "status": "open",
                "close_reason": None,
                "pnl": None,
                "fees": 0.0,  # TODO: Calcular fees reales
            }
            self.orders.append(order_data)

            logger.info(f"✅ Orden ejecutada | ID: {order_result.get('id')}")

        except Exception as e:
            logger.error(f"❌ Error ejecutando orden: {e}")

    async def check_open_positions(self):
        """
        Verifica posiciones abiertas y actualiza órdenes cerradas.
        """
        try:
            positions = await self.connector.fetch_positions()

            # Si no hay posiciones, alguna orden se cerró
            if not positions:
                # Buscar órdenes abiertas y marcarlas como cerradas
                for order in self.orders:
                    if order["status"] == "open":
                        order["status"] = "closed"
                        order["close_reason"] = "tp_or_sl"  # Asumimos TP o SL
                        order["exit_price"] = order["tp_price"]  # Simplificación

                        # Calcular PnL simple
                        if order["side"] == "buy":
                            order["pnl"] = (order["exit_price"] - order["entry_price"]) * order["amount"]
                        else:
                            order["pnl"] = (order["entry_price"] - order["exit_price"]) * order["amount"]

                        logger.info(f"🎯 Orden cerrada | PnL: ${order['pnl']:+,.2f}")

        except Exception as e:
            logger.error(f"❌ Error verificando posiciones: {e}")

    async def update_balance(self):
        """Actualiza balance actual."""
        try:
            balance_data = await self.connector.fetch_balance()
            self.current_balance = float(balance_data.get("free", {}).get("USD", 0))

            # Registrar balance
            self.balance_history.append(
                {
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "candle_index": self.candle_count - 1,
                    "balance": self.current_balance,
                    "equity": self.current_balance,  # Simplificación
                }
            )

        except Exception as e:
            logger.error(f"❌ Error actualizando balance: {e}")

    async def run(self):
        """Ejecuta el test completo."""
        try:
            await self.connect()

            logger.info("\n" + "=" * 80)
            logger.info("📊 INICIANDO CAPTURA DE 60 VELAS")
            logger.info("=" * 80)
            logger.info("Esperando velas cada 60 segundos...\n")

            # Capturar 60 velas
            while self.candle_count < self.config["num_candles"]:
                # Obtener vela
                candle = await self.fetch_and_record_candle()

                if candle:
                    # Generar señal
                    signal = self.generate_signal(candle)

                    # Ejecutar orden si hay señal
                    if signal:
                        await self.execute_order(signal, candle)

                    # Verificar posiciones abiertas
                    await self.check_open_positions()

                    # Actualizar balance
                    await self.update_balance()

                # Esperar 60 segundos para siguiente vela
                if self.candle_count < self.config["num_candles"]:
                    await asyncio.sleep(60)

            # Finalizar
            self.end_time = datetime.now()
            self.test_info["end_time"] = self.end_time.isoformat()
            self.test_info["final_balance"] = self.current_balance

            logger.info("\n" + "=" * 80)
            logger.info("✅ CAPTURA COMPLETADA")
            logger.info("=" * 80)
            logger.info(f"Velas capturadas: {len(self.candles)}")
            logger.info(f"Señales generadas: {len(self.signals)}")
            logger.info(f"Órdenes ejecutadas: {len(self.orders)}")
            logger.info(f"Balance inicial: ${self.initial_balance:,.2f}")
            logger.info(f"Balance final: ${self.current_balance:,.2f}")
            logger.info(f"PnL: ${self.current_balance - self.initial_balance:+,.2f}")

        except KeyboardInterrupt:
            logger.info("\n⚠️  Test interrumpido por usuario")
        except Exception as e:
            logger.error(f"\n❌ Error durante test: {e}", exc_info=True)
        finally:
            if self.connector:
                await self.connector.close()

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calcula métricas del test."""
        total_trades = len([o for o in self.orders if o["status"] == "closed"])
        winning_trades = len([o for o in self.orders if o.get("pnl", 0) > 0])
        losing_trades = len([o for o in self.orders if o.get("pnl", 0) < 0])

        total_pnl = sum(o.get("pnl", 0) for o in self.orders if o["status"] == "closed")
        total_fees = sum(o.get("fees", 0) for o in self.orders)

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0.0,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "net_pnl": total_pnl - total_fees,
            "max_drawdown": 0.0,  # TODO: Calcular
            "max_drawdown_percent": 0.0,  # TODO: Calcular
            "sharpe_ratio": 0.0,  # TODO: Calcular
            "profit_factor": 0.0,  # TODO: Calcular
        }

    def save_results(self, filepath: str):
        """Guarda resultados en archivo JSON."""
        results = {
            "test_info": self.test_info,
            "candles": self.candles,
            "signals": self.signals,
            "orders": self.orders,
            "balance_history": self.balance_history,
            "metrics": self.calculate_metrics(),
        }

        with open(filepath, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"\n💾 Resultados guardados en: {filepath}")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Testing en vivo - 60 velas")
    parser.add_argument("--strategy", type=str, default=COMMON_CONFIG.get("strategy"), help="Estrategia a usar")
    args = parser.parse_args()

    # Crear runner
    runner = LiveTestRunner(COMMON_CONFIG)

    # Ejecutar test
    await runner.run()

    # Guardar resultados
    timestamp = get_timestamp_str()
    filepath = get_live_results_path(timestamp)
    runner.save_results(filepath)

    logger.info("\n" + "=" * 80)
    logger.info("🏁 TEST COMPLETADO")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
