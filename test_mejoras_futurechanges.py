"""
====================================================
🧪 Tests para validar las mejoras de futurechanges.md
====================================================

Valida las 3 mejoras implementadas:
1. memory.py: Sincronización de _counts desde CSV
2. gemini_core.py: Simplificación de lógica de decisión
3. table_backtest.py: Fallback para trade_id faltante
"""

import os
import sys
import tempfile
import csv
from datetime import datetime

# Ajustar path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini.memory import GeminiMemory
from gemini.gemini_core import Gemini
from tables.table_backtest import TableBacktest


def test_memory_csv_sync():
    """
    Test 1: Validar que _counts se sincroniza desde CSV cuando tiene más datos que JSON
    """
    print("\n" + "="*60)
    print("🧪 Test 1: Sincronización de _counts desde CSV")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "memory_log.csv")
        state_path = os.path.join(tmpdir, "memory_state.json")
        
        # Crear CSV con 50 registros (30 wins, 20 losses)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "trade_id", "strategy", "bucket", "symbol", "timeframe", "market", "result"])
            
            for i in range(50):
                result = 1 if i < 30 else 0  # 30 wins, 20 losses
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    f"trade_{i}",
                    "TestStrategy",
                    "BUCKET_A",
                    "BTCUSDT",
                    "15min",
                    "BTCUSDT@15min",
                    result
                ])
        
        # Crear memoria con ventana de 100 (suficiente para todos los datos)
        memory = GeminiMemory(
            csv_path=csv_path,
            state_path=state_path,
            memory_window=100,
            autosave_interval=10
        )
        
        # Verificar que _counts se sincronizó correctamente
        key = "BTCUSDT@15min|BUCKET_A|TestStrategy"
        counts = memory.get_counts(key)
        
        print(f"   Registros en CSV: 50 (30 wins, 20 losses)")
        print(f"   Counts cargados: {counts}")
        print(f"   Winrate: {memory.get_winrate(key):.2%}")
        
        assert counts["wins"] == 30, f"Expected 30 wins, got {counts['wins']}"
        assert counts["losses"] == 20, f"Expected 20 losses, got {counts['losses']}"
        assert memory.get_winrate(key) == 0.6, f"Expected 60% winrate, got {memory.get_winrate(key)}"
        
        print("   ✅ Test 1 PASADO: _counts sincronizados correctamente desde CSV")
        return True


def test_gemini_decision_logic():
    """
    Test 2: Validar que la lógica simplificada de decisión funciona igual
    """
    print("\n" + "="*60)
    print("🧪 Test 2: Lógica simplificada de decisión en Gemini")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "memory_log.csv")
        state_path = os.path.join(tmpdir, "memory_state.json")
        
        # Crear CSV vacío
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "trade_id", "strategy", "bucket", "symbol", "timeframe", "market", "result"])
        
        memory = GeminiMemory(csv_path=csv_path, state_path=state_path)
        gemini = Gemini(memory=memory)
        
        # Test caso 1: Sin señales -> SKIP
        decision = gemini.evaluate_signals([], equity=10000.0)
        assert decision.action == "SKIP", f"Expected SKIP, got {decision.action}"
        assert decision.reason == "sin_señales", f"Expected 'sin_señales', got {decision.reason}"
        print("   ✅ Caso 1: Sin señales -> SKIP")
        
        # Test caso 2: Señales sin estrategias aprobadas -> GHOST
        signals = [{
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": "BTCUSDT",
            "timeframe": "15min",
            "side": "LONG",
            "origin": "TestSensor",
            "features": {
                "bbw": 0.015,
                "rsi": 35.0,
                "hurst": 0.45
            }
        }]
        
        decision = gemini.evaluate_signals(signals, equity=10000.0)
        assert decision.action == "GHOST", f"Expected GHOST, got {decision.action}"
        assert decision.reason == "sin_aprobadas", f"Expected 'sin_aprobadas', got {decision.reason}"
        print("   ✅ Caso 2: Señales sin aprobadas -> GHOST (sin_aprobadas)")
        
        # Test caso 3: Conflicto de lado -> GHOST con side=None
        signals_conflict = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": "BTCUSDT",
                "timeframe": "15min",
                "side": "LONG",
                "origin": "SensorA",
                "features": {"bbw": 0.015, "rsi": 35.0, "hurst": 0.45}
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": "BTCUSDT",
                "timeframe": "15min",
                "side": "SHORT",
                "origin": "SensorB",
                "features": {"bbw": 0.015, "rsi": 65.0, "hurst": 0.55}
            }
        ]
        
        decision = gemini.evaluate_signals(signals_conflict, equity=10000.0)
        assert decision.action == "GHOST", f"Expected GHOST, got {decision.action}"
        assert decision.reason == "conflicto_de_lado", f"Expected 'conflicto_de_lado', got {decision.reason}"
        assert decision.side is None, f"Expected None side for conflict, got {decision.side}"
        print("   ✅ Caso 3: Conflicto LONG/SHORT -> GHOST (conflicto_de_lado, side=None)")
        
        print("   ✅ Test 2 PASADO: Lógica simplificada funciona correctamente")
        return True


