"""
Paroli Player Configuration for Casino-V3.
Progressive betting strategy: 1-1-3
"""

# Paroli Progression
BASE_DIVISOR = 100  # Unit = equity / 100 (1% of equity)
PROGRESSION = (1, 1, 3)  # Multipliers for each step
MAX_POSITION_SIZE = 0.02  # Maximum 2% of equity per trade
LEVERAGE = 10  # Futures leverage (max 50x per trading config)

# Signal Aggregation
VOTING_THRESHOLD = 1.5  # Majority must be 1.5x minority to trigger
SIGNAL_TIMEOUT_MS = 100  # Wait 100ms for all sensors to fire
CONFLICT_DELTA_THRESHOLD = 0.01  # Min score difference to resolve conflict (reduced from 0.02)

# Risk Management
RESET_ON_LOSS = True  # Reset progression on any loss
RESET_AFTER_CYCLE = True  # Reset after completing full 1-1-3 cycle
