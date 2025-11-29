#!/usr/bin/env python3
"""
Analyze sensor performance from Gemini Memory logs.
Shows Win Rate, total trades, and contribution for each sensor.
"""

import sys
from pathlib import Path

import pandas as pd


def analyze_sensor_performance(memory_csv_path="gemini/data/memory_log.csv"):
    """Analyze individual sensor performance from Gemini Memory."""

    if not Path(memory_csv_path).exists():
        print(f"❌ Memory log not found: {memory_csv_path}")
        return

    # Load memory log
    df = pd.read_csv(memory_csv_path)

    if df.empty:
        print("❌ Memory log is empty")
        return

    print("\n" + "=" * 80)
    print("📊 SENSOR PERFORMANCE ANALYSIS (from Gemini Memory)")
    print("=" * 80 + "\n")

    # Group by strategy (sensor)
    sensor_stats = (
        df.groupby("strategy")
        .agg(total_trades=("result", "count"), wins=("result", "sum"), losses=("result", lambda x: (x == 0).sum()))
        .reset_index()
    )

    # Calculate Win Rate
    sensor_stats["win_rate"] = (sensor_stats["wins"] / sensor_stats["total_trades"] * 100).round(2)

    # Sort by Win Rate descending
    sensor_stats = sensor_stats.sort_values("win_rate", ascending=False)

    # Display results
    print(f"{'SENSOR':<30} | {'TRADES':>7} | {'WINS':>5} | {'LOSSES':>6} | {'WR %':>6}")
    print("-" * 80)

    for _, row in sensor_stats.iterrows():
        sensor = row["strategy"]
        trades = int(row["total_trades"])
        wins = int(row["wins"])
        losses = int(row["losses"])
        wr = row["win_rate"]

        # Color code based on WR
        if wr >= 70:
            marker = "🟢"
        elif wr >= 60:
            marker = "🟡"
        elif wr >= 50:
            marker = "🟠"
        else:
            marker = "🔴"

        print(f"{marker} {sensor:<28} | {trades:>7} | {wins:>5} | {losses:>6} | {wr:>6.2f}")

    print("\n" + "=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)

    # Overall stats
    total_trades = sensor_stats["total_trades"].sum()
    total_wins = sensor_stats["wins"].sum()
    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print(f"\nTotal Trades: {total_trades}")
    print(f"Total Wins: {total_wins}")
    print(f"Overall Win Rate: {overall_wr:.2f}%")

    # Top performers
    print("\n🏆 TOP 5 PERFORMERS (by Win Rate):")
    top5 = sensor_stats.head(5)
    for i, row in enumerate(top5.itertuples(), 1):
        print(f"  {i}. {row.strategy}: {row.win_rate:.2f}% ({row.wins}W / {row.losses}L)")

    # Bottom performers
    print("\n⚠️  BOTTOM 5 PERFORMERS (by Win Rate):")
    bottom5 = sensor_stats.tail(5).sort_values("win_rate")
    for i, row in enumerate(bottom5.itertuples(), 1):
        print(f"  {i}. {row.strategy}: {row.win_rate:.2f}% ({row.wins}W / {row.losses}L)")

    # High volume sensors
    print("\n📊 HIGH VOLUME SENSORS (>10 trades):")
    high_vol = sensor_stats[sensor_stats["total_trades"] > 10].sort_values("win_rate", ascending=False)
    for row in high_vol.itertuples():
        print(f"  • {row.strategy}: {row.win_rate:.2f}% ({row.total_trades} trades)")

    print("\n" + "=" * 80 + "\n")

    return sensor_stats


if __name__ == "__main__":
    memory_path = "gemini/data/memory_log.csv"
    if len(sys.argv) > 1:
        memory_path = sys.argv[1]

    analyze_sensor_performance(memory_path)
