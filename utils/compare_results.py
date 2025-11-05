#!/usr/bin/env python3
"""
Compare Results - Casino V2

Compara resultados de testing vs backtest para validar consistencia.

Usage:
    python utils/compare_results.py \
        --testing=logs/round1_testing.log \
        --backtest=logs/round1_backtest.log \
        --output=reports/round1_comparison.md
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def parse_log_file(log_path: str) -> Dict:
    """
    Parsea archivo de log y extrae métricas clave.

    Args:
        log_path: Ruta al archivo de log

    Returns:
        Dict con métricas extraídas
    """
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    metrics = {
        "mode": None,
        "initial_balance": None,
        "final_balance": None,
        "final_equity": None,
        "net_pnl": None,
        "total_trades": None,
        "candles_processed": None,
        "signals_detected": None,
        "orders_executed": None,
        "wins": None,
        "losses": None,
        "win_rate": None,
        "player_steps": [],
        "orders": [],
    }

    # Detectar modo
    if "TESTING" in content:
        metrics["mode"] = "TESTING"
    elif "BACKTEST" in content:
        metrics["mode"] = "BACKTEST"

    # Extraer balance inicial
    match = re.search(r"Initial Balance:\s+\$?([\d,]+\.?\d*)", content)
    if match:
        metrics["initial_balance"] = float(match.group(1).replace(",", ""))

    # Extraer balance final
    match = re.search(r"Final Balance:\s+\$?([\d,]+\.?\d*)", content)
    if match:
        metrics["final_balance"] = float(match.group(1).replace(",", ""))

    # Extraer equity final
    match = re.search(r"Final Equity:\s+\$?([\d,]+\.?\d*)", content)
    if match:
        metrics["final_equity"] = float(match.group(1).replace(",", ""))

    # Extraer PnL
    match = re.search(r"Net PnL:\s+\$?([+-]?[\d,]+\.?\d*)", content)
    if match:
        metrics["net_pnl"] = float(match.group(1).replace(",", ""))

    # Extraer total trades
    match = re.search(r"Total Trades:\s+(\d+)", content)
    if match:
        metrics["total_trades"] = int(match.group(1))

    # Extraer candles procesadas
    match = re.search(r"Candles:\s+(\d+)", content)
    if match:
        metrics["candles_processed"] = int(match.group(1))

    # Extraer señales detectadas
    match = re.search(r"Signals:\s+(\d+)", content)
    if match:
        metrics["signals_detected"] = int(match.group(1))

    # Extraer órdenes ejecutadas
    match = re.search(r"Orders:\s+(\d+)", content)
    if match:
        metrics["orders_executed"] = int(match.group(1))

    # Extraer wins/losses
    match = re.search(r"Win rate:\s+([\d.]+)%", content)
    if match:
        metrics["win_rate"] = float(match.group(1))

    # Extraer player steps de los logs de progreso
    step_matches = re.findall(r"Player step:\s+(\d+)", content)
    if step_matches:
        metrics["player_steps"] = [int(s) for s in step_matches]

    # Extraer órdenes ejecutadas
    order_matches = re.findall(r"Order built \| (BUY|SELL) ([\d.]+) @ ([\d.]+)", content)
    if order_matches:
        metrics["orders"] = [{"side": m[0], "amount": float(m[1]), "price": float(m[2])} for m in order_matches]

    return metrics


def calculate_difference(value1: float, value2: float) -> Tuple[float, float]:
    """
    Calcula diferencia absoluta y porcentual.

    Args:
        value1: Primer valor
        value2: Segundo valor

    Returns:
        (diferencia_absoluta, diferencia_porcentual)
    """
    if value1 is None or value2 is None:
        return None, None

    diff_abs = value2 - value1
    diff_pct = (diff_abs / value1 * 100) if value1 != 0 else 0

    return diff_abs, diff_pct


def generate_comparison_report(testing_metrics: Dict, backtest_metrics: Dict, output_path: str = None) -> str:
    """
    Genera reporte de comparación en formato Markdown.

    Args:
        testing_metrics: Métricas de testing mode
        backtest_metrics: Métricas de backtest mode
        output_path: Ruta del archivo de salida (opcional)

    Returns:
        String con el reporte en Markdown
    """
    report_lines = []

    # Header
    report_lines.append("# 📊 COMPARACIÓN: Testing vs Backtest")
    report_lines.append("")
    report_lines.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Balance Comparison
    report_lines.append("## 💰 BALANCE")
    report_lines.append("")
    report_lines.append("| Métrica | Testing | Backtest | Diferencia |")
    report_lines.append("|---------|---------|----------|------------|")

    # Initial Balance
    t_init = testing_metrics.get("initial_balance")
    b_init = backtest_metrics.get("initial_balance")
    if t_init and b_init:
        diff_abs, diff_pct = calculate_difference(t_init, b_init)
        report_lines.append(
            f"| Balance Inicial | ${t_init:,.2f} | ${b_init:,.2f} | " f"${diff_abs:+,.2f} ({diff_pct:+.2f}%) |"
        )

    # Final Balance
    t_final = testing_metrics.get("final_balance")
    b_final = backtest_metrics.get("final_balance")
    if t_final and b_final:
        diff_abs, diff_pct = calculate_difference(t_final, b_final)
        status = "✅" if abs(diff_pct) <= 10 else "❌"
        report_lines.append(
            f"| Balance Final | ${t_final:,.2f} | ${b_final:,.2f} | " f"${diff_abs:+,.2f} ({diff_pct:+.2f}%) {status} |"
        )

    # Net PnL
    t_pnl = testing_metrics.get("net_pnl")
    b_pnl = backtest_metrics.get("net_pnl")
    if t_pnl is not None and b_pnl is not None:
        diff_abs = b_pnl - t_pnl
        report_lines.append(f"| Net PnL | ${t_pnl:+,.2f} | ${b_pnl:+,.2f} | ${diff_abs:+,.2f} |")

    report_lines.append("")

    # Trading Activity
    report_lines.append("## 📈 ACTIVIDAD DE TRADING")
    report_lines.append("")
    report_lines.append("| Métrica | Testing | Backtest | Diferencia |")
    report_lines.append("|---------|---------|----------|------------|")

    # Candles
    t_candles = testing_metrics.get("candles_processed")
    b_candles = backtest_metrics.get("candles_processed")
    if t_candles and b_candles:
        diff = b_candles - t_candles
        status = "✅" if diff == 0 else "⚠️"
        report_lines.append(f"| Velas Procesadas | {t_candles} | {b_candles} | {diff:+d} {status} |")

    # Signals
    t_signals = testing_metrics.get("signals_detected")
    b_signals = backtest_metrics.get("signals_detected")
    if t_signals and b_signals:
        diff = b_signals - t_signals
        status = "✅" if diff == 0 else "❌"
        report_lines.append(f"| Señales Detectadas | {t_signals} | {b_signals} | {diff:+d} {status} |")

    # Orders
    t_orders = testing_metrics.get("orders_executed")
    b_orders = backtest_metrics.get("orders_executed")
    if t_orders and b_orders:
        diff = b_orders - t_orders
        status = "✅" if abs(diff) <= 1 else "❌"
        report_lines.append(f"| Órdenes Ejecutadas | {t_orders} | {b_orders} | {diff:+d} {status} |")

    # Trades
    t_trades = testing_metrics.get("total_trades")
    b_trades = backtest_metrics.get("total_trades")
    if t_trades is not None and b_trades is not None:
        diff = b_trades - t_trades
        status = "✅" if diff == 0 else "⚠️"
        report_lines.append(f"| Trades Cerrados | {t_trades} | {b_trades} | {diff:+d} {status} |")

    report_lines.append("")

    # Player Steps
    report_lines.append("## 🎲 PROGRESIÓN PAROLI")
    report_lines.append("")

    t_steps = testing_metrics.get("player_steps", [])
    b_steps = backtest_metrics.get("player_steps", [])

    if t_steps or b_steps:
        report_lines.append("| Vela | Testing Step | Backtest Step | Status |")
        report_lines.append("|------|--------------|---------------|--------|")

        max_len = max(len(t_steps), len(b_steps))
        for i in range(max_len):
            t_step = t_steps[i] if i < len(t_steps) else "N/A"
            b_step = b_steps[i] if i < len(b_steps) else "N/A"
            status = "✅" if t_step == b_step else "❌"
            report_lines.append(f"| {i*10} | {t_step} | {b_step} | {status} |")
    else:
        report_lines.append("⚠️ No se encontraron datos de progresión en los logs")

    report_lines.append("")

    # Summary
    report_lines.append("## 📋 RESUMEN")
    report_lines.append("")

    # Calculate overall status
    issues = []

    if t_signals and b_signals and t_signals != b_signals:
        issues.append(f"❌ **Señales diferentes:** Testing={t_signals}, Backtest={b_signals}")

    if t_orders and b_orders and abs(t_orders - b_orders) > 1:
        issues.append(f"❌ **Órdenes diferentes:** Testing={t_orders}, Backtest={b_orders}")

    if t_final and b_final:
        _, diff_pct = calculate_difference(t_final, b_final)
        if abs(diff_pct) > 10:
            issues.append(f"❌ **Balance final difiere >{10}%:** {diff_pct:+.2f}%")

    if t_steps and b_steps and t_steps != b_steps:
        issues.append(f"❌ **Progresión Paroli diferente:** Testing={t_steps}, Backtest={b_steps}")

    if issues:
        report_lines.append("### 🚨 Problemas Identificados:")
        report_lines.append("")
        for issue in issues:
            report_lines.append(f"- {issue}")
        report_lines.append("")
    else:
        report_lines.append("### ✅ Sin Problemas Críticos")
        report_lines.append("")
        report_lines.append("Los resultados son consistentes entre testing y backtest.")
        report_lines.append("")

    # Recommendations
    report_lines.append("## 💡 RECOMENDACIONES")
    report_lines.append("")

    if not issues:
        report_lines.append("✅ **Los modos están alineados.** Continuar con testing más largo.")
    else:
        report_lines.append("⚠️ **Requiere investigación:**")
        report_lines.append("")
        if any("Señales" in i for i in issues):
            report_lines.append("1. Verificar que sensores usan mismos datos en ambos modos")
        if any("Órdenes" in i for i in issues):
            report_lines.append("2. Verificar lógica de BuildOrderStage")
        if any("Balance" in i for i in issues):
            report_lines.append("3. Verificar cálculo de TP/SL y fees")
        if any("Progresión" in i for i in issues):
            report_lines.append("4. Verificar detección de cierres y handle_trade_outcome")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("*Generado automáticamente por compare_results.py*")

    # Join all lines
    report = "\n".join(report_lines)

    # Save to file if output path provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report, encoding="utf-8")
        print(f"✅ Reporte guardado en: {output_path}")

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compara resultados de testing vs backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplo:
  python utils/compare_results.py \\
      --testing=logs/round1_testing.log \\
      --backtest=logs/round1_backtest.log \\
      --output=reports/round1_comparison.md
        """,
    )

    parser.add_argument("--testing", type=str, required=True, help="Ruta al log de testing mode")

    parser.add_argument("--backtest", type=str, required=True, help="Ruta al log de backtest mode")

    parser.add_argument(
        "--output",
        type=str,
        help="Ruta del archivo de salida (default: imprime en consola)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📊 COMPARE RESULTS - Casino V2")
    print("=" * 60)

    # Parse logs
    print(f"\n📖 Parseando testing log: {args.testing}")
    testing_metrics = parse_log_file(args.testing)
    print(f"   Modo: {testing_metrics['mode']}")
    print(f"   Velas: {testing_metrics.get('candles_processed', 'N/A')}")
    print(f"   Órdenes: {testing_metrics.get('orders_executed', 'N/A')}")

    print(f"\n📖 Parseando backtest log: {args.backtest}")
    backtest_metrics = parse_log_file(args.backtest)
    print(f"   Modo: {backtest_metrics['mode']}")
    print(f"   Velas: {backtest_metrics.get('candles_processed', 'N/A')}")
    print(f"   Órdenes: {backtest_metrics.get('orders_executed', 'N/A')}")

    # Generate report
    print(f"\n📝 Generando reporte de comparación...")
    report = generate_comparison_report(testing_metrics, backtest_metrics, args.output)

    # Print to console if no output file
    if not args.output:
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)

    print("\n✅ Comparación completada")


if __name__ == "__main__":
    main()
