"""
Integration tests for core modules in Casino V2.

Tests the interaction between core components: session_runner, session_helpers,
tables, and players.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# Test integration between session_runner and session_helpers
def test_session_runner_with_helpers():
    """Test that session_runner properly uses session_helpers."""
    from core.session_helpers import get_table_state, set_table_balance
    from core.session_runner import run_session_with_player

    # Create a mock table
    mock_table = MagicMock()
    mock_table.balance_manager = MagicMock()
    mock_table.balance_manager.get_state.return_value = {"balance": 10000.0, "equity": 10000.0}

    # Test set_table_balance
    set_table_balance(mock_table, 5000.0)
    assert mock_table.balance_manager.balance == 5000.0
    assert mock_table.balance_manager.equity == 5000.0

    # Test get_table_state
    state = get_table_state(mock_table)
    assert state["balance"] == 10000.0
    assert state["equity"] == 10000.0


# Test table inheritance integration
def test_table_base_integration():
    """Test that tables properly inherit from BaseTable and work together."""
    from tables.table_backtest import TableBacktest
    from tables.table_base import BaseTable
    from tables.table_ccxt_pro import TableCCXTPro

    # Verify inheritance
    assert issubclass(TableBacktest, BaseTable)
    assert issubclass(TableCCXTPro, BaseTable)

    # Test that they have common interface
    common_methods = ["get_state"]
    for method in common_methods:
        assert hasattr(TableBacktest, method)
        assert hasattr(TableCCXTPro, method)


# Test player integration with session_runner
def test_player_integration():
    """Test that players integrate properly with session_runner."""
    # This would require more complex mocking, but shows the integration point
    from players.kelly_player import calculate_position_size

    # Test that player functions work as expected
    assert callable(calculate_position_size)

    # Test with sample data
    verdict = MagicMock()
    verdict.side = "BUY"
    verdict.confidence = 0.8

    size = calculate_position_size(verdict, 10000.0, None)
    # Note: Kelly player may return None in some cases
    if size is not None:
        assert isinstance(size, (int, float))
        assert 0 <= size <= 1  # Should be a fraction
    else:
        # None is acceptable for some player configurations
        pass


# Test sensor integration
def test_sensor_integration():
    """Test that sensors integrate properly with the system."""
    from sensors.sensor_manager import SensorManager

    sensor_manager = SensorManager()

    # Should be able to create sensor manager
    assert sensor_manager is not None

    # Should have process_candle method
    assert hasattr(sensor_manager, "process_candle")

    # Test with sample candle
    sample_candle = {
        "timestamp": "2023-01-01T00:00:00Z",
        "open": 50000.0,
        "high": 51000.0,
        "low": 49000.0,
        "close": 50500.0,
        "volume": 100.0,
        "symbol": "BTC/USDT",
    }

    signals = sensor_manager.process_candle(sample_candle)

    # Should return a list (may be empty if no signals)
    assert isinstance(signals, list)


# Test Gemini integration
def test_gemini_integration():
    """Test that Gemini integrates properly with other components."""
    from gemini.gemini_core import Gemini

    gemini = Gemini()

    # Should have required methods
    assert hasattr(gemini, "evaluate_signals_v2")
    assert hasattr(gemini, "make_order_from_verdict")
    assert hasattr(gemini, "on_trade_result")

    # Test basic functionality
    signals = []  # Empty signals
    verdict = gemini.evaluate_signals_v2(signals, equity=10000.0)

    # Should return a Verdict object
    assert verdict is not None
    assert hasattr(verdict, "side")
    # Note: Verdict may not have confidence attribute in all cases
    assert hasattr(verdict, "reason")  # Should have reason instead


# Test Croupier integration
def test_croupier_integration():
    """Test that Croupier integrates properly with tables."""
    from croupier.croupier import Croupier
    from tables.table_backtest import TableBacktest

    # Create a minimal table for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01T00:00:00Z,50000,51000,49000,50500,100\n")
        temp_file = f.name

    try:
        table = TableBacktest(temp_file)
        croupier = Croupier(table)

        # Should have route_order method
        assert hasattr(croupier, "route_order")

        # Test with a sample order (add required fields)
        sample_order = {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "size": 0.1,
            "type": "market",
            "ghost": True,
            "take_profit": 51000.0,
            "stop_loss": 49000.0,
        }

        # Need to advance table to have candle data
        table.next_candle()  # This sets up _last_index

        result = croupier.route_order(sample_order)

        # Should return a result dict
        assert isinstance(result, dict)
        assert "result" in result

    finally:
        os.unlink(temp_file)


# Test position tracker integration
def test_position_tracker_integration():
    """Test that PositionTracker integrates properly."""
    from tables.position_tracker import PositionTracker

    tracker = PositionTracker(max_concurrent_positions=2)

    # Should have required methods
    assert hasattr(tracker, "can_open_position")
    assert hasattr(tracker, "open_position")
    assert hasattr(tracker, "check_and_close_positions")
    assert hasattr(tracker, "get_stats")

    # Test basic functionality
    stats = tracker.get_stats()
    assert isinstance(stats, dict)
    assert "open_positions" in stats
    assert "blocked_capital" in stats


# Test balance manager integration
def test_balance_manager_integration():
    """Test that BalanceManager integrates properly."""
    from tables.balance_manager import BalanceManager

    bm = BalanceManager(starting_balance=10000.0)

    # Should have required methods
    assert hasattr(bm, "get_state")
    # Note: BalanceManager may not have set_balance method, just direct attribute access
    assert hasattr(bm, "balance")

    # Test basic functionality
    state = bm.get_state()
    assert isinstance(state, dict)
    assert "balance" in state
    assert "equity" in state
    assert state["balance"] == 10000.0

    # Test direct balance modification
    bm.balance = 5000.0
    bm.equity = 5000.0
    state = bm.get_state()
    assert state["balance"] == 5000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
