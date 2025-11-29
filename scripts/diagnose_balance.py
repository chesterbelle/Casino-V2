"""
Script de diagnóstico para verificar sincronización de balance.
"""

import asyncio
import logging

from exchanges.adapters import CCXTAdapter
from exchanges.adapters.exchange_state_sync import ExchangeStateSync
from exchanges.connectors import KrakenConnector, ResilientConnector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def diagnose():
    """Diagnóstico de balance."""
    logger.info("=" * 80)
    logger.info("🔍 DIAGNÓSTICO DE BALANCE")
    logger.info("=" * 80)

    # Conectar
    kraken = KrakenConnector(mode="testing")
    connector = ResilientConnector(
        connector=kraken,
        enable_state_recovery=False,  # Deshabilitado para diagnóstico
    )

    adapter = CCXTAdapter(connector=connector, symbol="BTC/USD:USD")
    await adapter.connect()

    logger.info("\n📊 BALANCE DESDE DIFERENTES FUENTES:")
    logger.info("-" * 80)

    # 1. Balance directo del connector
    try:
        balance_data = await connector.fetch_balance()
        connector_balance = float(balance_data.get("free", {}).get("USD", 0))
        logger.info(f"1. Connector.fetch_balance():     ${connector_balance:,.2f} USD")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # 2. Balance del BalanceManager
    try:
        manager_balance = adapter.balance_manager.balance
        logger.info(f"2. BalanceManager.balance:        ${manager_balance:,.2f} USD")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # 3. Equity del BalanceManager
    try:
        manager_equity = adapter.balance_manager.equity
        logger.info(f"3. BalanceManager.equity:         ${manager_equity:,.2f} USD")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # 4. Posiciones abiertas
    try:
        # Prefer normalized positions via ExchangeStateSync
        state_sync = ExchangeStateSync(connector)
        try:
            positions = await state_sync.sync_positions()
        except Exception:
            positions = await connector.fetch_positions()

        logger.info(f"\n📍 POSICIONES ABIERTAS: {len(positions)}")
        for pos in positions:
            if isinstance(pos, dict):
                sym = pos.get("symbol")
                contracts = pos.get("contracts")
                entry = pos.get("entryPrice", 0)
                mark = pos.get("markPrice", 0)
                pnl = pos.get("unrealizedPnl", 0)
            else:
                sym = getattr(pos, "symbol", None)
                contracts = getattr(pos, "contracts", None) or getattr(pos, "size", None)
                entry = getattr(pos, "entry_price", None) or getattr(pos, "entryPrice", 0)
                mark = getattr(pos, "mark_price", None) or getattr(pos, "markPrice", 0)
                pnl = getattr(pos, "unrealized_pnl", None) or getattr(pos, "unrealizedPnl", 0)

            logger.info(f"   - {sym}: {contracts} contracts")
            logger.info(f"     Entry: ${entry:,.2f}")
            logger.info(f"     Mark: ${mark:,.2f}")
            logger.info(f"     PnL: ${pnl:+,.2f}")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # 5. Órdenes abiertas
    try:
        orders = await connector._connector.fetch_open_orders()
        logger.info(f"\n📋 ÓRDENES ABIERTAS: {len(orders)}")
        for order in orders:
            logger.info(f"   - {order.get('id')}: {order.get('side')} {order.get('amount')}")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # 6. Verificar discrepancia
    logger.info("\n" + "=" * 80)
    if abs(connector_balance - manager_balance) > 0.01:
        logger.warning("⚠️  DISCREPANCIA DETECTADA!")
        logger.warning(f"   Diferencia: ${abs(connector_balance - manager_balance):,.2f}")
        logger.warning("   El BalanceManager NO está sincronizado con el exchange")
    else:
        logger.info("✅ Balance sincronizado correctamente")

    logger.info("=" * 80)

    await connector.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
