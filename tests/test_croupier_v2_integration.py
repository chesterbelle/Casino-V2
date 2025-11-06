"""
Integration tests for Croupier V2.

Tests both the new portfolio-managed mode and backward-compatible pass-through mode.
"""

import logging

from core.portfolio.portfolio_manager import PortfolioManager
from croupier.croupier import Croupier

logging.basicConfig(level=logging.INFO)


class MockExchangeAdapter:
    """Mock exchange adapter for testing."""

    def __init__(self, initial_balance=5000.0):
        self.balance_manager = type("obj", (object,), {"balance": initial_balance})()
        self.positions = {}
        self.execution_count = 0

    def execute_order(self, order):
        """Simulate order execution."""
        self.execution_count += 1
        status = order.get("status", "opened")

        if status == "opened":
            return {
                "status": "opened",
                "trade_id": order.get("trade_id", f"trade_{self.execution_count}"),
                "symbol": order["symbol"],
                "side": order["side"],
                "size": order["size"],
                "entry_price": 50000.0,
                "take_profit": order["take_profit"],
                "stop_loss": order["stop_loss"],
                "fee": order["size"] * 0.001,
            }
        else:
            return {
                "status": "closed",
                "trade_id": order.get("trade_id", f"trade_{self.execution_count}"),
                "exit_price": 51000.0,
                "exit_reason": "take_profit",
                "pnl": 100.0,
                "fee": order["size"] * 0.001,
                "result": "win",
            }

    def get_open_positions(self):
        """Get open positions."""
        return list(self.positions.values())


def test_backward_compatibility_mode():
    """Test pass-through mode (no portfolio management)."""
    print("\n" + "=" * 60)
    print("TEST 1: Backward Compatibility Mode (Pass-through)")
    print("=" * 60)

    adapter = MockExchangeAdapter(initial_balance=5000.0)
    croupier = Croupier(adapter)  # Old style - no initial_balance

    # Verify pass-through mode
    assert croupier.portfolio is None, "Portfolio should be None in pass-through mode"
    assert hasattr(croupier, "table"), "Should have 'table' alias for backward compatibility"
    assert croupier.table is adapter, "Table alias should point to exchange adapter"

    # Test balance retrieval (should fall back to adapter)
    balance = croupier.get_balance()
    assert balance == 5000.0, f"Expected balance 5000.0, got {balance}"
    print(f"✅ Balance retrieved from adapter: ${balance:,.2f}")

    # Test order execution (should delegate to adapter)
    order = {
        "trade_id": "test_1",
        "symbol": "BTC/USD",
        "side": "LONG",
        "size": 1000.0,
        "take_profit": 52000.0,
        "stop_loss": 49000.0,
        "ghost": False,
    }

    result = croupier.execute_order(order)
    assert result["status"] == "opened", f"Expected status 'opened', got {result['status']}"
    assert adapter.execution_count == 1, "Adapter should have executed the order"
    print(f"✅ Order executed via adapter: {result['status']}")

    # Verify portfolio was NOT updated (pass-through mode)
    positions = croupier.get_open_positions()
    assert len(positions) == 0, "Pass-through mode should not track positions"
    print("✅ Portfolio not updated (pass-through mode)")

    print("\n✅ Backward compatibility test PASSED")


