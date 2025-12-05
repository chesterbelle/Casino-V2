#!/usr/bin/env python3
"""
Multi-Strategy Backtest Runner (Inline Version)
Modifies strategies.py, runs backtest, collects results.
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
DATA_FILE = "data/raw/LTCUSDT_1m__30d.csv"
SYMBOL = "LTC/USDT:USDT"
STRATEGIES_FILE = Path("config/strategies.py")

STRATEGIES = [
    "TrendRider",
    "MeanReverter",
    "BreakoutHunter",
    "QuickScalper",
    "SmartMoneyFollower",
    "PatternTrader",
    "AlphaEdge",
    "SynergyFlow",
]


def set_active_strategy(strategy_name: str):
    """Modify strategies.py to enable only the specified strategy."""
    content = STRATEGIES_FILE.read_text()

    # Pattern to find strategy definitions with enabled field
    for strat in STRATEGIES + ["DebugAll"]:
        # Match the pattern "StrategyName": { ... "enabled": True/False
        pattern = rf'("{strat}":\s*\{{\s*"enabled":\s*)(True|False)'
        if strat == strategy_name:
            replacement = r"\1True"
        else:
            replacement = r"\1False"
        content = re.sub(pattern, replacement, content)

    STRATEGIES_FILE.write_text(content)


def parse_backtest_output(output: str) -> dict:
    """Parse backtest output to extract metrics."""
    result = {
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "final_balance": 10000.0,
        "fees": 0.0,
    }

    for line in output.split("\n"):
        if "Wins / Losses" in line:
            match = re.search(r"(\d+)\s*/\s*(\d+)", line)
            if match:
                result["wins"] = int(match.group(1))
                result["losses"] = int(match.group(2))
        elif "WinRate" in line:
            match = re.search(r"([\d.]+)%", line)
            if match:
                result["win_rate"] = float(match.group(1))
        elif "PnL Total" in line:
            match = re.search(r"([+-]?[\d.]+)\s*\(([+-]?[\d.]+)%\)", line)
            if match:
                result["pnl"] = float(match.group(1))
                result["pnl_pct"] = float(match.group(2))
        elif "Balance final" in line:
            match = re.search(r"([\d.]+)", line)
            if match:
                result["final_balance"] = float(match.group(1))
        elif "Comisiones" in line:
            match = re.search(r"([\d.]+)", line)
            if match:
                result["fees"] = float(match.group(1))

    return result


def run_backtest() -> str:
    """Run backtest.py and return output."""
    cmd = [
        sys.executable,
        "backtest.py",
        f"--data={DATA_FILE}",
        f"--symbol={SYMBOL}",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(Path(__file__).parent.parent)  # 5 min timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print("\n" + "=" * 80)
    print("🎰 CASINO-V3 MULTI-STRATEGY BACKTEST COMPARISON")
    print("=" * 80)
    print(f"📁 Dataset: {DATA_FILE}")
    print(f"📊 Symbol: {SYMBOL}")
    print(f"🎯 Strategies: {len(STRATEGIES)}")
    print("=" * 80 + "\n")

    results = []

    for i, strategy in enumerate(STRATEGIES, 1):
        print(f"[{i}/{len(STRATEGIES)}] Testing {strategy}...", end=" ", flush=True)

        # Enable only this strategy
        set_active_strategy(strategy)

        # Run backtest
        output = run_backtest()

        if "TIMEOUT" in output:
            print("⏱️ TIMEOUT")
            results.append({"strategy": strategy, "error": "timeout"})
            continue
        elif "ERROR" in output:
            print(f"❌ {output[:50]}")
            results.append({"strategy": strategy, "error": output})
            continue

        # Parse results
        parsed = parse_backtest_output(output)
        parsed["strategy"] = strategy
        total_trades = parsed["wins"] + parsed["losses"]
        parsed["trades"] = total_trades

        results.append(parsed)

        print(f"✅ {total_trades} trades | WR: {parsed['win_rate']:.1f}% | PnL: {parsed['pnl_pct']:+.2f}%")

    # Print comparison table
    print("\n\n" + "=" * 90)
    print("📊 RESULTS COMPARISON (sorted by PnL%)")
    print("=" * 90)

    # Header
    print(
        f"{'Strategy':<20} {'Trades':>7} {'Wins':>6} {'Losses':>7} {'WR%':>7} " f"{'PnL':>12} {'PnL%':>9} {'Final':>12}"
    )
    print("-" * 90)

    # Sort by PnL% descending
    valid = [r for r in results if "error" not in r]
    sorted_results = sorted(valid, key=lambda x: x["pnl_pct"], reverse=True)

    for r in sorted_results:
        print(
            f"{r['strategy']:<20} {r['trades']:>7} {r['wins']:>6} {r['losses']:>7} "
            f"{r['win_rate']:>6.1f}% {r['pnl']:>+12.2f} {r['pnl_pct']:>+8.2f}% "
            f"{r['final_balance']:>12.2f}"
        )

    print("=" * 90)

    # Winner
    if sorted_results:
        best = sorted_results[0]
        worst = sorted_results[-1]

        print(f"\n🏆 BEST:  {best['strategy']} → PnL: {best['pnl']:+.2f} ({best['pnl_pct']:+.2f}%)")
        print(f"💀 WORST: {worst['strategy']} → PnL: {worst['pnl']:+.2f} ({worst['pnl_pct']:+.2f}%)")

    # Restore AlphaEdge as active
    set_active_strategy("AlphaEdge")
    print("\n✅ Restored AlphaEdge as active strategy")

    # Save results
    import json

    output_file = f"state/backtest_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path("state").mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({"results": results, "dataset": DATA_FILE, "symbol": SYMBOL}, f, indent=2)
    print(f"💾 Results saved to: {output_file}")


if __name__ == "__main__":
    main()
