"""
Players module - Bet sizing strategies for Casino V3.

Available players:
- FixedPlayer: Fixed percentage per trade

Author: Casino V3 Team
"""

from .fixed import FixedPlayer

__all__ = ["FixedPlayer"]
