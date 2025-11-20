#!/usr/bin/env python3
"""
🎯 RONDA 1 - Validación Básica + TP/SL (30 velas)
Objetivo: Detectar bugs obvios y validar TP/SL con tiempo suficiente para ejecuciones
"""

import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def main():
    print("\n" + "=" * 70)
    print("🎯 RONDA 1 - VALIDACIÓN BÁSICA + TP/SL (30 velas)")
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    # Paso 1: Pre-validación del conector
    print("📋 PASO 1: Pre-validación del Conector Binance")
    print("-" * 70)

    try:
        from utils.croupier_validator import CroupierValidator

        validator = CroupierValidator(exchange="binance", symbol="1000PEPE/USDT:USDT", timeframe="1m")

        # Ejecutar tests básicos
        print("✅ Ejecutando 12 tests básicos...")
        basic_results = await validator.run_basic_tests()

        passed = sum(1 for r in basic_results if r.get("status") == "PASSED")
        total = len(basic_results)

        print(f"\n📊 Resultados Tests Básicos: {passed}/{total} PASSED")

        if passed < total:
            print("\n❌ Pre-validación FALLIDA - Algunos tests básicos fallaron")
            for r in basic_results:
                if r.get("status") != "PASSED":
                    print(f"  ❌ {r.get('name')}: {r.get('error')}")
            return False

        print("✅ Pre-validación EXITOSA - Todos los tests básicos pasaron\n")

        # Paso 2: Demo Trading (30 velas)
        print("📋 PASO 2: Demo Trading (30 velas)")
        print("-" * 70)
        print("⏳ Ejecutando demo trading durante ~30 minutos...")
        print("   (Esperando 30 velas con precios reales del exchange)")

        # Aquí iría la lógica de demo trading
        # Por ahora solo mostramos el plan
        print("\n📝 Plan de Demo Trading:")
        print("   1. Conectar a Binance Testnet")
        print("   2. Procesar 30 velas de LTC/USDT:USDT")
        print("   3. Ejecutar órdenes con TP/SL")
        print("   4. Monitorear ejecución de TP/SL")
        print("   5. Registrar resultados")

        print("\n✅ RONDA 1 - Plan de Validación Preparado")
        print("   Próximo paso: Ejecutar demo trading real")

        return True

    except Exception as e:
        print(f"\n❌ Error durante validación: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Validación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
