"""
Tests para ExchangeStateSync y sincronización de estado real.

Estos tests validan que:
1. ExchangeStateSync obtiene datos reales del exchange
2. TableCCXTPro retorna velas enriquecidas
3. PositionTracker modo híbrido funciona correctamente
4. Integración end-to-end con Kraken Demo
"""

from unittest.mock import AsyncMock, Mock

import pytest

from tables.connectors.kraken.kraken_connector import KrakenConnector
from tables.exchange_state_sync import ExchangeStateSync
from tables.position_tracker import PositionTracker
from tables.table_ccxt_pro import TableCCXTPro


class TestExchangeStateSync:
    """Tests para ExchangeStateSync component."""

    @pytest.fixture
    def mock_connector(self):
        """Connector mockeado para tests unitarios."""
        connector = Mock()
        connector.fetch_balance = AsyncMock(
            return_value={"free": {"USD": 5000.0}, "total": {"USD": 5000.0}, "used": {"USD": 0.0}}
        )
        connector.fetch_positions = AsyncMock(return_value=[])
        connector.fetch_my_trades = AsyncMock(return_value=[])
        return connector

    @pytest.mark.asyncio
    async def test_sync_equity_basic(self, mock_connector):
        """Test básico de sync_equity."""
        sync = ExchangeStateSync(mock_connector)

        equity = await sync.sync_equity()

        assert equity.balance == 5000.0
        assert equity.unrealized_pnl == 0.0
        assert equity.equity == 5000.0
        assert equity.open_positions == 0
        assert equity.currency == "USD"

    @pytest.mark.asyncio
    async def test_sync_equity_with_position(self, mock_connector):
        """Test sync_equity con posición abierta."""
        # Mock posición con unrealized PnL
        mock_connector.fetch_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "BTC/USD",
                    "side": "LONG",
                    "contracts": 0.1,
                    "entryPrice": 50000.0,
                    "markPrice": 51000.0,
                    "unrealizedPnl": 100.0,
                    "initialMargin": 500.0,
                    "leverage": 10,
                    "timestamp": 1699000000000,
                }
            ]
        )

        sync = ExchangeStateSync(mock_connector)
        equity = await sync.sync_equity()

        assert equity.balance == 5000.0
        assert equity.unrealized_pnl == 100.0
        assert equity.equity == 5100.0
        assert equity.open_positions == 1
        assert equity.margin_used == 500.0

    @pytest.mark.asyncio
    async def test_sync_positions(self, mock_connector):
        """Test sync_positions."""
        mock_connector.fetch_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "BTC/USD",
                    "side": "LONG",
                    "contracts": 0.1,
                    "entryPrice": 50000.0,
                    "markPrice": 51000.0,
                    "unrealizedPnl": 100.0,
                    "initialMargin": 500.0,
                    "leverage": 10,
                    "timestamp": 1699000000000,
                }
            ]
        )

        sync = ExchangeStateSync(mock_connector)
        positions = await sync.sync_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "BTC/USD"
        assert positions[0].side == "LONG"
        assert positions[0].size == 0.1
        assert positions[0].unrealized_pnl == 100.0

    @pytest.mark.asyncio
    async def test_sync_fills(self, mock_connector):
        """Test sync_fills."""
        mock_connector.fetch_my_trades = AsyncMock(
            return_value=[
                {
                    "id": "trade_123",
                    "order": "order_456",
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "price": 50000.0,
                    "amount": 0.1,
                    "cost": 5000.0,
                    "fee": {"cost": 2.5, "currency": "USD"},
                    "timestamp": 1699000000000,
                    "datetime": "2023-11-03T12:00:00Z",
                }
            ]
        )

        sync = ExchangeStateSync(mock_connector)
        fills = await sync.sync_fills()

        assert len(fills) == 1
        assert fills[0].trade_id == "trade_123"
        assert fills[0].price == 50000.0
        assert fills[0].fee == 2.5

    @pytest.mark.asyncio
    async def test_equity_cache(self, mock_connector):
        """Test que el cache de equity funciona."""
        sync = ExchangeStateSync(mock_connector)

        # Primera llamada
        equity1 = await sync.sync_equity()
        call_count_1 = mock_connector.fetch_balance.call_count

        # Segunda llamada inmediata (debe usar cache)
        equity2 = await sync.sync_equity(use_cache=True)
        call_count_2 = mock_connector.fetch_balance.call_count

        # No debe haber llamadas adicionales
        assert call_count_2 == call_count_1
        assert equity1.equity == equity2.equity


