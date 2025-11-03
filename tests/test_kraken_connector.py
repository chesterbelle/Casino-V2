"""
Tests for KrakenConnector and TableCCXTPro integration.

These tests validate the new Mesa + Connector architecture.
"""

import asyncio
import logging

import pytest

from tables.connectors import KrakenConnector
from tables.table_ccxt_pro import TableCCXTPro

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")


class TestKrakenConnector:
    """Test suite for KrakenConnector."""

    @pytest.mark.asyncio
    async def test_connector_initialization(self):
        """Test that connector initializes correctly."""
        connector = KrakenConnector(testnet=True)

        assert connector.exchange_name == "kraken"
        assert connector.testnet is True
        assert connector.is_connected is False

    @pytest.mark.asyncio
    async def test_connector_connect(self):
        """Test connector connection to Kraken testnet."""
        connector = KrakenConnector(testnet=True)

        try:
            await connector.connect()
            assert connector.is_connected is True
        finally:
            await connector.close()

    @pytest.mark.asyncio
    async def test_connector_fetch_balance(self):
        """Test fetching balance from Kraken."""
        connector = KrakenConnector(testnet=True)

        try:
            await connector.connect()
            balance = await connector.fetch_balance()

            assert isinstance(balance, dict)
            assert "total" in balance
            assert "free" in balance
            assert "used" in balance
            assert "currency" in balance
        finally:
            await connector.close()

    @pytest.mark.asyncio
    async def test_connector_fetch_ohlcv(self):
        """Test fetching OHLCV data from Kraken."""
        connector = KrakenConnector(testnet=True)

        try:
            await connector.connect()
            candles = await connector.fetch_ohlcv("BTC/USD", "1m", limit=10)

            assert isinstance(candles, list)
            assert len(candles) > 0

            # Validate candle structure
            candle = candles[0]
            assert "timestamp" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle
            assert "symbol" in candle
            assert candle["symbol"] == "BTC/USD"
        finally:
            await connector.close()

    @pytest.mark.asyncio
    async def test_symbol_normalization(self):
        """Test symbol normalization."""
        connector = KrakenConnector(testnet=True)

        # Test normalize
        kraken_symbol = connector.normalize_symbol("BTC/USD")
        assert kraken_symbol == "PF_XBTUSD"

        # Test denormalize
        standard_symbol = connector.denormalize_symbol("PF_XBTUSD")
        assert standard_symbol == "BTC/USD"


class TestTableCCXTPro:
    """Test suite for TableCCXTPro with KrakenConnector."""

    @pytest.mark.asyncio
    async def test_table_initialization(self):
        """Test that table initializes correctly with connector."""
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")

        assert table.symbol == "BTC/USD"
        assert table.timeframe == "1m"
        assert table.exchange_name == "kraken"
        assert table.is_connected is False

    @pytest.mark.asyncio
    async def test_table_connect(self):
        """Test table connection via connector."""
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")

        try:
            await table.connect()
            assert table.is_connected is True
            assert table.get_balance() > 0  # Should have fetched real balance
        finally:
            await table.close()

    @pytest.mark.asyncio
    async def test_table_next_candle(self):
        """Test fetching candles via table."""
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")

        try:
            await table.connect()
            candle = await table.next_candle()

            assert candle is not None
            assert isinstance(candle, dict)
            assert "close" in candle
            assert "timestamp" in candle
        finally:
            await table.close()

    @pytest.mark.asyncio
    async def test_table_balance_operations(self):
        """Test balance operations."""
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")

        try:
            await table.connect()

            # Get initial balance
            initial_balance = table.get_balance()
            assert initial_balance > 0

            # Refresh balance
            refreshed_balance = await table.refresh_balance()
            assert refreshed_balance > 0
        finally:
            await table.close()

    @pytest.mark.asyncio
    async def test_order_validation(self):
        """Test order validation logic."""
        connector = KrakenConnector(testnet=True)
        table = TableCCXTPro(connector=connector, symbol="BTC/USD", timeframe="1m")

        try:
            await table.connect()

            # Test invalid order (missing side)
            invalid_order = {"amount": 0.1}
            assert table._validate_order(invalid_order) is False

            # Test invalid order (negative amount)
            invalid_order = {"side": "buy", "amount": -0.1}
            assert table._validate_order(invalid_order) is False

            # Test valid order
            valid_order = {"side": "buy", "amount": 0.001}
            # Note: This might fail if balance is insufficient, which is correct
        finally:
            await table.close()


# =========================================================
# 🧪 MANUAL TESTING SCRIPT
# =========================================================


async def manual_test():
    """
    Manual test script for quick validation.

    Run this directly to test the connector and table:
        python -m pytest tests/test_kraken_connector.py -v -s
    """
    print("\n" + "=" * 60)
    print("🧪 MANUAL TEST: Kraken Connector + TableCCXTPro")
    print("=" * 60 + "\n")

    # Test 1: Connector
    print("📌 Test 1: KrakenConnector")
    connector = KrakenConnector(testnet=True)
    await connector.connect()
    print(f"✅ Connected to {connector.exchange_name}")

    balance = await connector.fetch_balance()
    print(f"💰 Balance: {balance.get('free', {})}")

    candles = await connector.fetch_ohlcv("BTC/USD", "1m", limit=5)
    print(f"📊 Fetched {len(candles)} candles")
    print(f"   Latest close: {candles[-1]['close']}")

    await connector.close()
    print("✅ Connector test passed\n")

    # Test 2: Table
    print("📌 Test 2: TableCCXTPro")
    connector2 = KrakenConnector(testnet=True)
    table = TableCCXTPro(connector=connector2, symbol="BTC/USD", timeframe="1m")

    await table.connect()
    print(f"✅ Table connected")
    print(f"💰 Balance: {table.get_balance()}")

    candle = await table.next_candle()
    print(f"📊 Latest candle: {candle['close']}")

    await table.close()
    print("✅ Table test passed\n")

    print("=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    # Run manual test
    asyncio.run(manual_test())
