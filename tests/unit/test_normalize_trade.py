"""
Test para validar que normalize_trade() funciona correctamente en cada conector.
"""


def test_binance_normalize_trade_with_close():
    """Test que BinanceConnector detecta correctamente un trade de cierre."""
    from exchanges.connectors.binance.binance_connector import BinanceConnector

    # Simular un trade de cierre de Binance
    raw_trade = {
        "id": "12345",
        "symbol": "LTC/USDT:USDT",
        "side": "buy",
        "price": 104.50,
        "amount": 2.5,
        "info": {
            "realizedPnl": "15.50",  # Binance retorna string
            "type": "MARKET",
        },
    }

    # Crear conector (sin conectar)
    connector = BinanceConnector(api_key="test", api_secret="test", testnet=True)

    # Normalizar trade
    normalized = connector.normalize_trade(raw_trade)

    # Verificar que se detectó como cierre
    assert normalized["is_close"] is True
    assert normalized["realized_pnl"] == 15.50
    assert normalized["close_reason"] == "MANUAL"


def test_binance_normalize_trade_without_close():
    """Test que BinanceConnector NO detecta un trade de apertura como cierre."""
    from exchanges.connectors.binance.binance_connector import BinanceConnector

    # Simular un trade de apertura de Binance
    raw_trade = {
        "id": "12345",
        "symbol": "LTC/USDT:USDT",
        "side": "buy",
        "price": 104.50,
        "amount": 2.5,
        "info": {
            "realizedPnl": "0",  # Sin PnL = apertura
            "type": "MARKET",
        },
    }

    connector = BinanceConnector(api_key="test", api_secret="test", testnet=True)

    normalized = connector.normalize_trade(raw_trade)

    # Verificar que NO se detectó como cierre
    assert normalized["is_close"] is False
    assert normalized["realized_pnl"] == 0.0
    assert normalized["close_reason"] is None


def test_kraken_normalize_trade_with_close():
    """Test que KrakenConnector detecta correctamente un trade de cierre."""
    from exchanges.connectors.kraken.kraken_connector import KrakenConnector

    # Simular un trade de cierre de Kraken
    raw_trade = {
        "id": "12345",
        "symbol": "BTC/USD",
        "side": "sell",
        "price": 45000.0,
        "amount": 0.1,
        "info": {
            "reduceOnly": True,  # Kraken usa reduceOnly
            "realizedPnl": 500.0,
            "orderType": "stop",
        },
    }

    connector = KrakenConnector(api_key="test", api_secret="test")

    normalized = connector.normalize_trade(raw_trade)

    # Verificar que se detectó como cierre
    assert normalized["is_close"] is True
    assert normalized["realized_pnl"] == 500.0
    assert normalized["close_reason"] == "SL"


def test_kraken_normalize_trade_without_close():
    """Test que KrakenConnector NO detecta un trade de apertura como cierre."""
    from exchanges.connectors.kraken.kraken_connector import KrakenConnector

    # Simular un trade de apertura de Kraken
    raw_trade = {
        "id": "12345",
        "symbol": "BTC/USD",
        "side": "buy",
        "price": 45000.0,
        "amount": 0.1,
        "info": {
            "reduceOnly": False,  # No es cierre
            "realizedPnl": 0.0,
            "orderType": "market",
        },
    }

    connector = KrakenConnector(api_key="test", api_secret="test")

    normalized = connector.normalize_trade(raw_trade)

    # Verificar que NO se detectó como cierre
    assert normalized["is_close"] is False
    assert normalized["realized_pnl"] == 0.0
    assert normalized["close_reason"] is None


def test_bybit_normalize_trade_with_close():
    """Test que BybitConnector detecta correctamente un trade de cierre."""
    from exchanges.connectors.bybit.bybit_connector import BybitConnector

    # Simular un trade de cierre de Bybit
    raw_trade = {
        "id": "12345",
        "symbol": "ETH/USDT:USDT",
        "side": "sell",
        "price": 3000.0,
        "amount": 1.0,
        "info": {
            "closedPnl": "50.25",  # Bybit retorna string
            "orderType": "Market",
        },
    }

    connector = BybitConnector(api_key="test", api_secret="test", demo=True)

    normalized = connector.normalize_trade(raw_trade)

    # Verificar que se detectó como cierre
    assert normalized["is_close"] is True
    assert normalized["realized_pnl"] == 50.25
    assert normalized["close_reason"] == "MANUAL"


def test_bybit_normalize_trade_without_close():
    """Test que BybitConnector NO detecta un trade de apertura como cierre."""
    from exchanges.connectors.bybit.bybit_connector import BybitConnector

    # Simular un trade de apertura de Bybit
    raw_trade = {
        "id": "12345",
        "symbol": "ETH/USDT:USDT",
        "side": "buy",
        "price": 3000.0,
        "amount": 1.0,
        "info": {
            "closedPnl": "0",  # Sin PnL = apertura
            "orderType": "Market",
        },
    }

    connector = BybitConnector(api_key="test", api_secret="test", demo=True)

    normalized = connector.normalize_trade(raw_trade)

    # Verificar que NO se detectó como cierre
    assert normalized["is_close"] is False
    assert normalized["realized_pnl"] == 0.0
    assert normalized["close_reason"] is None
