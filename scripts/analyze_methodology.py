#!/usr/bin/env python3
"""
📊 Sensor Methodology Performance Analytics

Analyzes backtest results grouped by sensor methodology and function.
Helps identify which types of sensors are performing best.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.sensor_metadata import SENSOR_METADATA  # noqa: E402


def load_sensor_stats() -> dict:
    """Load sensor statistics from state file."""
    stats_file = Path("state/sensor_stats.json")
    if not stats_file.exists():
        print("❌ No sensor stats found. Run a backtest first.")
        return {}

    with open(stats_file, "r") as f:
        return json.load(f)


def analyze_by_methodology(stats: dict) -> dict:
    """Group sensor performance by methodology."""
    methodology_stats = {}

    for sensor_name, sensor_data in stats.items():
        if sensor_name not in SENSOR_METADATA:
            continue

        methodology = SENSOR_METADATA[sensor_name]["methodology"]

        if methodology not in methodology_stats:
            methodology_stats[methodology] = {
                "sensors": [],
                "total_trades": 0,
                "total_wins": 0,
                "total_pnl": 0.0,
            }

        methodology_stats[methodology]["sensors"].append(sensor_name)
        methodology_stats[methodology]["total_trades"] += sensor_data.get("total_trades", 0)
        methodology_stats[methodology]["total_wins"] += sensor_data.get("total_wins", 0)
        methodology_stats[methodology]["total_pnl"] += sensor_data.get("total_profit", 0) - sensor_data.get(
            "total_loss", 0
        )

    # Calculate derived metrics
    for method, data in methodology_stats.items():
        if data["total_trades"] > 0:
            data["win_rate"] = data["total_wins"] / data["total_trades"]
            data["avg_pnl_per_trade"] = data["total_pnl"] / data["total_trades"]
        else:
            data["win_rate"] = 0
            data["avg_pnl_per_trade"] = 0

    return methodology_stats


def analyze_by_function(stats: dict) -> dict:
    """Group sensor performance by function."""
    function_stats = {}

    for sensor_name, sensor_data in stats.items():
        if sensor_name not in SENSOR_METADATA:
            continue

        function = SENSOR_METADATA[sensor_name]["function"]

        if function not in function_stats:
            function_stats[function] = {
                "sensors": [],
                "total_trades": 0,
                "total_wins": 0,
                "total_pnl": 0.0,
            }

        function_stats[function]["sensors"].append(sensor_name)
        function_stats[function]["total_trades"] += sensor_data.get("total_trades", 0)
        function_stats[function]["total_wins"] += sensor_data.get("total_wins", 0)
        function_stats[function]["total_pnl"] += sensor_data.get("total_profit", 0) - sensor_data.get("total_loss", 0)

    # Calculate derived metrics
    for func, data in function_stats.items():
        if data["total_trades"] > 0:
            data["win_rate"] = data["total_wins"] / data["total_trades"]
            data["avg_pnl_per_trade"] = data["total_pnl"] / data["total_trades"]
        else:
            data["win_rate"] = 0
            data["avg_pnl_per_trade"] = 0

    return function_stats


def print_report(stats: dict):
    """Print performance report."""
    methodology_stats = analyze_by_methodology(stats)
    function_stats = analyze_by_function(stats)

    print()
    print("=" * 60)
    print("📊 SENSOR METHODOLOGY PERFORMANCE")
    print("=" * 60)
    print(f"{'Methodology':<18} {'Trades':>8} {'WinRate':>8} {'PnL':>10} {'Sensors':>8}")
    print("-" * 60)

    sorted_methods = sorted(methodology_stats.items(), key=lambda x: x[1]["avg_pnl_per_trade"], reverse=True)

    for methodology, data in sorted_methods:
        wr = data["win_rate"] * 100
        pnl = data["total_pnl"]
        print(f"{methodology:<18} {data['total_trades']:>8} {wr:>7.1f}% {pnl:>+9.2f} {len(data['sensors']):>8}")

    print()
    print("=" * 60)
    print("🎯 SENSOR FUNCTION PERFORMANCE")
    print("=" * 60)
    print(f"{'Function':<18} {'Trades':>8} {'WinRate':>8} {'PnL':>10} {'Sensors':>8}")
    print("-" * 60)

    sorted_funcs = sorted(function_stats.items(), key=lambda x: x[1]["avg_pnl_per_trade"], reverse=True)

    for function, data in sorted_funcs:
        wr = data["win_rate"] * 100
        pnl = data["total_pnl"]
        print(f"{function:<18} {data['total_trades']:>8} {wr:>7.1f}% {pnl:>+9.2f} {len(data['sensors']):>8}")

    # Top performers
    print()
    print("=" * 60)
    print("🏆 TOP SENSORS BY EXPECTANCY")
    print("=" * 60)

    sensor_list = []
    for sensor_name, sensor_data in stats.items():
        if sensor_name not in SENSOR_METADATA:
            continue

        trades = sensor_data.get("total_trades", 0)
        if trades < 10:
            continue

        expectancy = sensor_data.get("expectancy", 0)
        methodology = SENSOR_METADATA[sensor_name]["methodology"]
        function = SENSOR_METADATA[sensor_name]["function"]

        sensor_list.append(
            {
                "name": sensor_name,
                "expectancy": expectancy,
                "trades": trades,
                "methodology": methodology,
                "function": function,
            }
        )

    sorted_sensors = sorted(sensor_list, key=lambda x: x["expectancy"], reverse=True)[:10]

    print(f"{'Sensor':<22} {'Exp':>8} {'Trades':>7} {'Methodology':<15}")
    print("-" * 60)
    for s in sorted_sensors:
        print(f"{s['name']:<22} {s['expectancy']:>+7.4f} {s['trades']:>7} {s['methodology']:<15}")

    print()
    print("💡 INSIGHTS:")
    if sorted_methods:
        best_method = sorted_methods[0]
        print(f"   Best Methodology: {best_method[0]} (Avg PnL: {best_method[1]['avg_pnl_per_trade']:.4f})")
    if sorted_funcs:
        best_func = sorted_funcs[0]
        print(f"   Best Function: {best_func[0]} (Avg PnL: {best_func[1]['avg_pnl_per_trade']:.4f})")
    print()


if __name__ == "__main__":
    stats = load_sensor_stats()
    if stats:
        print_report(stats)
