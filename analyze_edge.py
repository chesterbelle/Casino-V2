#!/usr/bin/env python3
"""
Análisis de Edge Real

Calcula el Expected Value (EV) real de la estrategia
basándose en los resultados del backtest.
"""

import json
from pathlib import Path


def analyze_edge(json_path):
    """Analiza el edge real desde los resultados del backtest."""

    with open(json_path, "r") as f:
        data = json.load(f)

    closed_trades = data.get("closed_trades", [])

    if not closed_trades:
        print("❌ No hay trades cerrados para analizar")
        return

    # Separar wins y losses
    wins = [t for t in closed_trades if t.get("pnl", 0) > 0]
    losses = [t for t in closed_trades if t.get("pnl", 0) <= 0]

    # Calcular promedios
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 0

    total_win_amount = sum(t["pnl"] for t in wins)
    total_loss_amount = abs(sum(t["pnl"] for t in losses))

    win_rate = len(wins) / len(closed_trades) if closed_trades else 0
    loss_rate = 1 - win_rate

    # Calcular fees promedio
    total_fees = sum(t.get("fee", 0) for t in closed_trades)
    avg_fee = total_fees / len(closed_trades) if closed_trades else 0

    # Expected Value por trade
    ev_before_fees = (win_rate * avg_win) - (loss_rate * avg_loss)
    ev_after_fees = ev_before_fees - avg_fee

    # Profit Factor
    profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else 0

    # Risk/Reward Ratio
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    # Breakeven Win Rate (considerando fees)
    # WR_breakeven = (AvgLoss + Fee) / (AvgWin + AvgLoss + Fee)
    if (avg_win + avg_loss + avg_fee) > 0:
        breakeven_wr = (avg_loss + avg_fee) / (avg_win + avg_loss + avg_fee)
    else:
        breakeven_wr = 0

    print("\n" + "=" * 70)
    print("💰 ANÁLISIS DE EDGE REAL")
    print("=" * 70 + "\n")

    print("📊 Estadísticas Básicas:")
    print(f"  Total trades: {len(closed_trades)}")
    print(f"  Wins: {len(wins)} ({win_rate*100:.2f}%)")
    print(f"  Losses: {len(losses)} ({loss_rate*100:.2f}%)")
    print()

    print("💵 Análisis de Ganancias/Pérdidas:")
    print(f"  Ganancia promedio: ${avg_win:.2f}")
    print(f"  Pérdida promedio: ${avg_loss:.2f}")
    print(f"  Risk/Reward Ratio: {rr_ratio:.3f}:1")
    print()

    print(f"  Total ganado: ${total_win_amount:.2f}")
    print(f"  Total perdido: ${total_loss_amount:.2f}")
    print(f"  Profit Factor: {profit_factor:.3f}")
    print()

    print("💸 Impacto de Comisiones:")
    print(f"  Comisiones totales: ${total_fees:.2f}")
    print(f"  Comisión promedio por trade: ${avg_fee:.4f}")
    print(f"  % de PnL consumido por fees: {(total_fees / total_win_amount * 100):.2f}%")
    print()

    print("🎯 Expected Value (EV):")
    print(f"  EV antes de fees: ${ev_before_fees:.4f} por trade")
    print(f"  EV después de fees: ${ev_after_fees:.4f} por trade")
    print()

    if ev_after_fees > 0:
        print(f"  ✅ EDGE POSITIVO: +${ev_after_fees:.4f} por trade")
        edge_pct = (ev_after_fees / data.get("initial_balance", 10000)) * 100
        print(f"  Edge como % del balance: {edge_pct:.4f}%")
    elif ev_after_fees < 0:
        print(f"  ❌ EDGE NEGATIVO: ${ev_after_fees:.4f} por trade")
        print("  ⚠️ La estrategia pierde dinero en promedio")
    else:
        print("  ⚖️ BREAKEVEN: EV = $0")

    print()
    print("📈 Win Rate Requerido:")
    print(f"  WR actual: {win_rate*100:.2f}%")
    print(f"  WR breakeven (con fees): {breakeven_wr*100:.2f}%")

    if win_rate > breakeven_wr:
        margin = (win_rate - breakeven_wr) * 100
        print(f"  ✅ Margen sobre breakeven: +{margin:.2f}%")
    else:
        deficit = (breakeven_wr - win_rate) * 100
        print(f"  ❌ Déficit vs breakeven: -{deficit:.2f}%")

    print()
    print("=" * 70)
    print("🎲 CONCLUSIÓN SOBRE SISTEMAS DE APUESTAS")
    print("=" * 70 + "\n")

    if ev_after_fees <= 0:
        print("❌ NO EXISTE EDGE POSITIVO")
        print()
        print("Ningún sistema de apuestas (Paroli, Martingala, Kelly, etc.)")
        print("puede hacer rentable una estrategia con EV negativo.")
        print()
        print("Los sistemas de apuestas solo optimizan CÓMO apostar cuando")
        print("ya tienes edge, pero NO CREAN edge donde no existe.")
        print()
        print("📌 Necesitas mejorar:")
        print("  1. Win Rate (actual: {:.2f}%)".format(win_rate * 100))
        print("  2. Risk/Reward Ratio (actual: {:.3f}:1)".format(rr_ratio))
        print("  3. Reducir comisiones (${:.2f} total)".format(total_fees))
    else:
        print("✅ TIENES EDGE POSITIVO")
        print()
        print("Con EV positivo, un sistema de apuestas puede:")
        print("  • Maximizar crecimiento (Kelly)")
        print("  • Capitalizar rachas (Paroli)")
        print("  • Gestionar riesgo (Fixed Fraction)")
        print()
        print("Pero el edge ya existe - el sistema solo lo optimiza.")

    print()
    print(f"{'='*70}\n")

    return {
        "ev_after_fees": ev_after_fees,
        "win_rate": win_rate,
        "breakeven_wr": breakeven_wr,
        "profit_factor": profit_factor,
        "rr_ratio": rr_ratio,
        "avg_fee": avg_fee,
    }


def main():
    logs_dir = Path("/home/chesterbelle/Casino-V2/logs")
    json_files = sorted(logs_dir.glob("backtest_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not json_files:
        print("❌ No se encontraron archivos JSON de backtest")
        return

    latest_json = json_files[0]
    print(f"Analizando: {latest_json.name}\n")

    analyze_edge(latest_json)


if __name__ == "__main__":
    main()
