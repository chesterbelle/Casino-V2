"""
Comparación: Testing vs Backtesting.

Este script compara los resultados del testing en vivo vs backtesting
y genera un reporte detallado de las diferencias.

Usage:
    python tests/validation/compare_testing_vs_backtest.py \
        --live test_live_results_20241106_2000.json \
        --backtest test_backtest_results_20241106_2000.json
"""

import argparse
import json
import logging
from typing import Any, Dict, List

from tests.validation.validation_config import (
    TOLERANCES,
    get_comparison_report_path,
    get_timestamp_str,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ResultsComparator:
    """
    Compara resultados de testing vs backtesting.
    """

    def __init__(self, live_results: Dict, backtest_results: Dict):
        self.live = live_results
        self.backtest = backtest_results
        self.report_lines: List[str] = []
        self.differences: List[Dict[str, Any]] = []
        self.validation_passed = True

    def add_line(self, line: str = ""):
        """Agrega línea al reporte."""
        self.report_lines.append(line)
        print(line)

    def add_section(self, title: str):
        """Agrega sección al reporte."""
        self.add_line()
        self.add_line("=" * 80)
        self.add_line(title)
        self.add_line("=" * 80)

    def compare_test_info(self):
        """Compara información general del test."""
        self.add_section("📊 INFORMACIÓN GENERAL")

        live_info = self.live["test_info"]
        backtest_info = self.backtest["test_info"]

        self.add_line(f"\nTesting en Vivo:")
        self.add_line(f"  Período: {live_info['start_time']} - {live_info['end_time']}")
        self.add_line(f"  Velas: {len(self.live['candles'])}")
        self.add_line(f"  Balance inicial: ${live_info['initial_balance']:,.2f}")
        self.add_line(f"  Balance final: ${live_info['final_balance']:,.2f}")

        self.add_line(f"\nBacktesting:")
        self.add_line(f"  Período: {backtest_info['start_time']} - {backtest_info['end_time']}")
        self.add_line(f"  Velas: {len(self.backtest['candles'])}")
        self.add_line(f"  Balance inicial: ${backtest_info['initial_balance']:,.2f}")
        self.add_line(f"  Balance final: ${backtest_info['final_balance']:,.2f}")

        # Validar que coinciden
        if len(self.live["candles"]) != len(self.backtest["candles"]):
            self.add_line(f"\n❌ Número de velas diferente!")
            self.validation_passed = False
        else:
            self.add_line(f"\n✅ Número de velas coincide: {len(self.live['candles'])}")

    def compare_operations(self):
        """Compara operaciones ejecutadas."""
        self.add_section("📈 OPERACIONES")

        live_orders = self.live["orders"]
        backtest_orders = self.backtest["orders"]

        self.add_line(f"\nTesting: {len(live_orders)} operaciones")
        self.add_line(f"Backtesting: {len(backtest_orders)} operaciones")

        if len(live_orders) != len(backtest_orders):
            self.add_line(f"\n❌ Número de operaciones diferente!")
            self.validation_passed = False
            return
        else:
            self.add_line(f"✅ Número de operaciones coincide\n")

        # Comparar operación por operación
        self.add_line("Comparación operación por operación:")
        self.add_line("-" * 80)

        for i, (live_order, backtest_order) in enumerate(zip(live_orders, backtest_orders), 1):
            self.add_line(f"\nOperación #{i}:")

            # Comparar side
            if live_order["side"] != backtest_order["side"]:
                self.add_line(f"  ❌ Side diferente: live={live_order['side']}, " f"backtest={backtest_order['side']}")
                self.validation_passed = False
            else:
                self.add_line(f"  ✅ Side: {live_order['side']}")

            # Comparar entry price
            live_entry = live_order["entry_price"]
            backtest_entry = backtest_order["entry_price"]
            price_diff_percent = abs(live_entry - backtest_entry) / live_entry

            if price_diff_percent > TOLERANCES["price_difference_percent"]:
                self.add_line(
                    f"  ⚠️  Entry price: live=${live_entry:,.2f}, "
                    f"backtest=${backtest_entry:,.2f} "
                    f"(diff={price_diff_percent*100:.3f}%)"
                )
                self.differences.append(
                    {
                        "type": "entry_price",
                        "operation": i,
                        "live": live_entry,
                        "backtest": backtest_entry,
                        "diff_percent": price_diff_percent * 100,
                    }
                )
            else:
                self.add_line(f"  ✅ Entry price: ${live_entry:,.2f}")

            # Comparar PnL si ambas están cerradas
            if live_order["status"] == "closed" and backtest_order["status"] == "closed":
                live_pnl = live_order.get("pnl", 0)
                backtest_pnl = backtest_order.get("pnl", 0)

                if live_pnl != 0:
                    pnl_diff_percent = abs(live_pnl - backtest_pnl) / abs(live_pnl)
                else:
                    pnl_diff_percent = 0

                if pnl_diff_percent > TOLERANCES["pnl_difference_percent"]:
                    self.add_line(
                        f"  ⚠️  PnL: live=${live_pnl:+,.2f}, "
                        f"backtest=${backtest_pnl:+,.2f} "
                        f"(diff={pnl_diff_percent*100:.3f}%)"
                    )
                    self.differences.append(
                        {
                            "type": "pnl",
                            "operation": i,
                            "live": live_pnl,
                            "backtest": backtest_pnl,
                            "diff_percent": pnl_diff_percent * 100,
                        }
                    )
                else:
                    self.add_line(f"  ✅ PnL: ${live_pnl:+,.2f}")

    def compare_balance(self):
        """Compara balance final."""
        self.add_section("💰 BALANCE FINAL")

        live_balance = self.live["test_info"]["final_balance"]
        backtest_balance = self.backtest["test_info"]["final_balance"]

        self.add_line(f"\nTesting: ${live_balance:,.2f}")
        self.add_line(f"Backtesting: ${backtest_balance:,.2f}")

        diff = backtest_balance - live_balance
        diff_percent = abs(diff) / live_balance if live_balance != 0 else 0

        self.add_line(f"Diferencia: ${diff:+,.2f} ({diff_percent*100:+.3f}%)")

        if diff_percent > TOLERANCES["balance_difference_percent"]:
            self.add_line(f"\n⚠️  Diferencia mayor a tolerancia aceptable!")
            self.differences.append(
                {
                    "type": "final_balance",
                    "live": live_balance,
                    "backtest": backtest_balance,
                    "diff": diff,
                    "diff_percent": diff_percent * 100,
                }
            )
        else:
            self.add_line(f"\n✅ Diferencia dentro de tolerancia")

    def compare_metrics(self):
        """Compara métricas de rendimiento."""
        self.add_section("📊 MÉTRICAS DE RENDIMIENTO")

        live_metrics = self.live["metrics"]
        backtest_metrics = self.backtest["metrics"]

        # Win rate
        self.add_line(f"\nWin Rate:")
        self.add_line(f"  Testing: {live_metrics['win_rate']*100:.1f}%")
        self.add_line(f"  Backtesting: {backtest_metrics['win_rate']*100:.1f}%")

        if live_metrics["win_rate"] != backtest_metrics["win_rate"]:
            self.add_line(f"  ⚠️  Win rate diferente!")
            self.validation_passed = False
        else:
            self.add_line(f"  ✅ Win rate coincide")

        # Total PnL
        self.add_line(f"\nTotal PnL:")
        self.add_line(f"  Testing: ${live_metrics['total_pnl']:+,.2f}")
        self.add_line(f"  Backtesting: ${backtest_metrics['total_pnl']:+,.2f}")

        pnl_diff = backtest_metrics["total_pnl"] - live_metrics["total_pnl"]
        self.add_line(f"  Diferencia: ${pnl_diff:+,.2f}")

    def generate_summary(self):
        """Genera resumen final."""
        self.add_section("🎯 RESULTADO FINAL")

        if self.validation_passed and len(self.differences) == 0:
            self.add_line("\n✅ VALIDACIÓN EXITOSA")
            self.add_line("Backtesting produce los mismos resultados que testing en vivo")
        elif len(self.differences) > 0:
            self.add_line(f"\n⚠️  VALIDACIÓN CON ADVERTENCIAS")
            self.add_line(f"Se encontraron {len(self.differences)} diferencias:")
            for diff in self.differences:
                self.add_line(f"  - {diff['type']}: {diff.get('diff_percent', 0):.3f}%")
            self.add_line("\nEstas diferencias pueden ser aceptables debido a:")
            self.add_line("  - Slippage en ejecución real")
            self.add_line("  - Diferencias de timing")
            self.add_line("  - Actualizaciones de datos de mercado")
        else:
            self.add_line("\n❌ VALIDACIÓN FALLIDA")
            self.add_line("Backtesting NO produce los mismos resultados que testing")

    def run(self):
        """Ejecuta comparación completa."""
        self.add_section("COMPARACIÓN: Testing vs Backtesting")

        self.compare_test_info()
        self.compare_operations()
        self.compare_balance()
        self.compare_metrics()
        self.generate_summary()

    def save_report(self, filepath: str):
        """Guarda reporte en archivo."""
        with open(filepath, "w") as f:
            f.write("\n".join(self.report_lines))

        logger.info(f"\n💾 Reporte guardado en: {filepath}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Comparación testing vs backtesting")
    parser.add_argument("--live", type=str, required=True, help="Path a resultados de testing en vivo")
    parser.add_argument(
        "--backtest",
        type=str,
        required=True,
        help="Path a resultados de backtesting",
    )
    args = parser.parse_args()

    # Cargar resultados
    logger.info(f"📂 Cargando resultados de testing: {args.live}")
    with open(args.live, "r") as f:
        live_results = json.load(f)

    logger.info(f"📂 Cargando resultados de backtesting: {args.backtest}")
    with open(args.backtest, "r") as f:
        backtest_results = json.load(f)

    # Crear comparador
    comparator = ResultsComparator(live_results, backtest_results)

    # Ejecutar comparación
    comparator.run()

    # Guardar reporte
    timestamp = get_timestamp_str()
    filepath = get_comparison_report_path(timestamp)
    comparator.save_report(filepath)

    logger.info("\n" + "=" * 80)
    logger.info("🏁 COMPARACIÓN COMPLETADA")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
