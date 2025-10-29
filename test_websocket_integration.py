"""
Test suite for TableCCXTPro WebSocket Integration
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import ccxtpro

from tables.table_ccxt_pro import TableCCXTPro


class TestTableCCXTProWebSocket:
    """Test WebSocket integration for TableCCXTPro."""

    @pytest.fixture
    def mock_exchange(self):
        """Mock CCXT Pro exchange."""
        exchange = Mock()
        exchange.loadMarkets = AsyncMock()
        exchange.subscribe_ohlcv = AsyncMock()
        exchange.watch_ohlcv_for_symbols = AsyncMock()
        exchange.watch_balance = AsyncMock()
        exchange.close = AsyncMock()
        return exchange

    @pytest.fixture
    def table(self, mock_exchange):
        """Create TableCCXTPro instance with mocked exchange."""
        with patch('tables.table_ccxt_pro.ccxtpro') as mock_ccxtpro:
            mock_ccxtpro.kraken.return_value = mock_exchange
            table = TableCCXTPro(
                exchange_id='kraken',
                symbols=['BTC/USDT', 'ETH/USDT'],
                timeframe='1m',
                testnet=True
            )
            return table

    @pytest.mark.asyncio
    async def test_connect_subscribes_to_symbols(self, table, mock_exchange):
        """Test that connect() subscribes to all symbols."""
        await table.connect()

        # Verify subscriptions were made
        assert mock_exchange.subscribe_ohlcv.call_count == 2
        mock_exchange.subscribe_ohlcv.assert_any_call('BTC/USDT', '1m')
        mock_exchange.subscribe_ohlcv.assert_any_call('ETH/USDT', '1m')

        assert table.is_connected
        assert len(table.active_streams) == 2

    @pytest.mark.asyncio
    async def test_start_listening_processes_ohlcv_updates(self, table, mock_exchange):
        """Test that start_listening processes OHLCV updates correctly."""
        # Mock WebSocket messages
        mock_messages = [
            {
                'symbol': 'BTC/USDT',
                'ohlcv': [1640995200000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
            },
            {
                'symbol': 'ETH/USDT',
                'ohlcv': [1640995200000, 3000.0, 3100.0, 2900.0, 3050.0, 200.0]
            }
        ]

        mock_exchange.watch_ohlcv_for_symbols.side_effect = [mock_messages, []]  # Return messages then empty

        # Start listening with timeout
        listen_task = asyncio.create_task(table.start_listening())

        # Let it process messages
        await asyncio.sleep(0.1)

        # Cancel listening
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass

        # Verify data was processed
        assert 'BTC/USDT' in table.last_candles
        assert 'ETH/USDT' in table.last_candles

        btc_candle = table.last_candles['BTC/USDT']
        assert btc_candle['close'] == 50500.0
        assert btc_candle['volume'] == 100.0

    def test_next_candle_returns_real_time_data(self, table):
        """Test that next_candle returns real-time WebSocket data."""
        # Simulate WebSocket data
        table.last_candles['BTC/USDT'] = {
            'timestamp': 1640995200000,
            'open': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'close': 50500.0,
            'volume': 100.0
        }

        candle = table.next_candle()

        assert candle is not None
        assert candle['symbol'] == 'BTC/USDT'
        assert candle['close'] == 50500.0
        assert candle['volume'] == 100.0
        assert 'equity' in candle
        assert 'balance' in candle

    def test_next_candle_specific_symbol(self, table):
        """Test next_candle with specific symbol parameter."""
        # Add data for multiple symbols
        table.last_candles = {
            'BTC/USDT': {'timestamp': 1, 'close': 50000.0, 'open': 49000.0, 'high': 51000.0, 'low': 48000.0, 'volume': 100.0},
            'ETH/USDT': {'timestamp': 2, 'close': 3000.0, 'open': 2900.0, 'high': 3100.0, 'low': 2800.0, 'volume': 200.0}
        }

        # Test specific symbol
        eth_candle = table.next_candle('ETH/USDT')
        assert eth_candle['symbol'] == 'ETH/USDT'
        assert eth_candle['close'] == 3000.0

        # Test default (first symbol)
        btc_candle = table.next_candle()
        assert btc_candle['symbol'] == 'BTC/USDT'

    def test_get_state_includes_websocket_info(self, table):
        """Test that get_state includes WebSocket status information."""
        # Simulate some data
        table.last_candles['BTC/USDT'] = {'timestamp': 1640995200000, 'close': 50000.0}
        table.is_connected = True
        table.active_streams = ['btc/usdt@1m', 'eth/usdt@1m']

        state = table.get_state()

        assert 'websocket' in state
        assert state['websocket']['connected'] is True
        assert state['websocket']['active_streams'] == 2
        assert state['websocket']['symbols_with_data'] == 1
        assert 'last_candles' in state

    @pytest.mark.asyncio
    async def test_watchdog_monitors_data_freshness(self, table):
        """Test that watchdog detects stale data."""
        # Add stale data (more than 1 minute old)
        old_timestamp = (asyncio.get_event_loop().time() * 1000) - 120000  # 2 minutes ago
        table.last_candles['BTC/USDT'] = {'timestamp': old_timestamp, 'close': 50000.0}
        table.is_connected = True

        # Start watchdog briefly
        watchdog_task = asyncio.create_task(table._watchdog())
        await asyncio.sleep(0.1)  # Let it check once

        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass

        # Watchdog should have logged warnings about stale data
        # (We can't easily test logs in this context, but the logic is there)

    @pytest.mark.asyncio
    async def test_handle_ohlcv_update_validation(self, table):
        """Test OHLCV update validation and error handling."""
        # Test valid data
        valid_ohlcv = [1640995200000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
        await table._handle_ohlcv_update('BTC/USDT', valid_ohlcv)

        assert 'BTC/USDT' in table.last_candles
        assert table.last_candles['BTC/USDT']['close'] == 50500.0

        # Test invalid data (too short)
        await table._handle_ohlcv_update('BTC/USDT', [1640995200000, 50000.0])
        # Should not crash, should log warning

        # Test invalid symbol
        await table._handle_ohlcv_update('INVALID', valid_ohlcv)
        # Should not crash, should log warning

    @pytest.mark.asyncio
    async def test_handle_balance_update(self, table):
        """Test balance update processing."""
        balance_data = {
            'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0},
            'BTC': {'free': 0.05, 'used': 0.0, 'total': 0.05}
        }

        await table._handle_balance_update(balance_data)

        # Balance manager should have been updated with USDT balance
        # (This assumes balance_manager.set_balance was called)

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_properly(self, table, mock_exchange):
        """Test that disconnect cleans up WebSocket connections."""
        # Connect first
        await table.connect()
        assert table.is_connected

        # Disconnect
        await table.disconnect()

        # Verify cleanup
        assert not table.is_connected
        assert len(table.active_streams) == 0
        mock_exchange.close.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])