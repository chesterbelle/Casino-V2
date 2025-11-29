import json
import sys
from pathlib import Path

import pandas as pd


def analyze_gemini_memory(backtest_log_path):
    # 1. Load Backtest Log (for PnL per trade)
    with open(backtest_log_path, "r") as f:
        backtest_data = json.load(f)

    trades = backtest_data.get("closed_trades", [])
    if not trades:
        print("No closed trades found in backtest log.")
        return

    # Create DataFrame from trades
    df_trades = pd.DataFrame(trades)

    # Check if we have the link (gemini_trade_id)
    if "gemini_trade_id" not in df_trades.columns:
        print("❌ 'gemini_trade_id' not found in backtest trades.")
        print("   You need to ensure trade_id is passed to VirtualExchange via params.")
        return

    # 2. Load Gemini Memory Log (for attribution)
    memory_csv_path = "/home/chesterbelle/Casino-V2/gemini/data/memory_log.csv"
    if not Path(memory_csv_path).exists():
        print(f"Gemini memory log not found at {memory_csv_path}")
        return

    df_memory = pd.read_csv(memory_csv_path)

    # 3. Merge
    # df_memory has: timestamp, trade_id, strategy, bucket, ...
    # df_trades has: id (tr_X), gemini_trade_id, pnl, ...

    # Join on trade_id
    merged = pd.merge(
        df_memory,
        df_trades[["gemini_trade_id", "pnl", "side"]],
        left_on="trade_id",
        right_on="gemini_trade_id",
        how="inner",
    )

    if merged.empty:
        print("No matching trades found between Backtest and Gemini Memory.")
        return

    # 4. Analyze Performance by Sensor (Strategy)
    print("\n=== PERFORMANCE BY SENSOR (ATTRIBUTED) ===")
    stats = (
        merged.groupby("strategy")
        .agg(trades=("trade_id", "nunique"), pnl=("pnl", "sum"), avg_pnl=("pnl", "mean"))
        .sort_values("pnl", ascending=False)
    )

    print(stats)

    # Calculate Win Rate per sensor (based on the trade result)
    # Note: A trade is a WIN if pnl > 0
    merged["is_win"] = merged["pnl"] > 0

    wr_stats = merged.groupby("strategy").agg(wins=("is_win", "sum"), total=("is_win", "count"))
    wr_stats["win_rate"] = (wr_stats["wins"] / wr_stats["total"]) * 100

    print("\n=== WIN RATE BY SENSOR ===")
    print(wr_stats.sort_values("win_rate", ascending=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_gemini_memory.py <backtest_log.json>")
        sys.exit(1)
    analyze_gemini_memory(sys.argv[1])
