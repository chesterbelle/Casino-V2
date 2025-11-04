import pytest

import croupier.broker_interface as broker_module
from core import config as core_config


@pytest.fixture(autouse=True)
def reset_mode(monkeypatch):
    original_mode = getattr(core_config, "MODE", "testing")
    original_exchange = getattr(core_config, "EXCHANGE", "KRAKEN")

    yield

    monkeypatch.setattr(core_config, "MODE", original_mode, raising=False)
    monkeypatch.setattr(core_config, "EXCHANGE", original_exchange, raising=False)


def test_broker_testing_mode_uses_table(monkeypatch):
    monkeypatch.setattr(core_config, "MODE", "testing", raising=False)
    monkeypatch.setattr(core_config, "EXCHANGE", "KRAKEN", raising=False)

    class DummyConnector:
        def __init__(self, mode="testing", **_):
            self.mode = mode

    class DummyTable:
        def __init__(self, *, connector, symbol, timeframe):
            self.connector = connector
            self.symbol = symbol
            self.timeframe = timeframe

    monkeypatch.setattr("tables.connectors.KrakenConnector", DummyConnector)
    monkeypatch.setattr(broker_module, "CCXTAdapter", DummyTable)

    broker = broker_module.BrokerInterface(symbol="BTC/USD", interval="1m")

    assert isinstance(broker.engine.table, DummyTable)
    assert broker.engine.table.symbol == "BTC/USD"
    assert broker.engine.table.timeframe == "1m"
    assert isinstance(broker.engine.table.connector, DummyConnector)
    assert broker.engine.table.connector.mode == "testing"


def test_broker_backtest_requires_csv(monkeypatch):
    monkeypatch.setattr(core_config, "MODE", "backtest", raising=False)

    class DummyBacktest:
        def __init__(self, csv_path, symbol=None):
            self.csv_path = csv_path
            self.symbol = symbol

    monkeypatch.setattr(broker_module, "TableBacktest", DummyBacktest)

    broker = broker_module.BrokerInterface(csv_path="dummy.csv", symbol="BTCUSDT")

    assert isinstance(broker.engine.table, DummyBacktest)
    assert broker.engine.table.csv_path == "dummy.csv"


def test_broker_live_mode_not_available(monkeypatch):
    monkeypatch.setattr(core_config, "MODE", "live", raising=False)

    with pytest.raises(NotImplementedError):
        broker_module.BrokerInterface(symbol="BTC/USD", interval="1m")
