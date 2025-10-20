#!/usr/bin/env python3
"""
Entry point for launching the validate-strategies command from utils.

Usage:
    python3 utils/validate_strategies.py --pattern "*_15m_*.csv"
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
    """Delegate to the consolidated CLI with the validate-strategies command."""
    _ensure_project_root()
    from utils.cli import main as cli_main  # pylint: disable=import-outside-toplevel

    args = list(argv) if argv is not None else sys.argv[1:]
    return cli_main(["validate-strategies", *args])


if __name__ == "__main__":
    raise SystemExit(main())