def test_portfolio_managed_mode():
    """Test new portfolio-managed mode."""
    print("\n" + "=" * 60)
    print("TEST 2: Portfolio-Managed Mode (New V2)")
    print("=" * 60)

    adapter = MockExchangeAdapter(initial_balance=5000.0)
    croupier = Croupier(adapter, initial_balance=10000.0)  # New style

    # Verify portfolio mode
    assert croupier.portfolio is not None, "Portfolio should exist in managed mode"
    assert isinstance(croupier.portfolio, PortfolioManager), "Should be PortfolioManager instance"
    print("✅ PortfolioManager initialized")

    # Test balance retrieval (should come from portfolio)
    balance = croupier.get_balance()
    assert balance == 10000.0, f"Expected balance 10000.0, got {balance}"
    print(f"✅ Balance from portfolio: ${balance:,.2f}")

    # Test order execution with portfolio tracking
    order = {
        "trade_id": "test_2",
        "symbol": "BTC/USD",
        "side": "LONG",
        "size": 1000.0,
        "take_profit": 52000.0,
        "stop_loss": 49000.0,
        "ghost": False,
    }

    result = croupier.execute_order(order)
    assert result["status"] == "opened", f"Expected status 'opened', got {result['status']}"
    print(f"✅ Order executed: {result['status']}")

    # Verify portfolio was updated
    positions = croupier.get_open_positions()
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert positions[0]["trade_id"] == "test_2", "Position should match trade_id"
    print(f"✅ Portfolio updated: {len(positions)} position(s) tracked")

    # Test balance after position opened
    balance_after = croupier.get_balance()
    expected_balance = 10000.0 - 1000.0  # Initial - position size
    assert balance_after == expected_balance, f"Expected {expected_balance}, got {balance_after}"
    print(f"✅ Balance after position: ${balance_after:,.2f}")

    # Test equity calculation
    equity = croupier.get_equity()
    print(f"✅ Equity calculated: ${equity:,.2f}")

    print("\n✅ Portfolio-managed mode test PASSED")


def test_ghost_orders():
    """Test ghost orders (should not affect balance)."""
    print("\n" + "=" * 60)
    print("TEST 3: Ghost Orders (Shadow Trading)")
    print("=" * 60)

    adapter = MockExchangeAdapter()
    croupier = Croupier(adapter, initial_balance=10000.0)

    initial_balance = croupier.get_balance()

    # Execute ghost order
    order = {
        "trade_id": "ghost_1",
        "symbol": "BTC/USD",
        "side": "LONG",
        "size": 1000.0,
        "take_profit": 52000.0,
        "stop_loss": 49000.0,
        "ghost": True,  # Ghost order
    }

    result = croupier.execute_order(order)
    assert result["status"] == "opened", f"Expected status 'opened', got {result['status']}"
    assert result["ghost"] is True, "Result should indicate ghost order"
    print(f"✅ Ghost order executed: {result['status']}")

    # Verify balance unchanged
    balance_after = croupier.get_balance()
    assert balance_after == initial_balance, f"Ghost order should not affect balance"
    print(f"✅ Balance unchanged: ${balance_after:,.2f}")

    # Verify position not tracked
    positions = croupier.get_open_positions()
    assert len(positions) == 0, "Ghost orders should not be tracked"
    print("✅ Ghost position not tracked")

    print("\n✅ Ghost orders test PASSED")


def test_insufficient_funds():
    """Test insufficient funds rejection."""
    print("\n" + "=" * 60)
    print("TEST 4: Insufficient Funds Rejection")
    print("=" * 60)

    adapter = MockExchangeAdapter()
    croupier = Croupier(adapter, initial_balance=1000.0)  # Small balance

    # Try to open position larger than balance
    order = {
        "trade_id": "test_3",
        "symbol": "BTC/USD",
        "side": "LONG",
        "size": 5000.0,  # Larger than balance
        "take_profit": 52000.0,
        "stop_loss": 49000.0,
        "ghost": False,
    }

    result = croupier.execute_order(order)
    assert result["status"] == "rejected", f"Expected status 'rejected', got {result['status']}"
    assert result["reason"] == "insufficient_funds", f"Expected reason 'insufficient_funds'"
    print(f"✅ Order rejected: {result['reason']}")

    # Verify adapter was NOT called
    assert adapter.execution_count == 0, "Adapter should not be called for rejected orders"
    print("✅ Exchange adapter not called")

    print("\n✅ Insufficient funds test PASSED")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CROUPIER V2 INTEGRATION TESTS")
    print("=" * 60)

    try:
        test_backward_compatibility_mode()
        test_portfolio_managed_mode()
        test_ghost_orders()
        test_insufficient_funds()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nCroupier V2 is ready for production with full backward compatibility.")
        print("Both pass-through mode and portfolio-managed mode are working correctly.")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise
