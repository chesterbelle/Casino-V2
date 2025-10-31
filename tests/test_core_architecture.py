"""
Test suite for Core Architecture (v1.7 Code Cleanup)

Tests the new modular architecture with core/ package and reorganized utils/.
"""

from unittest.mock import MagicMock, patch

import pytest


# Test core package imports
def test_core_package_imports():
    """Test that core package imports work correctly."""
    try:
        from core import (
            ask_initial_balance,
            print_session_summary,
            run_session_with_player,
        )

        assert callable(run_session_with_player)
        assert callable(ask_initial_balance)
        assert callable(print_session_summary)
        print("✅ Core package imports working")
    except ImportError as e:
        pytest.fail(f"Core package import failed: {e}")


# Test utils reorganization
def test_utils_reorganization():
    """Test that utils subpackages are properly organized."""
    try:
        # Test exchanges subpackage
        from utils.exchanges.binance_env_loader import validate_binance_config

        assert callable(validate_binance_config)

        # Test analysis subpackage (just check import works, not specific functions)
        import utils.analysis.analyze_memory

        assert hasattr(utils.analysis.analyze_memory, "__file__")

        # Test data subpackage (just check import works)
        import utils.data.download_training_data

        assert hasattr(utils.data.download_training_data, "__file__")

        # Test training subpackage (just check import works)
        import utils.training.full_pipeline

        assert hasattr(utils.training.full_pipeline, "__file__")

        print("✅ Utils reorganization working")
    except ImportError as e:
        pytest.fail(f"Utils reorganization failed: {e}")


# Test Table inheritance
def test_table_inheritance():
    """Test that Tables properly inherit from BaseTable."""
    from tables.table_backtest import TableBacktest
    from tables.table_base import BaseTable
    from tables.table_ccxt_pro import TableCCXTPro

    # Check inheritance
    assert issubclass(TableBacktest, BaseTable)
    assert issubclass(TableCCXTPro, BaseTable)

    # Check instances (use real file for backtest)
    import os

    real_csv = "tables/data/raw/BTCUSDT_15m__30d.csv"
    if os.path.exists(real_csv):
        backtest = TableBacktest(real_csv)
        assert isinstance(backtest, BaseTable)
    else:
        # Skip instance test if file doesn't exist
        print("⚠️ Skipping backtest instance test - CSV not found")

    # CCXT Pro instance (mocked)
    ccxt_pro = TableCCXTPro("kraken", ["BTC/USDT"])
    assert isinstance(ccxt_pro, BaseTable)

    print("✅ Table inheritance working")


# Test main.py size reduction
def test_main_py_size():
    """Test that main.py has been properly refactored."""
    with open("main.py", "r") as f:
        lines = f.readlines()
        line_count = len(lines)

    # Should be much smaller than original 644 lines
    assert line_count < 200, f"main.py is still too large: {line_count} lines"
    assert line_count > 100, f"main.py might be too small: {line_count} lines"

    print(f"✅ main.py size: {line_count} lines (refactored from 644)")


# Test core functionality
def test_core_session_runner():
    """Test that core session runner can be imported and has expected interface."""
    from core.session_runner import run_session_with_player

    # Should be callable
    assert callable(run_session_with_player)

    # Should have proper signature (basic check)
    import inspect

    sig = inspect.signature(run_session_with_player)
    params = list(sig.parameters.keys())

    expected_params = ["dataset_path", "initial_balance", "gemini", "player_module", "player_name"]
    for param in expected_params:
        assert param in params, f"Missing parameter: {param}"

    print("✅ Core session runner interface correct")


def test_session_helpers():
    """Test session helpers functionality."""
    from core.session_helpers import ask_initial_balance, log_trade, set_table_balance

    # Test ask_initial_balance with mocked input
    with patch("builtins.input", return_value="10000"):
        balance = ask_initial_balance()
        assert balance == 10000.0

    # Test set_table_balance
    mock_table = MagicMock()
    set_table_balance(mock_table, 5000.0)
    # Should not crash

    print("✅ Session helpers working")


def test_session_summary():
    """Test session summary functionality."""
    from core.session_summary import print_session_summary

    # Test with complete sample stats
    sample_stats = {
        "dataset": "BTCUSDT_15m.csv",
        "player": "kelly",
        "initial_balance": 10000.0,
        "final_balance": 10500.0,
        "candles": 1000,
        "bet_trades": 10,
        "ghost_trades": 5,
        "skip_trades": 2,
        "wins": 7,
        "losses": 3,
        "winrate": 70.0,
        "fees": 50.0,
        "funding": 10.0,
        "liquidations": 0,
    }

    # Should not crash
    print_session_summary(sample_stats)

    print("✅ Session summary working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
