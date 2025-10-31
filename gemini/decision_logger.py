from __future__ import annotations

import csv
import os
from typing import Any, Dict, Iterable

try:
    import config
except ImportError:
    # Fallback for when config is in core/
    import os
    import sys

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        # Last resort: import from core
        from core import config


class DecisionLogger:
    HEADERS = [
        "timestamp",
        "trade_id",
        "market",
        "symbol",
        "timeframe",
        "side",
        "action",
        "reason",
        "size",
        "equity",
        "contributors",
        "strategy",
        "bucket",
        "support",
        "p_hat",
        "credibility",
        "p_conservative",
        "kelly",
        "approved",
        "participant_reason",
        "p_star",
        "r_net",
        "l_net",
    ]

    RESULT_HEADERS = [
        "timestamp",
        "trade_id",
        "market",
        "symbol",
        "timeframe",
        "side",
        "action",
        "result",
        "exit_reason",
        "bars_held",
        "entry_price",
        "trigger_price",
        "pnl",
        "pnl_pct",
        "fee",
        "balance",
        "ghost",
    ]

    def __init__(self, path: str | None = None) -> None:
        self.path = path or getattr(config, "DECISIONS_LOG_PATH", "gemini/data/gemini_decisions.csv")
        self.result_path = getattr(config, "TRADE_RESULTS_LOG_PATH", "gemini/data/gemini_trade_results.csv")
        self._ensure_file()
        self._ensure_result_file()

    def _ensure_file(self) -> None:
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.path):
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()

    def log(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            for row in rows:
                writer.writerow(row)

    def _ensure_result_file(self) -> None:
        directory = os.path.dirname(self.result_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.result_path):
            with open(self.result_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.RESULT_HEADERS)
                writer.writeheader()

    def log_result(self, result: Dict[str, Any]) -> None:
        if not result:
            return
        row = {key: result.get(key) for key in self.RESULT_HEADERS}
        with open(self.result_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.RESULT_HEADERS)
            writer.writerow(row)
