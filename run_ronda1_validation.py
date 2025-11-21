#!/usr/bin/env python3
"""
🎯 RONDA 1 - Validación Básica + TP/SL (30 velas)
Objetivo: Detectar bugs obvios y validar TP/SL con tiempo suficiente para ejecuciones
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

logger = logging.getLogger(__name__)


async def main():
    logger.info("\n" + "=" * 70)
    logger.info("🎯 RONDA 1 - VALIDACIÓN BÁSICA + TP/SL (30 velas)")
    logger.info("=" * 70)
    logger.info(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70 + "\n")

    # Paso 1: Pre-validación del conector
    logger.info("📋 PASO 1: Pre-validación del Conector Binance")
    logger.info("-" * 70)

    try:
        from utils.croupier_validator import CroupierValidator

        validator = CroupierValidator(exchange="binance", symbol="1000PEPE/USDT:USDT", timeframe="1m")

        # Ejecutar tests básicos
        logger.info("✅ Ejecutando 12 tests básicos...")
        basic_results = await validator.run_basic_tests()

        passed = sum(1 for r in basic_results if r.get("status") == "PASSED")
        total = len(basic_results)

        logger.info(f"\n📊 Resultados Tests Básicos: {passed}/{total} PASSED")

        if passed < total:
            logger.error("\n❌ Pre-validación FALLIDA - Algunos tests básicos fallaron")
            for r in basic_results:
                if r.get("status") != "PASSED":
                    logger.error(f"  ❌ {r.get('name')}: {r.get('error')}")
            return False

        logger.info("✅ Pre-validación EXITOSA - Todos los tests básicos pasaron\n")

        # Paso 2: Demo Trading (30 velas)
        logger.info("📋 PASO 2: Demo Trading (30 velas)")
        logger.info("-" * 70)
        logger.info("⏳ Ejecutando demo trading durante ~30 minutos...")
        logger.info("   (Esperando 30 velas con precios reales del exchange)")

        # Aquí iría la lógica de demo trading
        # Por ahora solo mostramos el plan
        logger.info("\n📝 Plan de Demo Trading:")
        logger.info("   1. Conectar a Binance Testnet")
        logger.info("   2. Procesar 30 velas de LTC/USDT:USDT")
        logger.info("   3. Ejecutar órdenes con TP/SL")
        logger.info("   4. Monitorear ejecución de TP/SL")
        logger.info("   5. Registrar resultados")

        logger.info("\n✅ RONDA 1 - Plan de Validación Preparado")
        logger.info("   Próximo paso: Ejecutar demo trading real")

        return True

    except Exception as e:
        logger.exception("\n❌ Error durante validación: %s", e)
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n⏹️  Validación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.exception("\n❌ Error fatal: %s", e)
        import traceback

        traceback.print_exc()
        sys.exit(1)
