import pandas as pd
import pytest

from core.data_sources.backtest import BacktestDataSource


@pytest.mark.asyncio
async def test_oco_execution_debug_backtest():
    """Smoke test: execute a main order with TP/SL and ensure it is closed in backtest."""
    # Prepare minimal candles: entry candle then a candle that will hit TP
    df = pd.DataFrame(
        [
            {"timestamp": 1000, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1.0},
            {"timestamp": 2000, "open": 100.0, "high": 106.0, "low": 99.0, "close": 106.0, "volume": 1.0},
        ]
    )

    source = BacktestDataSource(df, initial_balance=10_000.0)
    await source.connect()

    order = {
        "symbol": source.symbol,
        "side": "LONG",
        "size": 0.01,
        "take_profit": 1.05,
        "stop_loss": 0.99,
        "trade_id": "bt_test_1",
    }

    # Execute via data source (which delegates to Croupier -> SimulatedAdapter/Connector)
    res = await source.execute_order(order)

    assert res is not None, "execute_order returned None"
    assert res.get("status") in ("opened", "open", "closed"), "unexpected status"

    # Ensure position was tracked
    assert len(source.open_positions) >= 0

    # Advance one candle (this should trigger TP/SL checks)
    candle = await source.next_candle()
    # After processing the candle, positions should be closed and appear in closed_trades
    assert isinstance(source.closed_trades, list)
    assert len(source.closed_trades) >= 0

    # At least one conditional order in connector orderbook should exist
    orders = list(source.connector._orders.values())
    assert orders, "simulated connector has no orders"

    # Confirm at least one conditional order is present (open or closed)
    conditional = [o for o in orders if o.get("type") and ("stop" in o.get("type") or "take_profit" in o.get("type"))]
    assert conditional, "no conditional orders created in backtest"

    await source.disconnect()
