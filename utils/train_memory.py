#!/usr/bin/env python3
"""
Entry point for launching the train-memory command directly from utils.

Usage:
    python3 utils/train_memory.py --pattern "*training.csv"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional


def _ensure_project_root() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Delegate to the consolidated CLI with the train-memory command."""
    _ensure_project_root()
    from utils.cli import main as cli_main  # pylint: disable=import-outside-toplevel

    args = list(argv) if argv is not None else sys.argv[1:]
    return cli_main(["train-memory", *args])


if __name__ == "__main__":
    raise SystemExit(main())
