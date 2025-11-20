import asyncio

import pandas as pd

from core.data_sources.backtest import BacktestDataSource

path = "tables/data/raw/BTCUSDT_5m__30d.csv"
df = pd.read_csv(path)
sdf = df.iloc[:10].copy()
# Ensure timestamp is integer milliseconds like from_csv would provide
if sdf["timestamp"].dtype == object:
    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"]).astype(int) // 10**6

source = BacktestDataSource(sdf, initial_balance=10000)


async def run():
    await source.connect()
    await source.next_candle()
    order = {
        "symbol": source.symbol,
        "side": "LONG",
        "size": 0.01,
        "take_profit": 1.02,
        "stop_loss": 0.995,
        "trade_id": "TEST1",
        "timestamp": None,
        "ghost": False,
    }
    res = await source.execute_order(order)
    print("EXECUTE_RESULT:", res)
    print("\nConnector orders:")
    for oid, o in source.connector._orders.items():
        print(oid, o.get("type"), o.get("status"), o.get("parent"), o.get("stopPrice"))
    # Now simulate a TP hit by closing the position via internal backtest close
    if source.open_positions:
        pos = source.open_positions[0]
        tp_mult = pos.get("take_profit")
        entry = pos.get("entry_price")
        tp_price = entry * tp_mult if tp_mult else None
        if tp_price:
            print("\nSimulating TP hit at", tp_price)
            source._close_position(pos, tp_price, None, "take_profit", source._get_current_timestamp())

            print("\nAfter closure, connector orders:")
            for oid, o in source.connector._orders.items():
                print(oid, o.get("type"), o.get("status"), o.get("parent"), o.get("stopPrice"))

            print("\nClosed trades:")
            for t in source.closed_trades:
                print(t.get("trade_id", t.get("entry_price")), t.get("exit_reason"), t.get("pnl"))

    await source.disconnect()


asyncio.run(run())
