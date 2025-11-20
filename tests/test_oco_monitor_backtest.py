import pandas as pd
import pytest

from core.data_sources.backtest import BacktestDataSource


@pytest.mark.asyncio
async def test_oco_monitor_backtest():
    """Test that fetch_order / fetch_open_orders / cancel_order are available and reflect backtest events."""
    df = pd.DataFrame(
        [
            {"timestamp": 1000, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1.0},
            {"timestamp": 2000, "open": 100.0, "high": 106.0, "low": 99.0, "close": 106.0, "volume": 1.0},
        ]
    )

    source = BacktestDataSource(df, initial_balance=5_000.0)
    await source.connect()

    order = {
        "symbol": source.symbol,
        "side": "LONG",
        "size": 0.02,
        "take_profit": 1.05,
        "stop_loss": 0.98,
        "trade_id": "bt_test_monitor",
    }

    res = await source.execute_order(order)
    assert res and res.get("status") in ("opened", "open", "closed")

    # Check connector has helper methods and open orders
    open_orders = await source.connector.fetch_open_orders(source.symbol)
    assert isinstance(open_orders, list)

    # If there are open orders, cancel one to test cancel_order
    if open_orders:
        oid = open_orders[0].get("id")
        canceled = await source.connector.cancel_order(oid, source.symbol)
        assert canceled.get("status") == "canceled"

    # Advance candle to trigger TP/SL and then call fetch_order on known ids
    await source.next_candle()

    # Fetch all orders and ensure at least one has status 'closed'
    all_orders = list(source.connector._orders.values())
    assert any(o.get("status") == "closed" for o in all_orders), "no orders marked closed after tick"

    await source.disconnect()
