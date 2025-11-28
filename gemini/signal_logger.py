"""Signal Logger for Gemini."""

from __future__ import annotations

import csv
import os
from typing import Any, Dict

from config import system


class SignalLogger:
    """
    Logs detailed signal features for analysis.
    Captures the state of sensors (ATR, BBW, RSI, etc.) at the moment of decision.
    """

    HEADERS = [
        "timestamp",
        "trade_id",
        "symbol",
        "timeframe",
        "side",
        "price_entry",  # Close price at signal time
        "atr",
        "bbw",
        "rsi2",
        "touch_dn",
        "touch_up",
        "cond_bbw",
        "range_score",
        "bucket_id",
        "contributors",
    ]

    def __init__(self, path: str | None = None) -> None:
        self.path = path or getattr(system, "SIGNALS_LOG_PATH", "gemini/data/casino_signals_log.csv")
        self._ensure_file()

    def _ensure_file(self) -> None:
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.path):
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()

    def log_signal(self, signal_data: Dict[str, Any]) -> None:
        """
        Log a signal event.

        Args:
            signal_data: Dict containing keys matching HEADERS.
                         Missing keys will be empty.
        """
        if not signal_data:
            return

        # Filter only known headers to avoid errors
        row = {key: signal_data.get(key, "") for key in self.HEADERS}

        try:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writerow(row)
        except Exception as e:
            # Fail silently to not disrupt trading
            print(f"❌ [SignalLogger] Error logging signal: {e}")
