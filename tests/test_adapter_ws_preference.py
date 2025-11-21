import pytest

from exchanges.adapters.ccxt_adapter import CCXTAdapter
from exchanges.connectors.binance.binance_connector import BinanceConnector


@pytest.mark.asyncio
async def test_ws_preference_fallback(monkeypatch):
    """
    Test that CCXTAdapter prefers WS methods and falls back to REST if WS not available.
    """

    class DummyConnector(BinanceConnector):
        def __init__(self):
            self.enable_websocket = True
            self.ws_exchange = object()  # Simulate WS available with a non-bool object
            self.exchange = object()  # Dummy non-None exchange property

        async def watch_balance(self):
            print("USING WS BALANCE")
            return {"total": {"USDT": 1234.56}}

        async def fetch_balance(self):
            print("USING REST BALANCE")
            return {"total": {"USDT": 999.99}}

        async def watch_positions(self, *args, **kwargs):
            print(f"USING WS POSITIONS | args={args} kwargs={kwargs}")
            # Simulate different return if called with symbol as string
            if args and args[0] == "ETH/USDT":
                return [{"symbol": "ETH/USDT", "contracts": 1}]
            return [{"symbol": "ETH/USDT", "contracts": 42}]

        async def fetch_positions(self, symbols=None):
            print("USING REST POSITIONS")
            return [{"symbol": "ETH/USDT", "contracts": 0}]

        async def watch_order_book(self, symbol, limit=20):
            print("USING WS ORDER BOOK")
            return {"bids": [[1, 2]], "asks": [[3, 4]]}

        async def fetch_order_book(self, symbol, limit=20):
            print("USING REST ORDER BOOK")
            return {"bids": [[0, 0]], "asks": [[0, 0]]}

    connector = DummyConnector()
    adapter = CCXTAdapter(connector=connector, symbol="ETH/USDT", prefer_ws=True)

    # Debug: print WS availability attributes
    print(
        f"TEST prefer_ws={adapter.prefer_ws} has_watch_positions={hasattr(connector, 'watch_positions')} enable_websocket={getattr(connector, 'enable_websocket', False)} ws_exchange={getattr(connector, 'ws_exchange', None)}"
    )
    print(f"TEST connector.watch_positions={connector.watch_positions}")

    # Should use WS
    balance = await adapter.fetch_balance()
    assert balance["total"]["USDT"] == 1234.56
    positions = await adapter.fetch_positions(["ETH/USDT"])
    assert positions[0]["contracts"] == 1
    order_book = await adapter.fetch_order_book("ETH/USDT")
    assert order_book["bids"][0][0] == 1

    # Simulate WS not implemented
    connector.ws_exchange = False

    async def not_implemented(*args, **kwargs):
        raise NotImplementedError()

    connector.watch_balance = not_implemented
    connector.watch_positions = not_implemented
    connector.watch_order_book = not_implemented

    # Should fallback to REST
    balance = await adapter.fetch_balance()
    assert balance["total"]["USDT"] == 999.99
    positions = await adapter.fetch_positions(["ETH/USDT"])
    assert positions[0]["contracts"] == 0
    order_book = await adapter.fetch_order_book("ETH/USDT")
    assert order_book["bids"][0][0] == 0
