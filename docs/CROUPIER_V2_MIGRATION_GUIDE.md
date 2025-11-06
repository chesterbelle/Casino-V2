# 🎯 Croupier V2 Migration Guide

## Overview

Croupier V2 transforms the Croupier from a simple order router into a comprehensive **control board** that manages portfolio state, tracks positions, and coordinates with exchange adapters.

**Key Benefits:**
- ✅ Centralized portfolio management
- ✅ Automatic balance tracking
- ✅ Position lifecycle management
- ✅ 100% backward compatible
- ✅ Zero breaking changes

---

## 🔄 Migration Modes

### Mode 1: Pass-Through (Backward Compatible)

**Use this mode if:**
- You want zero code changes
- Your existing code manages portfolio state
- You're using legacy `TableBacktest` or similar

**Example:**
```python
from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter

# Old style - no changes needed
adapter = CCXTAdapter(...)
croupier = Croupier(adapter)  # No initial_balance = pass-through mode

# Croupier delegates everything to the adapter
result = croupier.execute_order(order)
balance = croupier.get_balance()  # Falls back to adapter.balance_manager
```

**What happens:**
- `croupier.portfolio` is `None`
- All balance/position queries fall back to the exchange adapter
- Orders are passed through to the adapter without portfolio tracking
- The `table` alias is available for backward compatibility

---

### Mode 2: Portfolio-Managed (New V2)

**Use this mode if:**
- You want centralized portfolio management
- You're building new features
- You want automatic position tracking

**Example:**
```python
from croupier.croupier import Croupier
from exchanges.adapters.ccxt_adapter import CCXTAdapter

# New style - with portfolio management
adapter = CCXTAdapter(...)
croupier = Croupier(adapter, initial_balance=10000.0)  # Enable portfolio mode

# Croupier manages the portfolio
result = croupier.execute_order(order)
balance = croupier.get_balance()  # From portfolio
positions = croupier.get_open_positions()  # From portfolio
equity = croupier.get_equity()  # From portfolio
```

**What happens:**
- `croupier.portfolio` is a `PortfolioManager` instance
- Balance is tracked internally
- Positions are tracked automatically
- Fund validation happens before execution
- PnL is calculated and applied automatically

---

## 📋 API Reference

### Initialization

```python
# Pass-through mode (backward compatible)
croupier = Croupier(exchange_adapter)

# Portfolio-managed mode (new)
croupier = Croupier(exchange_adapter, initial_balance=10000.0)
```

### Query Methods

All methods work in both modes with automatic fallback:

```python
# Balance
balance = croupier.get_balance()
# Pass-through: Falls back to adapter.balance_manager.balance
# Portfolio: Returns portfolio.get_balance()

# Equity
equity = croupier.get_equity()
# Pass-through: Falls back to adapter.balance_manager.equity
# Portfolio: Returns portfolio.get_equity()

# Positions
positions = croupier.get_open_positions()
# Pass-through: Falls back to adapter.get_open_positions()
# Portfolio: Returns portfolio.get_open_positions()

# Single position
position = croupier.get_position(trade_id)
# Pass-through: Falls back to adapter (if available)
# Portfolio: Returns portfolio.get_position(trade_id)

# Full state
state = croupier.get_portfolio_state()
# Returns: {"balance": ..., "equity": ..., "open_positions": [...]}
```

### Execution Methods

```python
# Execute order
result = croupier.execute_order(order)

# Alias for backward compatibility
result = croupier.route_order(order)
```

**Order Format:**
```python
order = {
    "trade_id": "unique_id",
    "symbol": "BTC/USD",
    "side": "LONG",  # or "SHORT"
    "size": 1000.0,  # Position size in USDT
    "take_profit": 52000.0,
    "stop_loss": 49000.0,
    "ghost": False,  # True for shadow trading
}
```

**Result Format:**
```python
result = {
    "status": "opened",  # or "closed", "rejected", "error"
    "trade_id": "unique_id",
    "balance": 9000.0,
    "equity": 9000.0,
    "ghost": False,
    # ... additional fields depending on status
}
```

---

## 🎭 Ghost Orders (Shadow Trading)

Ghost orders are executed but don't affect the portfolio balance. Useful for:
- Paper trading
- Strategy testing
- Parallel evaluation

