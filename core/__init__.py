"""
Core modules for Casino V2 trading system.

This package contains the main execution logic, session management, and configuration.
"""

from . import config

# Lazy imports to avoid circular dependencies
# Import these directly when needed:
# from core.session_runner import run_session_with_player
# from core.session_helpers import ask_initial_balance, etc.

__all__ = [
    "config",
]
