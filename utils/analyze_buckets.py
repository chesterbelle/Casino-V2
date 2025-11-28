#!/usr/bin/env python3
"""
Analyze Gemini Buckets
----------------------
Reads gemini/data/memory_state.json and displays a formatted table of bucket statistics.
"""

import json
import os
import sys
from typing import Dict, List

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None


def print_table(data, headers):
    if tabulate:
        print(tabulate(data, headers=headers, tablefmt="grid"))
    else:
        # Simple fallback
        print(" | ".join(headers))
        print("-" * 80)
        for row in data:
            print(" | ".join(str(x) for x in row))


STATE_PATH = "gemini/data/memory_state.json"


def load_state(path: str) -> Dict:
    if not os.path.exists(path):
        print(f"❌ State file not found: {path}")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading state: {e}")
        return {}


def analyze_buckets():
    state = load_state(STATE_PATH)
    if not state:
        return

    strategies = state.get("strategies", {})
    if not strategies:
        print("⚠️ No strategies found in memory state.")
        return

    table_data = []

    # Headers
    headers = ["Strategy / Bucket", "Winrate", "Wins", "Losses", "Total", "Status"]

    for key, stats in strategies.items():
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total = wins + losses
        winrate = stats.get("winrate")

        wr_display = f"{winrate:.2%}" if winrate is not None else "N/A"

        # Simple status check (heuristic)
        status = "Unknown"
        if total < 20:
            status = "Building Support"
        elif winrate is not None and winrate > 0.52:  # Rough BEP check
            status = "✅ Positive"
        else:
            status = "❌ Negative"

        table_data.append([key, wr_display, wins, losses, total, status])

    # Sort by Total desc
    table_data.sort(key=lambda x: x[4], reverse=True)

    print(f"\n📊 Gemini Bucket Analysis ({len(table_data)} entries)\n")
    print_table(table_data, headers)
    print(f"\nTotal Observations: {sum(x[4] for x in table_data)}")


def main():
    analyze_buckets()
    return 0


if __name__ == "__main__":
    main()
