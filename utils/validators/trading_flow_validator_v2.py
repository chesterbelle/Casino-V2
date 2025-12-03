"""
Trading Flow Validator - Redesigned for Refactored Architecture
----------------------------------------------------------------
Validates the refactored Croupier architecture:
- OrderExecutor: Individual order execution
- OCOManager: OCO bracket creation (main + TP + SL)
- ReconciliationService: State synchronization
- PositionTracker: Position management
- Real exchange connectivity

Usage:
    python -m utils.validators.trading_flow_validator_v2 \\
        --exchange binance \\
        --symbol LTCUSDT \\
        --mode demo \\
        --size 0.05
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from croupier.croupier import Croupier
from exchanges.adapters import ExchangeAdapter
from exchanges.connectors.binance.binance_native_connector import BinanceNativeConnector


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/validator_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
        handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
    )


logger = logging.getLogger("ValidatorV2")


class TradingFlowValidatorV2:
    """Validates refactored Croupier architecture with real exchange."""

    def __init__(self, exchange_id="binance", symbol="LTCUSDT", mode="demo", size=0.05):
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.mode = mode
        self.size = size

        # Load credentials
        load_dotenv()
        if mode == "demo":
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            secret = os.getenv("BINANCE_TESTNET_SECRET")
        else:
            api_key = os.getenv("BINANCE_API_KEY")
            secret = os.getenv("BINANCE_API_SECRET")

        if not api_key or not secret:
            raise ValueError(f"Missing API keys for mode {mode}")

        # Setup connector
        self.connector = BinanceNativeConnector(
            api_key=api_key, secret=secret, mode=mode, enable_websocket=False  # Not needed for testing
        )

        self.adapter = None
        self.croupier = None

    async def setup(self):
        """Initialize adapter and croupier."""
        logger.info(f"🔧 Setting up validator for {self.exchange_id.upper()} - {self.symbol}")

        # Connect
        await self.connector.connect()

        # Create adapter
        self.adapter = ExchangeAdapter(self.connector, self.symbol)

        # Get balance
        balance_data = await self.connector.fetch_balance()
        initial_balance = balance_data.get("free", {}).get("USDT", 0.0)

        if initial_balance < 10:
            raise ValueError(f"Insufficient balance: ${initial_balance:.2f}")

        logger.info(f"💰 Balance: ${initial_balance:,.2f}")

        # Create croupier
        self.croupier = Croupier(
            exchange_adapter=self.adapter, initial_balance=initial_balance, max_concurrent_positions=10
        )

        # Pre-test cleanup
        await self.cleanup()
        logger.info("✅ Setup complete\n")

    async def cleanup(self):
        """Clean all positions and orders."""
        logger.info("🧹 Cleaning up...")

        try:
            # Close all positions for this symbol
            positions = await self.connector.fetch_positions()
            for pos in positions:
                if pos.get("symbol") == self.symbol and abs(float(pos.get("contracts", 0))) > 0:
                    side = "sell" if float(pos["contracts"]) > 0 else "buy"
                    await self.connector.create_order(
                        symbol=self.symbol, order_type="market", side=side, amount=abs(float(pos["contracts"]))
                    )
                    logger.info(f"  ✓ Closed position")

            # Cancel all open orders
            open_orders = await self.connector.fetch_open_orders(self.symbol)
            for order in open_orders:
                await self.connector.cancel_order(order["id"], self.symbol)
                logger.info(f"  ✓ Cancelled order {order['id']}")

            await asyncio.sleep(2)  # Let exchange process

        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")

    async def test_1_order_execution(self):
        """Test 1: Validate OrderExecutor executes orders correctly."""
        logger.info("=" * 60)
        logger.info("TEST 1: Order Execution via OrderExecutor")
        logger.info("=" * 60)

        # Get current price
        current_price = await self.adapter.get_current_price(self.symbol)
        logger.info(f"Current price: {current_price:.2f}")

        # Calculate test amount (Binance minimum notional is $5)
        # For LTCUSDT at ~$85, need at least 0.06 LTC
        test_amount = float(self.adapter.amount_to_precision(self.symbol, 0.07))

        # Execute market order directly via OrderExecutor
        order = {"symbol": self.symbol, "type": "market", "side": "buy", "amount": test_amount}

        logger.info(f"📤 Executing market order: {order}")
        result = await self.croupier.order_executor.execute_market_order(order)

        # Validations
        assert result is not None, "Order result is None"
        order_id = result.get("order_id") or result.get("id")
        assert order_id is not None, "No order_id in result"
        logger.info(f"✅ Order executed: {order_id}")

        # Verify in exchange
        await asyncio.sleep(1)
        exchange_order = await self.connector.fetch_order(order_id, self.symbol)
        assert exchange_order is not None, "Order not found in exchange"
        logger.info(f"✅ Order verified in exchange: {exchange_order.get('status')}")

        # Close position immediately
        await self.connector.create_order(symbol=self.symbol, order_type="market", side="sell", amount=test_amount)

        logger.info("✅ TEST 1 PASSED\n")

    async def test_2_oco_bracket(self):
        """Test 2: Validate OCOManager creates complete OCO bracket."""
        logger.info("=" * 60)
        logger.info("TEST 2: OCO Bracket Creation (Main + TP + SL)")
        logger.info("=" * 60)

        # Create order with OCO
        order = {
            "symbol": self.symbol,
            "side": "LONG",
            "size": self.size,
            "take_profit": 0.02,  # +2%
            "stop_loss": 0.02,  # -2%
            "trade_id": f"test2_{int(datetime.now().timestamp())}",
        }

        logger.info(f"📤 Creating OCO bracket: {order}")
        result = await self.croupier.execute_order(order)

        # Validations
        assert "main_order" in result, "No main_order in result"
        assert "tp_order" in result, "No tp_order in result"
        assert "sl_order" in result, "No sl_order in result"
        assert result["fill_price"] > 0, "Invalid fill_price"

        logger.info(f"✅ Main order: {result['main_order'].get('id')}")
        logger.info(f"✅ TP order: {result['tp_order'].get('id')}")
        logger.info(f"✅ SL order: {result['sl_order'].get('id')}")
        logger.info(f"✅ Fill price: {result['fill_price']:.2f}")

        # Verify TP/SL in exchange
        await asyncio.sleep(2)
        open_orders = await self.connector.fetch_open_orders(self.symbol)
        order_ids = [o["id"] for o in open_orders]

        tp_id = result["tp_order"].get("order_id") or result["tp_order"].get("id")
        sl_id = result["sl_order"].get("order_id") or result["sl_order"].get("id")

        assert tp_id in order_ids, f"TP order {tp_id} not in exchange"
        assert sl_id in order_ids, f"SL order {sl_id} not in exchange"
        logger.info(f"✅ TP/SL verified in exchange")

        logger.info("✅ TEST 2 PASSED\n")

        # Keep position open for next test
        return result

    async def test_3_position_tracking(self):
        """Test 3: Validate PositionTracker maintains correct state."""
        logger.info("=" * 60)
        logger.info("TEST 3: Position Tracking")
        logger.info("=" * 60)

        # Verify current positions (should be 1 from test 2)
        positions = self.croupier.position_tracker.open_positions
        assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"

        position = positions[0]
        assert position.symbol == self.symbol, f"Wrong symbol: {position.symbol}"
        assert position.side == "LONG", f"Wrong side: {position.side}"
        assert position.tp_order_id is not None, "No TP order ID"
        assert position.sl_order_id is not None, "No SL order ID"

        logger.info(f"✅ Position: {position.trade_id}")
        logger.info(f"✅ Symbol: {position.symbol}")
        logger.info(f"✅ Side: {position.side}")
        logger.info(f"✅ TP ID: {position.tp_order_id}")
        logger.info(f"✅ SL ID: {position.sl_order_id}")

        logger.info("✅ TEST 3 PASSED\n")

    async def test_4_balance_equity(self):
        """Test 4: Validate balance and equity calculations."""
        logger.info("=" * 60)
        logger.info("TEST 4: Balance & Equity")
        logger.info("=" * 60)

        balance = self.croupier.balance_manager.get_balance()
        equity = self.croupier.get_equity()

        assert balance > 0, "Invalid balance"
        assert equity > 0, "Invalid equity"

        logger.info(f"✅ Balance: ${balance:.2f}")
        logger.info(f"✅ Equity: ${equity:.2f}")

        # With open position, equity might differ from balance
        diff = abs(equity - balance)
        logger.info(f"   Difference: ${diff:.2f}")

        logger.info("✅ TEST 4 PASSED\n")

    async def test_5_position_close(self):
        """Test 5: Validate position close and TP/SL cancellation."""
        logger.info("=" * 60)
        logger.info("TEST 5: Position Close & TP/SL Cleanup")
        logger.info("=" * 60)

        # Get current position
        positions = self.croupier.position_tracker.open_positions
        assert len(positions) == 1, "No position to close"

        position = positions[0]
        tp_id = position.tp_order_id
        sl_id = position.sl_order_id
        trade_id = position.trade_id

        logger.info(f"📤 Closing position: {trade_id}")
        await self.croupier.close_position(trade_id)

        # Verify position closed
        await asyncio.sleep(2)
        positions = self.croupier.position_tracker.open_positions
        assert len(positions) == 0, f"Position not closed, still {len(positions)} open"
        logger.info(f"✅ Position closed")

        # Verify TP/SL cancelled
        open_orders = await self.connector.fetch_open_orders(self.symbol)
        order_ids = [o["id"] for o in open_orders]

        assert tp_id not in order_ids, f"TP order {tp_id} not cancelled"
        assert sl_id not in order_ids, f"SL order {sl_id} not cancelled"
        logger.info(f"✅ TP/SL orders cancelled")

        logger.info("✅ TEST 5 PASSED\n")

    async def test_6_error_handling(self):
        """Test 6: Validate error handling."""
        logger.info("=" * 60)
        logger.info("TEST 6: Error Handling")
        logger.info("=" * 60)

        # Test 1: Order without size or amount
        try:
            order = {"symbol": self.symbol, "side": "LONG", "tp": 0.02, "sl": 0.02}
            await self.croupier.execute_order(order)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            logger.info(f"✅ Caught expected error: {e}")

        # Test 2: Invalid amount (too small)
        try:
            order = {"symbol": self.symbol, "side": "LONG", "size": 0.0001, "tp": 0.02, "sl": 0.02}  # Very small
            await self.croupier.execute_order(order)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            logger.info(f"✅ Caught expected error: {e}")

        logger.info("✅ TEST 6 PASSED\n")

    async def run_all_tests(self):
        """Run all validation tests."""
        logger.info("\n" + "=" * 60)
        logger.info(" TRADING FLOW VALIDATOR V2 - REFACTORED ARCHITECTURE")
        logger.info("=" * 60 + "\n")

        await self.setup()

        try:
            await self.test_1_order_execution()
            await self.test_2_oco_bracket()
            await self.test_3_position_tracking()
            await self.test_4_balance_equity()
            await self.test_5_position_close()
            await self.test_6_error_handling()

            logger.info("\n" + "=" * 60)
            logger.info("✅ ALL TESTS PASSED")
            logger.info("=" * 60 + "\n")

        except Exception as e:
            logger.error(f"\n❌ Test failed: {e}", exc_info=True)
            raise

        finally:
            await self.cleanup()
            # Connector cleanup happens automatically


async def main():
    parser = argparse.ArgumentParser(description="Trading Flow Validator V2")
    parser.add_argument("--exchange", required=True, help="Exchange ID (binance)")
    parser.add_argument("--symbol", required=True, help="Trading symbol (LTCUSDT)")
    parser.add_argument("--mode", default="demo", choices=["demo", "live"], help="Mode")
    parser.add_argument("--size", type=float, default=0.05, help="Position size fraction (0.05 = 5%)")

    args = parser.parse_args()

    setup_logging()

    validator = TradingFlowValidatorV2(exchange_id=args.exchange, symbol=args.symbol, mode=args.mode, size=args.size)

    await validator.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
