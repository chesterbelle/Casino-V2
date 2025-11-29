"""
Players - Bet Sizing Strategies

This module contains different bet sizing strategies (players) that can be used
interchangeably in the trading system.

Available players:
- ParoliV3: Progressive betting (1-1-3 progression)
- (Future) KellyPlayer: Kelly criterion based sizing
- (Future) FixedPlayer: Fixed percentage betting
"""

from .paroli import ParoliV3

__all__ = ["ParoliV3"]
