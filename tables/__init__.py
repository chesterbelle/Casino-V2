"""
DEPRECATED: Legacy tables/ module.

This module is deprecated and will be removed in v2.0.
All functionality has been moved to:
- exchanges/ (connectors, adapters, resilience)
- core/portfolio/ (balance, position management)

For backward compatibility, this module re-exports from the new locations.
Please update your imports to use the new structure.
"""

import warnings

# Re-export from new locations for backward compatibility
from core.portfolio.balance_manager import BalanceManager  # noqa: E402
from core.portfolio.position_manager import PositionManager  # noqa: E402
from core.portfolio.position_tracker import PositionTracker  # noqa: E402
from exchanges.adapters.ccxt_adapter import CCXTAdapter  # noqa: E402
from exchanges.adapters.exchange_state_sync import ExchangeStateSync  # noqa: E402

# Issue deprecation warning
warnings.warn(
    "The 'tables' module is deprecated and will be removed in v2.0. "
    "Please use 'exchanges' and 'core.portfolio' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BalanceManager",
    "PositionManager",
    "PositionTracker",
    "CCXTAdapter",
    "ExchangeStateSync",
]
