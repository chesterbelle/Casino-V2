# ExitManager Implementation Plan

## Overview

New component to manage dynamic exit strategies for open positions.

## Configuration (Global)

```python
# config/trading.py
EXIT_STRATEGY = "BREAKEVEN"  # FIXED | BREAKEVEN | TRAILING | PARTIAL_TP

EXIT_PARAMS = {
    "breakeven_trigger": 0.5,    # Move SL to entry at 50% of TP distance
    "trailing_step": 0.005,      # 0.5% trailing step
    "trailing_activation": 0.3,  # Start trailing at 30% of TP
    "partial_close_pct": 0.5,    # Close 50% of position
    "partial_trigger": 0.5,      # At 50% of TP distance
}
```

## Architecture

```
┌────────────────┐     ┌──────────────┐     ┌───────────────┐
│PositionTracker │────▶│ ExitManager  │────▶│ Croupier      │
│ (price events) │     │ (exit logic) │     │ (modify SL)   │
└────────────────┘     └──────────────┘     └───────────────┘
```

## File: `core/exit_manager.py`

```python
from enum import Enum

class ExitStrategy(Enum):
    FIXED = "fixed"           # No modification (current behavior)
    BREAKEVEN = "breakeven"   # Move SL to entry at trigger
    TRAILING = "trailing"     # Move SL up as price moves
    PARTIAL_TP = "partial"    # Close partial position

class ExitManager:
    def __init__(self, croupier, strategy: ExitStrategy, params: dict):
        self.croupier = croupier
        self.strategy = strategy
        self.params = params
        self.position_state = {}  # Track per-position state

    def on_price_update(self, position, current_price):
        """Called on each candle to check if exit action needed."""
        if self.strategy == ExitStrategy.BREAKEVEN:
            return self._check_breakeven(position, current_price)
        elif self.strategy == ExitStrategy.TRAILING:
            return self._check_trailing(position, current_price)
        elif self.strategy == ExitStrategy.PARTIAL_TP:
            return self._check_partial(position, current_price)
        return None

    def _check_breakeven(self, position, current_price):
        # If already at breakeven, skip
        if position.sl_level == position.entry_price:
            return None

        # Calculate progress to TP
        if position.side == "LONG":
            tp_distance = position.tp_level - position.entry_price
            current_progress = current_price - position.entry_price
        else:
            tp_distance = position.entry_price - position.tp_level
            current_progress = position.entry_price - current_price

        progress_pct = current_progress / tp_distance if tp_distance > 0 else 0

        # Trigger breakeven
        if progress_pct >= self.params["breakeven_trigger"]:
            return {"action": "MODIFY_SL", "new_sl": position.entry_price}
        return None
```

## Exit Strategy Details

### 1. BREAKEVEN
- **Trigger**: Price reaches X% of TP distance (default 50%)
- **Action**: Move SL to entry price
- **Benefit**: Eliminates loss risk on favorable trades

### 2. TRAILING (Future)
- **Activation**: Starts when price reaches X% of TP
- **Logic**: SL follows price at fixed distance or percentage
- **Benefit**: Captures larger moves, lets winners run

### 3. PARTIAL_TP (Future)
- **Trigger**: Price reaches X% of TP distance
- **Action**: Close 50% of position, keep rest running
- **Benefit**: Locks in partial profit

## Integration Points

1. **PositionTracker.check_and_close_positions()**
   - Call `exit_manager.on_price_update()` for each position

2. **Croupier.modify_sl()**
   - New method to update SL order on exchange

3. **VirtualExchange (backtest)**
   - Simulate SL modification

## Implementation Order

1. [ ] Create `core/exit_manager.py` with base structure
2. [ ] Add EXIT_STRATEGY config to `config/trading.py`
3. [ ] Implement BREAKEVEN strategy
4. [ ] Integrate with PositionTracker
5. [ ] Add `modify_sl()` to Croupier/VirtualExchange
6. [ ] Backtest and validate
7. [ ] Implement TRAILING
8. [ ] Implement PARTIAL_TP

## Backtest Validation Required First

Before implementing, validate current changes:
- [x] Voting system (min 2 sensors)
- [x] Score threshold (0.5)
- [x] Mandatory HTF alignment
- [ ] Run full backtest with new aggregator
- [ ] Compare results before/after