```python
order = {
    "trade_id": "ghost_1",
    "symbol": "BTC/USD",
    "side": "LONG",
    "size": 1000.0,
    "take_profit": 52000.0,
    "stop_loss": 49000.0,
    "ghost": True,  # Shadow trade
}

result = croupier.execute_order(order)
# Order is executed but balance remains unchanged
# Position is NOT tracked in portfolio
```

---

## 🔒 Fund Validation

In portfolio-managed mode, Croupier validates funds before execution:

```python
# Insufficient funds
order = {"size": 5000.0, ...}  # More than balance
result = croupier.execute_order(order)

# Result:
{
    "status": "rejected",
    "reason": "insufficient_funds",
    "balance": 1000.0,
    "equity": 1000.0,
}
```

**Note:** Pass-through mode does NOT validate funds (delegates to adapter).

---

## 🔄 Migration Examples

### Example 1: Legacy session_runner.py

**Before (works as-is):**
```python
from croupier.croupier import Croupier

table = CCXTAdapter(...)
croupier = Croupier(table)  # Pass-through mode

# Everything works unchanged
result = croupier.execute_order(order)
balance = croupier.get_balance()
```

**After (optional upgrade):**
```python
from croupier.croupier import Croupier

adapter = CCXTAdapter(...)
initial_balance = 10000.0  # Get from config or user input
croupier = Croupier(adapter, initial_balance=initial_balance)

# Now with portfolio management
result = croupier.execute_order(order)
balance = croupier.get_balance()  # From portfolio
positions = croupier.get_open_positions()  # Tracked automatically
```

### Example 2: New TradingSession

The modern `TradingSession` doesn't use Croupier directly (it uses `DataSource.execute_order()`). However, you can integrate Croupier for portfolio tracking:

```python
from core.trading.session import TradingSession
from croupier.croupier import Croupier

# Create session
session = TradingSession(data_source, player_module)

# Optional: Add Croupier for portfolio tracking
croupier = Croupier(data_source, initial_balance=10000.0)

# Use croupier for queries
balance = croupier.get_balance()
positions = croupier.get_open_positions()
```

---

## 🧪 Testing

Comprehensive integration tests are available:

```bash
cd /home/pedro/ProyectosGITHUB/Casino-V2
PYTHONPATH=$PWD python3 tests/test_croupier_v2_integration.py
```

**Tests cover:**
- ✅ Backward compatibility (pass-through mode)
- ✅ Portfolio management (V2 mode)
- ✅ Ghost orders
- ✅ Insufficient funds rejection

---

## 📊 Architecture

### Pass-Through Mode
```
Gemini → Croupier (router) → ExchangeAdapter
                                ├── BalanceManager
                                └── Positions
```

### Portfolio-Managed Mode
```
Gemini → Croupier (control board) → ExchangeAdapter
           ├── PortfolioManager
           │     ├── BalanceManager
           │     └── Positions (dict)
           └── ExchangeAdapter (delegate)
```

---

## 🚀 Best Practices

1. **Use portfolio mode for new code**: It provides better control and tracking
2. **Keep pass-through mode for legacy code**: Zero changes needed
3. **Use ghost orders for testing**: Safe way to test strategies
4. **Check portfolio state regularly**: Use `get_portfolio_state()` for debugging
5. **Handle rejected orders**: Always check `result["status"]`

---

## 🐛 Troubleshooting

### Issue: Balance not updating

**Pass-through mode:**
- Check that `adapter.balance_manager` exists
- Verify adapter is updating balance correctly

**Portfolio mode:**
- Ensure `initial_balance` was provided
- Check that orders are not ghost orders
- Verify `result["status"]` is "opened" or "closed"

### Issue: Positions not tracked

**Pass-through mode:**
- This is expected - positions are NOT tracked in pass-through mode
- Use portfolio mode if you need position tracking

**Portfolio mode:**
- Ensure orders are not ghost orders
- Check that `result["status"]` is "opened"
- Verify `trade_id` is unique

### Issue: Orders rejected

**Check:**
- Balance: `croupier.get_balance()`
- Order size: Must be <= balance
- Ghost flag: Ghost orders bypass validation

---

## 📝 Summary

Croupier V2 provides:
- **100% backward compatibility** via pass-through mode
- **Centralized portfolio management** via portfolio mode
- **Automatic position tracking** and balance updates
- **Fund validation** before execution
- **Ghost orders** for shadow trading

**No breaking changes** - existing code continues to work unchanged.

**Migration is optional** - upgrade when ready to benefit from portfolio management.

---

**Last Updated:** 2025-01-XX
**Version:** 2.0.0
