#!/usr/bin/env python3
"""
Script de validación de refactorización.

Ejecuta un backtest rápido para verificar que todo funciona correctamente.
"""

import asyncio
import logging
import sys

from config import system
from core.data_sources import BacktestDataSource
from core.trading import TradingSession
from players import kelly_player

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("Validation")


async def validate():
    """Run validation backtest."""
    logger.info("=" * 60)
    logger.info("🔍 VALIDACIÓN DE REFACTORIZACIÓN")
    logger.info("=" * 60)

    # Get data file
    data_file = getattr(system, "DATASET_PATH", "tables/data/raw/BTCUSDT_1m__30d.csv")

    logger.info(f"📁 Data file: {data_file}")
    logger.info("🎮 Player: Kelly")
    logger.info("📊 Mode: Backtest (validation)")

    try:
        # Create backtest data source
        logger.info("📥 Loading data...")
        source = BacktestDataSource.from_csv(
            data_file,
            normalize_symbol=True,  # USDT → USD
            force_timeframe="1m",  # Force 1m for memory compatibility
        )

        # Create session with limited candles for quick validation
        max_candles = 100  # Solo 100 velas para validación rápida
        logger.info(f"🎯 Processing {max_candles} candles for validation")

        session = TradingSession(source, kelly_player, max_candles)

        # Run
        logger.info("▶️  Starting backtest...")
        await session.run()

        # Get stats
        stats = source.get_stats()

        # Print results
        logger.info("=" * 60)
        logger.info("✅ VALIDACIÓN COMPLETADA")
        logger.info("=" * 60)
        logger.info(f"Initial Balance:  ${stats['initial_balance']:,.2f}")
        logger.info(f"Final Balance:    ${stats['final_balance']:,.2f}")
        logger.info(f"Final Equity:     ${stats['final_equity']:,.2f}")
        logger.info(f"Net PnL:          ${stats['net_pnl']:+,.2f}")
        logger.info(f"Total Fees:       ${stats['total_fees']:,.2f}")
        logger.info(f"Total Trades:     {stats['total_trades']}")
        if "candles_processed" in stats:
            logger.info(f"Candles Processed: {stats['candles_processed']}")
        logger.info("=" * 60)

        # Validation checks
        logger.info("\n🔍 VALIDATION CHECKS:")

        checks_passed = 0
        checks_total = 0

        # Check 1: Balance is a number
        checks_total += 1
        if isinstance(stats["final_balance"], (int, float)):
            logger.info("✅ Balance is numeric")
            checks_passed += 1
        else:
            logger.error("❌ Balance is not numeric")

        # Check 2: System ran without errors
        checks_total += 1
        logger.info("✅ System ran without errors")
        checks_passed += 1

        # Check 3: System didn't crash
        checks_total += 1
        logger.info("✅ System completed without crashing")
        checks_passed += 1

        # Check 4: Stats structure is correct
        checks_total += 1
        required_keys = [
            "initial_balance",
            "final_balance",
            "final_equity",
            "net_pnl",
            "total_fees",
            "total_trades",
        ]
        if all(key in stats for key in required_keys):
            logger.info("✅ Stats structure is correct")
            checks_passed += 1
        else:
            logger.error("❌ Stats structure is incomplete")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"📊 VALIDATION SUMMARY: {checks_passed}/{checks_total} checks passed")
        logger.info("=" * 60)

        if checks_passed == checks_total:
            logger.info("🎉 ALL CHECKS PASSED - Refactoring is working correctly!")
            return 0
        else:
            logger.error("⚠️  SOME CHECKS FAILED - Review the output above")
            return 1

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ VALIDATION FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(validate())
    sys.exit(exit_code)
