import json
import sys

import numpy as np
import pandas as pd


def load_data(filepath):
    df = pd.read_csv(filepath)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def simulate_tp_sl(data_path, logs_path, tp_levels, sl_levels):
    """
    Simula diferentes combinaciones de TP/SL para encontrar la óptima.
    """
    print(f"📉 Loading market data from {data_path}...")
    df = load_data(data_path)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    print(f"📋 Loading signals/trades from {logs_path}...")
    with open(logs_path, "r") as f:
        results = json.load(f)

    trades = results.get("closed_trades", [])
    if not trades:
        print("❌ No trades found in logs.")
        return

    print(
        f"🔍 Simulating {len(tp_levels)} TP levels x {len(sl_levels)} SL levels = {len(tp_levels) * len(sl_levels)} combinations..."
    )
    print(f"📊 Analyzing {len(trades)} trades...\n")

    results_matrix = []

    for tp_pct in tp_levels:
        for sl_pct in sl_levels:
            wins = 0
            losses = 0
            total_pnl = 0

            for trade in trades:
                entry_time = pd.to_datetime(trade["entry_time"], unit="ms", utc=True)
                entry_price = trade["entry_price"]
                position_side = trade["position_side"]

                try:
                    idx = df.index.get_indexer([entry_time], method="nearest")[0]
                    if idx == -1:
                        continue

                    # Get future candles until TP or SL is hit (max 100 candles)
                    future_candles = df.iloc[idx : idx + 100]

                    if len(future_candles) < 2:
                        continue

                    # Simulate TP/SL execution
                    hit_tp = False
                    hit_sl = False

                    for i, (ts, candle) in enumerate(future_candles.iterrows()):
                        if i == 0:  # Skip entry candle
                            continue

                        high = candle["high"]
                        low = candle["low"]

                        if position_side == "LONG":
                            tp_price = entry_price * (1 + tp_pct)
                            sl_price = entry_price * (1 - sl_pct)

                            # Check if TP hit first
                            if high >= tp_price:
                                hit_tp = True
                                break
                            # Check if SL hit
                            if low <= sl_price:
                                hit_sl = True
                                break
                        else:  # SHORT
                            tp_price = entry_price * (1 - tp_pct)
                            sl_price = entry_price * (1 + sl_pct)

                            # Check if TP hit first
                            if low <= tp_price:
                                hit_tp = True
                                break
                            # Check if SL hit
                            if high >= sl_price:
                                hit_sl = True
                                break

                    if hit_tp:
                        wins += 1
                        total_pnl += tp_pct
                    elif hit_sl:
                        losses += 1
                        total_pnl -= sl_pct
                    # If neither hit, ignore trade (shouldn't happen with 100 candles)

                except Exception:
                    continue

            total_trades = wins + losses
            if total_trades == 0:
                continue

            win_rate = wins / total_trades

            # Calculate net PnL after fees (0.05% per trade, 2 trades per round trip)
            fee_rate = 0.001  # 0.1% total fees
            net_pnl_pct = (total_pnl - (total_trades * fee_rate)) / total_trades * 100

            results_matrix.append(
                {
                    "tp": tp_pct * 100,
                    "sl": sl_pct * 100,
                    "trades": total_trades,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate * 100,
                    "gross_pnl": total_pnl / total_trades * 100,
                    "net_pnl": net_pnl_pct,
                    "expectancy": net_pnl_pct / total_trades if total_trades > 0 else 0,
                }
            )

    # Sort by net PnL
    results_matrix.sort(key=lambda x: x["net_pnl"], reverse=True)

    print("=" * 100)
    print(
        f"{'TP%':>6} | {'SL%':>6} | {'Trades':>7} | {'WR%':>6} | {'Gross PnL%':>11} | {'Net PnL%':>10} | {'Expectancy':>10}"
    )
    print("=" * 100)

    for r in results_matrix[:15]:  # Top 15
        print(
            f"{r['tp']:>6.2f} | {r['sl']:>6.2f} | {r['trades']:>7} | {r['win_rate']:>6.2f} | {r['gross_pnl']:>11.4f} | {r['net_pnl']:>10.4f} | {r['expectancy']:>10.6f}"
        )

    print("\n💡 Best Configuration:")
    best = results_matrix[0]
    print(f"   TP: {best['tp']:.2f}% | SL: {best['sl']:.2f}%")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   Net PnL per Trade: {best['net_pnl']:.4f}%")
    print(f"   Total Trades: {best['trades']}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 utils/optimize_tp_sl.py <data_csv> <backtest_json_log>")
        sys.exit(1)

    data_file = sys.argv[1]
    log_file = sys.argv[2]

    # Test range of TP/SL values
    tp_levels = [0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010]  # 0.2% to 1.0%
    sl_levels = [0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010]

    simulate_tp_sl(data_file, log_file, tp_levels, sl_levels)
