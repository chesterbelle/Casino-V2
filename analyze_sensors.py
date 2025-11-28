import json
import sys
from collections import defaultdict

import pandas as pd


def analyze_backtest(log_file):
    try:
        with open(log_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {log_file} not found.")
        return

    signals = data.get("signals", [])
    trades = data.get("closed_trades", [])

    print(f"Total Signals: {len(signals)} (Note: Raw signals might not be in log)")
    print(f"Total Trades: {len(trades)}")

    # Map trade ID to result
    trade_results = {}
    for trade in trades:
        trade_results[trade["trade_id"]] = {"pnl": trade["pnl"], "outcome": "WIN" if trade["pnl"] > 0 else "LOSS"}

    # Analyze sensors
    sensor_stats = defaultdict(lambda: {"signals": 0, "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})

    for signal in signals:
        # Check if signal has 'origin' or 'contributors'
        # The log format might vary, let's inspect a sample signal structure if needed.
        # Assuming signal object has 'origin' or we look at the trade's contributors
        pass

    # Since the signal log in the JSON might not directly link to the trade outcome easily without
    # matching timestamps/IDs, and the 'contributors' are in the trade object.

    for trade in trades:
        contributors = trade.get("contributors", [])
        if isinstance(contributors, str):
            contributors = [contributors]

        outcome = "WIN" if trade["pnl"] > 0 else "LOSS"
        pnl = trade["pnl"]

        for sensor in contributors:
            sensor_stats[sensor]["trades"] += 1
            if outcome == "WIN":
                sensor_stats[sensor]["wins"] += 1
            else:
                sensor_stats[sensor]["losses"] += 1
            sensor_stats[sensor]["pnl"] += pnl

    # Calculate metrics
    results = []
    for sensor, stats in sensor_stats.items():
        total_trades = stats["trades"]
        win_rate = (stats["wins"] / total_trades * 100) if total_trades > 0 else 0
        results.append(
            {
                "Sensor": sensor,
                "Trades": total_trades,
                "Win Rate": win_rate,
                "PnL": stats["pnl"],
                "Wins": stats["wins"],
                "Losses": stats["losses"],
            }
        )

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="Win Rate", ascending=False)
        print(df.to_string(index=False))
    else:
        print("No trade data found to analyze.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_sensors.py <log_file>")
    else:
        analyze_backtest(sys.argv[1])