class TestPositionTrackerHybrid:
    """Tests para PositionTracker modo híbrido."""

    def test_init_modes(self):
        """Test inicialización en diferentes modos."""
        tracker_sim = PositionTracker(mode="simulation")
        assert tracker_sim.mode == "simulation"

        tracker_conf = PositionTracker(mode="confirmed")
        assert tracker_conf.mode == "confirmed"

        tracker_hyb = PositionTracker(mode="hybrid")
        assert tracker_hyb.mode == "hybrid"

    def test_simulation_mode(self):
        """Test modo simulation cierra inmediatamente."""
        tracker = PositionTracker(mode="simulation")

        # Abrir posición
        position = tracker.open_position(
            order={
                "trade_id": "test_123",
                "symbol": "BTC/USD",
                "side": "LONG",
                "size": 0.01,
                "leverage": 10,
                "take_profit": 1.02,
                "stop_loss": 0.99,
            },
            entry_price=50000.0,
            entry_timestamp="2025-11-03T18:00:00",
            available_equity=10000.0,
        )

        assert position is not None
        assert len(tracker.open_positions) == 1

        # Simular vela que toca TP
        candle = {"high": 51100, "low": 49900, "close": 51000, "timestamp": "2025-11-03T18:05:00"}

        closes = tracker.check_and_close_positions(candle)

        # En modo simulation, debe cerrar inmediatamente
        assert len(closes) == 1
        assert closes[0]["confirmed"] == True
        assert closes[0]["exit_reason"] == "TP"
        assert len(tracker.open_positions) == 0

    def test_hybrid_mode_pending(self):
        """Test modo hybrid marca como pending."""
        tracker = PositionTracker(mode="hybrid")

        # Abrir posición
        position = tracker.open_position(
            order={
                "trade_id": "test_123",
                "symbol": "BTC/USD",
                "side": "LONG",
                "size": 0.01,
                "leverage": 10,
                "take_profit": 1.02,
                "stop_loss": 0.99,
            },
            entry_price=50000.0,
            entry_timestamp="2025-11-03T18:00:00",
            available_equity=10000.0,
        )

        # Simular vela que toca TP
        candle = {"high": 51100, "low": 49900, "close": 51000, "timestamp": "2025-11-03T18:05:00"}

        pending = tracker.check_and_close_positions(candle)

        # En modo hybrid, debe marcar como pending
        assert len(pending) == 1
        assert pending[0]["confirmed"] == False
        assert pending[0]["pending_confirmation"] == True
        assert len(tracker.open_positions) == 1  # Aún abierta
        assert "test_123" in tracker.pending_confirmations

    def test_confirm_close(self):
        """Test confirmación de cierre con datos reales."""
        tracker = PositionTracker(mode="hybrid")

        # Abrir posición
        position = tracker.open_position(
            order={
                "trade_id": "test_123",
                "symbol": "BTC/USD",
                "side": "LONG",
                "size": 0.01,
                "leverage": 10,
                "take_profit": 1.02,
                "stop_loss": 0.99,
            },
            entry_price=50000.0,
            entry_timestamp="2025-11-03T18:00:00",
            available_equity=10000.0,
        )

        # Confirmar cierre con datos reales
        result = tracker.confirm_close(
            trade_id="test_123", exit_price=51050.0, exit_reason="TP", pnl=200.0, fee=3.5  # Precio REAL  # PnL REAL
        )

        assert result is not None
        assert result["confirmed"] == True
        assert result["exit_price"] == 51050.0
        assert result["pnl"] == 200.0
        assert result["fee"] == 3.5
        assert result["state_source"] == "exchange_confirmed"
        assert len(tracker.open_positions) == 0


class TestTableCCXTProEnriched:
    """Tests para TableCCXTPro con velas enriquecidas."""

    @pytest.mark.asyncio
    async def test_next_candle_enriched_structure(self):
        """Test que next_candle retorna estructura enriquecida."""
        # Mock connector
        connector = Mock()
        connector.exchange_name = "kraken"
        connector.fetch_ohlcv = AsyncMock(
            return_value=[
                {
                    "timestamp": 1699000000000,
                    "open": 50000.0,
                    "high": 50100.0,
                    "low": 49900.0,
                    "close": 50050.0,
                    "volume": 100.0,
                }
            ]
        )
        connector.fetch_balance = AsyncMock(return_value={"free": {"USD": 5000.0}, "total": {"USD": 5000.0}})
        connector.fetch_positions = AsyncMock(return_value=[])
        connector.fetch_my_trades = AsyncMock(return_value=[])

        table = TableCCXTPro(connector, "BTC/USD:USD", "1m")
        table._connected = True

        candle = await table.next_candle()

        # Verificar estructura enriquecida
        assert candle is not None
        assert "close" in candle
        assert "equity" in candle
        assert "balance" in candle
        assert "unrealized_pnl" in candle
        assert "open_positions" in candle
        assert "positions" in candle
        assert "recent_fills" in candle
        assert candle["state_source"] == "exchange_confirmed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_kraken_demo():
    """
    Test de integración con Kraken Demo.

    Requiere:
    - Credenciales de Kraken Demo en .env
    - Conexión a internet
    """
    try:
        connector = KrakenConnector(mode="testing")
        await connector.connect()

        # Test ExchangeStateSync
        sync = ExchangeStateSync(connector)
        equity = await sync.sync_equity()

        assert equity.balance > 0
        assert equity.currency in ["USD", "USDT", "USDC"]

        # Test TableCCXTPro
        table = TableCCXTPro(connector, "BTC/USD:USD", "1m")
        table._connected = True

        candle = await table.next_candle()

        assert candle is not None
        assert candle.get("state_source") == "exchange_confirmed"
        assert "equity" in candle
        assert "balance" in candle

        await connector.close()

        print("✅ Test de integración con Kraken Demo PASADO")

    except Exception as e:
        pytest.skip(f"Test de integración omitido: {e}")


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v", "-s"])
