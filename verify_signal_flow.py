"""
Verification script for Casino-V3 Signal Flow.
Manually dispatches a SignalEvent to test OrderManager -> Croupier execution.
"""
import asyncio
import logging
import time
from unittest.mock import MagicMock, AsyncMock

from core.v3.engine import Engine
from core.v3.events import SignalEvent, EventType
from core.v3.execution import OrderManager
from croupier.croupier import Croupier

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("VerifyFlow")

async def main():
    logger.info("🧪 Starting Signal Flow Verification...")

    # 1. Mock Components
    adapter = MagicMock()
    adapter.symbol = "BTC/USDT:USDT"
    
    # Mock Croupier.execute_order to return success
    croupier = MagicMock(spec=Croupier)
    croupier.execute_order = AsyncMock(return_value={"status": "filled", "id": "TEST_ORDER_123"})
    croupier.initial_balance = 1000.0

    # 2. Initialize Engine & OrderManager
    engine = Engine()
    order_manager = OrderManager(engine, croupier)
    await order_manager.start()
    
    # 3. Start Engine (in background)
    engine_task = asyncio.create_task(engine.start())
    
    # Allow engine to start
    await asyncio.sleep(1)

    # 4. Dispatch Test Signal
    logger.info("📢 Dispatching Test Signal...")
    signal = SignalEvent(
        type=EventType.SIGNAL,
        timestamp=time.time(),
        symbol="BTC/USDT:USDT",
        side="LONG",
        strategy_name="TestStrategy",
        score=0.95,
        metadata={"reason": "Manual Test"}
    )
    await engine.dispatch(signal)

    # 5. Wait for processing
    await asyncio.sleep(1)

    # 6. Verify Execution
    logger.info("🔍 Verifying Execution...")
    croupier.execute_order.assert_called_once()
    call_args = croupier.execute_order.call_args[0][0]
    
    if call_args["symbol"] == "BTC/USDT:USDT" and call_args["side"] == "LONG":
        logger.info("✅ SUCCESS: OrderManager correctly called Croupier with valid payload.")
        logger.info(f"Payload: {call_args}")
    else:
        logger.error(f"❌ FAILURE: Croupier called with unexpected arguments: {call_args}")

    # Cleanup
    await engine.stop()
    await order_manager.stop()
    engine_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