def test_table_backtest_trade_id_fallback():
    """
    Test 3: Validar que table_backtest asigna trade_id si falta
    """
    print("\n" + "="*60)
    print("🧪 Test 3: Fallback de trade_id en TableBacktest")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test_data.csv")
        
        # Crear CSV de prueba con 10 velas
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            
            base_price = 100.0
            for i in range(10):
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    base_price + i,
                    base_price + i + 2,
                    base_price + i - 1,
                    base_price + i + 1,
                    1000.0
                ])
        
        table = TableBacktest(csv_path, symbol="TESTUSDT", timeframe="15min")
        
        # Avanzar una vela
        candle = table.next_candle()
        assert candle is not None, "Failed to get first candle"
        
        # Test 1: Orden SIN trade_id -> debe asignar automáticamente
        order_without_id = {
            "symbol": "TESTUSDT",
            "timeframe": "15min",
            "timestamp": candle["timestamp"],
            "side": "LONG",
            "size": 0.01,
            "ghost": True  # GHOST para no afectar balance
        }
        
        result = table.execute_order(order_without_id)
        
        print(f"   Orden sin trade_id ejecutada")
        print(f"   trade_id asignado: {result.get('trade_id')}")
        
        assert result.get("trade_id") is not None, "trade_id should not be None"
        assert result.get("trade_id").startswith("backtest_"), f"trade_id should start with 'backtest_', got {result.get('trade_id')}"
        print("   ✅ trade_id asignado automáticamente")
        
        # Test 2: Orden CON trade_id -> debe respetar el original
        candle2 = table.next_candle()
        order_with_id = {
            "symbol": "TESTUSDT",
            "timeframe": "15min",
            "timestamp": candle2["timestamp"],
            "side": "LONG",
            "size": 0.01,
            "trade_id": "custom_trade_123",
            "ghost": True
        }
        
        result2 = table.execute_order(order_with_id)
        
        print(f"   Orden con trade_id personalizado ejecutada")
        print(f"   trade_id respetado: {result2.get('trade_id')}")
        
        assert result2.get("trade_id") == "custom_trade_123", f"trade_id should be 'custom_trade_123', got {result2.get('trade_id')}"
        print("   ✅ trade_id personalizado respetado")
        
        print("   ✅ Test 3 PASADO: Fallback de trade_id funciona correctamente")
        return True


def run_all_tests():
    """Ejecuta todos los tests y reporta resultados"""
    print("\n" + "="*60)
    print("🎯 VALIDACIÓN DE MEJORAS - futurechanges.md")
    print("="*60)
    
    tests = [
        ("Memory CSV Sync", test_memory_csv_sync),
        ("Gemini Decision Logic", test_gemini_decision_logic),
        ("TableBacktest trade_id Fallback", test_table_backtest_trade_id_fallback),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"   ❌ FALLO: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("📊 RESUMEN DE TESTS")
    print("="*60)
    print(f"   ✅ Pasados: {passed}/{len(tests)}")
    print(f"   ❌ Fallidos: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n   🎉 ¡TODAS LAS MEJORAS VALIDADAS EXITOSAMENTE!")
        print("="*60)
        return True
    else:
        print("\n   ⚠️  Algunos tests fallaron. Revisa los errores arriba.")
        print("="*60)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
