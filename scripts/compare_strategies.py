#!/usr/bin/env python3
"""
Multi-Strategy Backtest Comparison.
Runs the same backtest with each strategy enabled and compares results.
"""

import os
import re
import subprocess
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# List of all strategies to test
STRATEGIES = [
    "TrendRider",
    "MeanReverter",
    "BreakoutHunter",
    "QuickScalper",
    "SmartMoneyFollower",
    "PatternTrader",
    "AlphaEdge",
    "SynergyFlow",
    "DebugAll",  # All sensors (no strategy filter)
]

DATA_FILE = "data/raw/LTCUSDT_1m__30d.csv"
SYMBOL = "LTC/USDT:USDT"


def enable_strategy(strategy_name: str):
    """Enable only the specified strategy by modifying the file."""
    import re

    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "strategies.py")

    with open(config_file, "r") as f:
        content = f.read()

    # First, disable all strategies
    # Pattern: "StrategyName": {\n        "enabled": True/False
    def replace_enabled(match):
        name = match.group(1)
        if name == strategy_name:
            return f'"{name}": {{\n        "enabled": True'
        else:
            return f'"{name}": {{\n        "enabled": False'

    # Match strategy definitions with enabled field
    pattern = r'"([A-Za-z]+)":\s*\{\s*\n\s*"enabled":\s*(True|False)'

    new_content = re.sub(pattern, replace_enabled, content)

    with open(config_file, "w") as f:
        f.write(new_content)


def run_backtest() -> dict:
    """Run backtest and parse results."""
    cmd = [
        sys.executable,
        "backtest.py",
        "--data",
        DATA_FILE,
        "--symbol",
        SYMBOL,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    output = result.stdout + result.stderr

    # Parse results
    wins = losses = 0
    pnl = 0.0

    # Extract Wins / Losses
    match = re.search(r"Wins / Losses\s*:\s*(\d+)\s*/\s*(\d+)", output)
    if match:
        wins, losses = int(match.group(1)), int(match.group(2))

    # Extract PnL
    match = re.search(r"PnL Total\s*:\s*([+-]?\d+\.?\d*)", output)
    if match:
        pnl = float(match.group(1))

    # Extract WinRate
    winrate = 0.0
    match = re.search(r"WinRate.*?:\s*(\d+\.?\d*)%", output)
    if match:
        winrate = float(match.group(1))

    trades = wins + losses
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pnl": pnl,
    }


def main():
    results = {}

    print("=" * 60)
    print("📊 MULTI-STRATEGY BACKTEST COMPARISON")
    print(f"   Data: {DATA_FILE}")
    print(f"   Symbol: {SYMBOL}")
    print("=" * 60)
    print()

    for strategy in STRATEGIES:
        print(f"🔄 Testing {strategy}...", end=" ", flush=True)

        try:
            # Enable strategy
            enable_strategy(strategy)

            # Run backtest
            result = run_backtest()
            results[strategy] = result

            print(f"✅ {result['trades']} trades, WR: {result['winrate']:.1f}%, PnL: {result['pnl']:+.2f}")
        except Exception as e:
            print(f"❌ Error: {e}")
            results[strategy] = {"trades": 0, "wins": 0, "losses": 0, "winrate": 0, "pnl": 0, "error": str(e)}

    # Print comparison table
    print()
    print("=" * 60)
    print("📈 RESULTS COMPARISON")
    print("=" * 60)
    print(f"{'Strategy':<20} {'Trades':>7} {'W/L':>8} {'WinRate':>8} {'PnL':>10}")
    print("-" * 60)

    # Sort by PnL descending
    sorted_results = sorted(results.items(), key=lambda x: x[1].get("pnl", 0), reverse=True)

    for strategy, data in sorted_results:
        trades = data.get("trades", 0)
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        winrate = data.get("winrate", 0)
        pnl = data.get("pnl", 0)

        print(f"{strategy:<20} {trades:>7} {wins:>3}/{losses:<4} {winrate:>7.1f}% {pnl:>+9.2f}")

    print("=" * 60)

    # Find best
    best = sorted_results[0]
    print(f"\n🏆 BEST STRATEGY: {best[0]} (PnL: {best[1]['pnl']:+.2f})")


if __name__ == "__main__":
    main()
