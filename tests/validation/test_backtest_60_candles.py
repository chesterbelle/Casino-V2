"""
Backtesting - 60 Velas de 1 Minuto.

Este script ejecuta backtesting con los datos históricos descargados,
usando la misma estrategia y balance inicial que el testing en vivo.

Usage:
    python tests/validation/test_backtest_60_candles.py --data historical_data_20241106_2000.json
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from tests.validation.validation_config import (
    COMMON_CONFIG,
    get_backtest_results_path,
    get_timestamp_str,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Ejecuta backtesting y registra todos los datos.
    """

    def __init__(self, config: Dict[str, Any], candles: List[Dict[str, Any]]):
        self.config = config
        self.candles = candles

        # Datos a registrar
        self.test_info: Dict[str, Any] = {}
        self.signals: List[Dict[str, Any]] = []
        self.orders: List[Dict[str, Any]] = []
        self.balance_history: List[Dict[str, Any]] = []

        # Estado
        self.initial_balance: float = config["initial_balance"]
        self.current_balance: float = self.initial_balance
        self.candle_count: int = 0

    def generate_signal(self, candle: Dict[str, Any]) -> str:
        """
        Genera señal basada en estrategia simple (misma que testing en vivo).

        Args:
            candle: Datos de la vela actual

        Returns:
            "LONG", "SHORT", o None
        """
        # Misma estrategia que en testing en vivo
        if self.candle_count % 10 == 0 and self.candle_count > 0:
            signal = "LONG" if self.candle_count % 20 == 0 else "SHORT"

            # Registrar señal
            signal_data = {
                "timestamp": candle["timestamp"],
                "candle_index": self.candle_count - 1,
                "signal": signal,
                "confidence": 0.75,
                "indicators": {
                    "price": candle["close"],
                    "volume": candle["volume"],
                },
            }
            self.signals.append(signal_data)

            logger.info(f"📊 SEÑAL: {signal} @ ${candle['close']:,.2f}")

            return signal

        return None

    def execute_order(self, signal: str, candle: Dict[str, Any]):
        """
        Simula ejecución de orden.

        Args:
            signal: "LONG" o "SHORT"
            candle: Datos de la vela actual
        """
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

        logger.info(f"🚀 Orden {signal} | Entry: ${current_price:,.2f}")

        # Registrar orden
        order_data = {
            "timestamp": candle["timestamp"],
            "candle_index": self.candle_count - 1,
            "order_id": f"backtest_{self.candle_count}",
            "side": side,
            "amount": amount,
            "entry_price": current_price,
            "exit_price": None,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "status": "open",
            "close_reason": None,
            "pnl": None,
            "fees": 0.0,
        }
        self.orders.append(order_data)

    def check_open_positions(self, candle: Dict[str, Any]):
        """
        Verifica si alguna orden abierta alcanzó TP o SL.

        Args:
            candle: Vela actual
        """
        for order in self.orders:
            if order["status"] == "open":
                current_price = candle["close"]

                # Check TP
                if (order["side"] == "buy" and current_price >= order["tp_price"]) or (
                    order["side"] == "sell" and current_price <= order["tp_price"]
                ):
                    order["status"] = "closed"
                    order["close_reason"] = "tp"
                    order["exit_price"] = order["tp_price"]

                # Check SL
                elif (order["side"] == "buy" and current_price <= order["sl_price"]) or (
                    order["side"] == "sell" and current_price >= order["sl_price"]
                ):
                    order["status"] = "closed"
                    order["close_reason"] = "sl"
                    order["exit_price"] = order["sl_price"]

                # Calcular PnL si cerró
                if order["status"] == "closed":
                    if order["side"] == "buy":
                        order["pnl"] = (order["exit_price"] - order["entry_price"]) * order["amount"]
                    else:
                        order["pnl"] = (order["entry_price"] - order["exit_price"]) * order["amount"]

                    self.current_balance += order["pnl"]
                    logger.info(
                        f"🎯 Orden cerrada por {order['close_reason'].upper()} | " f"PnL: ${order['pnl']:+,.2f}"
                    )

    def update_balance(self, candle: Dict[str, Any]):
        """Registra balance actual."""
        self.balance_history.append(
            {
                "timestamp": candle["timestamp"],
                "candle_index": self.candle_count - 1,
                "balance": self.current_balance,
                "equity": self.current_balance,
            }
        )

    def run(self):
        """Ejecuta el backtest completo."""
        logger.info("=" * 80)
        logger.info("🔄 BACKTESTING - 60 VELAS")
        logger.info("=" * 80)
        logger.info(f"Balance inicial: ${self.initial_balance:,.2f}\n")

        # Registrar info del test
        self.test_info = {
            "exchange": self.config["exchange"],
            "symbol": self.config["symbol"],
            "timeframe": self.config["timeframe"],
            "start_time": datetime.fromtimestamp(self.candles[0]["timestamp"] / 1000).isoformat(),
            "end_time": datetime.fromtimestamp(self.candles[-1]["timestamp"] / 1000).isoformat(),
            "initial_balance": self.initial_balance,
            "final_balance": None,
            "mode": "backtest",
        }

        # Registrar balance inicial
        self.balance_history.append(
            {
                "timestamp": self.candles[0]["timestamp"],
                "candle_index": 0,
                "balance": self.initial_balance,
                "equity": self.initial_balance,
            }
        )

        # Procesar cada vela
        for candle in self.candles:
            self.candle_count += 1

            logger.info(
                f"[{self.candle_count:02d}/60] "
                f"C: ${candle['close']:,.2f} | "
                f"Balance: ${self.current_balance:,.2f}"
            )

            # Generar señal
            signal = self.generate_signal(candle)

            # Ejecutar orden si hay señal
            if signal:
                self.execute_order(signal, candle)

            # Verificar posiciones abiertas
            self.check_open_positions(candle)

            # Actualizar balance
            self.update_balance(candle)

        # Finalizar
        self.test_info["final_balance"] = self.current_balance

        logger.info("\n" + "=" * 80)
        logger.info("✅ BACKTEST COMPLETADO")
        logger.info("=" * 80)
        logger.info(f"Velas procesadas: {len(self.candles)}")
        logger.info(f"Señales generadas: {len(self.signals)}")
        logger.info(f"Órdenes ejecutadas: {len(self.orders)}")
        logger.info(f"Balance inicial: ${self.initial_balance:,.2f}")
        logger.info(f"Balance final: ${self.current_balance:,.2f}")
        logger.info(f"PnL: ${self.current_balance - self.initial_balance:+,.2f}")

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calcula métricas del backtest."""
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
            "max_drawdown": 0.0,
            "max_drawdown_percent": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
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


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Backtesting - 60 velas")
    parser.add_argument("--data", type=str, required=True, help="Path al archivo de datos históricos")
    args = parser.parse_args()

    # Cargar datos históricos
    logger.info(f"📂 Cargando datos de: {args.data}")
    with open(args.data, "r") as f:
        historical_data = json.load(f)

    candles = historical_data["candles"]
    logger.info(f"✅ Cargadas {len(candles)} velas\n")

    # Crear runner
    runner = BacktestRunner(COMMON_CONFIG, candles)

    # Ejecutar backtest
    runner.run()

    # Guardar resultados
    timestamp = get_timestamp_str()
    filepath = get_backtest_results_path(timestamp)
    runner.save_results(filepath)

    logger.info("\n" + "=" * 80)
    logger.info("🏁 BACKTEST COMPLETADO")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
