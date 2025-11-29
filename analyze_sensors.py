import json
from collections import defaultdict
from pathlib import Path


def analyze_sensors():
    logs_dir = Path("/home/chesterbelle/Casino-V2/logs")
    json_files = sorted(logs_dir.glob("backtest_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not json_files:
        print("❌ No log files found")
        return

    latest_json = json_files[0]
    print(f"Analyzing: {latest_json.name}\n")

    with open(latest_json, "r") as f:
        data = json.load(f)

    trades = data.get("closed_trades", [])

    sensor_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0})

    for trade in trades:
        pnl = trade.get("pnl", 0)
        contributors = trade.get("contributors", [])

        # If no contributors listed (shouldn't happen in new logs), skip or label unknown
        if not contributors:
            contributors = ["Unknown"]

        for sensor in contributors:
            stats = sensor_stats[sensor]
            stats["trades"] += 1
            stats["pnl"] += pnl
            if pnl > 0:
                stats["wins"] += 1
            else:
                stats["losses"] += 1

    print(f"{'SENSOR':<25} | {'TRADES':<6} | {'WR %':<6} | {'PnL ($)':<8} | {'AVG ($)':<6}")
    print("-" * 65)

    sorted_sensors = sorted(sensor_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)

    for sensor, stats in sorted_sensors:
        trades = stats["trades"]
        wr = (stats["wins"] / trades * 100) if trades > 0 else 0
        pnl = stats["pnl"]
        avg = pnl / trades if trades > 0 else 0

        print(f"{sensor:<25} | {trades:<6} | {wr:6.2f} | {pnl:8.2f} | {avg:6.2f}")


if __name__ == "__main__":
    analyze_sensors()
