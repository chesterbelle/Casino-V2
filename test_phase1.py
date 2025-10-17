"""
====================================================
🧪 TEST FASE 1 - Separación Gemini/Player
====================================================

Script de validación para verificar que la nueva arquitectura
funciona correctamente y produce resultados similares.

Tests:
------
1. Verdict Structure: Verifica que Verdict contenga campos esperados
2. Kelly Player: Calcula sizing correctamente
3. Fixed Player: Retorna tamaño fijo cuando hay edge
4. Order Construction: make_order_from_verdict() funciona
5. Compatibility: evaluate_signals() legacy sigue funcionando

Uso:
----
    python test_phase1.py

Expected Output:
----------------
✅ Todos los tests pasan
❌ Si algo falla, se muestra el error específico
"""

import sys
import logging
from typing import List

# Setup path
import config
from gemini.gemini_core import Gemini, Verdict, Decision, ParticipantMetrics, Participant
from players import kelly_player, fixed_player

# Setup logging
logging.basicConfig(level=logging.WARNING)  # Silenciar logs para tests


# ============================================================
# 🧪 TEST UTILITIES
# ============================================================
class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def run_test(self, name: str, test_func):
        """Ejecuta un test y registra resultado"""
        try:
            test_func()
            self.passed += 1
            self.tests.append((name, True, None))
            print(f"✅ {name}")
        except AssertionError as e:
            self.failed += 1
            self.tests.append((name, False, str(e)))
            print(f"❌ {name}: {e}")
        except Exception as e:
            self.failed += 1
            self.tests.append((name, False, f"Error inesperado: {e}"))
            print(f"❌ {name}: Error inesperado - {e}")
    
    def print_summary(self):
        """Imprime resumen final"""
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE TESTS")
        print("=" * 60)
        print(f"✅ Pasados: {self.passed}")
        print(f"❌ Fallados: {self.failed}")
        print(f"📈 Total: {self.passed + self.failed}")
        print("=" * 60)
        
        if self.failed > 0:
            print("\n❌ Tests fallados:")
            for name, passed, error in self.tests:
                if not passed:
                    print(f"  • {name}: {error}")
            sys.exit(1)
        else:
            print("\n🎉 ¡Todos los tests pasaron!")
            sys.exit(0)


# ============================================================
# 🧪 MOCK DATA
# ============================================================
def create_mock_signals_long() -> List[dict]:
    """Crea señales mock que disparan LONG"""
    return [
        {
            "timestamp": "2024-01-01T12:00:00",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "side": "LONG",
            "origin": "RSIReversion",
            "contributors": ["RSIReversion"],
            "features": {"rsi2": 8.5, "bbw": 0.25, "atr": 0.3},
            "range_score": 1
        }
    ]


def create_mock_signals_conflict() -> List[dict]:
    """Crea señales mock con conflicto (LONG y SHORT)"""
    return [
        {
            "timestamp": "2024-01-01T12:00:00",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "side": "LONG",
            "origin": "RSIReversion",
            "contributors": ["RSIReversion"],
            "features": {"rsi2": 8.5, "bbw": 0.25},
            "range_score": 1
        },
        {
            "timestamp": "2024-01-01T12:00:00",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "side": "SHORT",
            "origin": "BollingerTouch",
            "contributors": ["BollingerTouch"],
            "features": {"bbw": 0.25},
            "range_score": 1
        }
    ]


def create_mock_verdict_approved() -> Verdict:
    """Crea un Verdict mock con participantes aprobados"""
    participant = Participant(
        strategy="RSIReversion",
        bucket="BBW=L|RS1|H=M",
        symbol="BTCUSDT",
        timeframe="15m"
    )
    
    metrics = ParticipantMetrics(
        participant=participant,
        support=100,
        p_hat=0.65,
        credibility=0.85,
        p_conservative=0.58,
        kelly=0.15,
        approved=True,
        reason="approved",
        p_star=0.5,
        r_net=0.01,
        l_net=0.01
    )
    
    return Verdict(
        trade_id="TEST-BTCUSDT@15m-LONG-001",
        side="LONG",
        reason="aprobado",
        metrics=[metrics],
        participants=[participant],
        meta={
            "timestamp": "2024-01-01T12:00:00",
            "symbol": "BTCUSDT",
            "timeframe": "15m"
        }
    )


def create_mock_verdict_no_edge() -> Verdict:
    """Crea un Verdict mock sin edge positivo"""
    participant = Participant(
        strategy="RSIReversion",
        bucket="BBW=L|RS1|H=M",
        symbol="BTCUSDT",
        timeframe="15m"
    )
    
    metrics = ParticipantMetrics(
        participant=participant,
        support=50,
        p_hat=0.48,
        credibility=0.3,
        p_conservative=0.45,
        kelly=0.0,
        approved=False,
        reason="edge_not_positive",
        p_star=0.5,
        r_net=0.01,
        l_net=0.01
    )
    
    return Verdict(
        trade_id="TEST-BTCUSDT@15m-LONG-002",
        side="LONG",
        reason="sin_aprobadas",
        metrics=[metrics],
        participants=[participant],
        meta={
            "timestamp": "2024-01-01T12:00:00",
            "symbol": "BTCUSDT",
            "timeframe": "15m"
        }
    )


# ============================================================
# 🧪 TESTS
# ============================================================
def test_verdict_structure():
    """Test 1: Verificar estructura de Verdict"""
    gemini = Gemini()
    signals = create_mock_signals_long()
    verdict = gemini.evaluate_signals_v2(signals, equity=10000.0)
    
    # Verificar que tiene los campos esperados
    assert verdict is not None, "Verdict no debe ser None"
    assert hasattr(verdict, 'trade_id'), "Verdict debe tener trade_id"
    assert hasattr(verdict, 'side'), "Verdict debe tener side"
    assert hasattr(verdict, 'reason'), "Verdict debe tener reason"
    assert hasattr(verdict, 'metrics'), "Verdict debe tener metrics"
    assert hasattr(verdict, 'participants'), "Verdict debe tener participants"
    assert hasattr(verdict, 'meta'), "Verdict debe tener meta"
    
    # Verificar que side es correcto
    assert verdict.side in ["LONG", "SHORT", None], f"Side inválido: {verdict.side}"
    
    # Verificar que metrics es una lista
    assert isinstance(verdict.metrics, list), "Metrics debe ser una lista"


def test_verdict_conflict():
    """Test 2: Verificar manejo de conflicto (LONG y SHORT simultáneos)"""
    gemini = Gemini()
    signals = create_mock_signals_conflict()
    verdict = gemini.evaluate_signals_v2(signals, equity=10000.0)
    
    # En caso de conflicto, side debe ser None
    assert verdict.side is None, "En conflicto, side debe ser None"
    assert verdict.reason == "conflicto_de_lado", f"Razón incorrecta: {verdict.reason}"
    assert verdict.trade_id is not None, "Trade_id debe existir para entrenar"


def test_kelly_player_with_edge():
    """Test 3: Kelly Player con edge positivo"""
    verdict = create_mock_verdict_approved()
    size = kelly_player.calculate_position_size(verdict, equity=10000.0)
    
    assert size is not None, "Kelly debe retornar size con edge positivo"
    assert size > 0, "Size debe ser mayor que 0"
    assert size <= config.MAX_POSITION_SIZE, "Size no debe exceder MAX_POSITION_SIZE"
    print(f"    → Kelly size: {size:.4f}")


def test_kelly_player_no_edge():
    """Test 4: Kelly Player sin edge positivo"""
    verdict = create_mock_verdict_no_edge()
    size = kelly_player.calculate_position_size(verdict, equity=10000.0)
    
    assert size is None, "Kelly debe retornar None sin edge positivo"


def test_fixed_player_with_edge():
    """Test 5: Fixed Player con edge positivo"""
    verdict = create_mock_verdict_approved()
    size = fixed_player.calculate_position_size(verdict, equity=10000.0)
    
    assert size is not None, "Fixed debe retornar size con edge positivo"
    assert size > 0, "Size debe ser mayor que 0"
    expected = getattr(config, "FIXED_POSITION_SIZE", config.MAX_POSITION_SIZE)
    assert abs(size - expected) < 0.0001, f"Size debe ser {expected}, got {size}"
    print(f"    → Fixed size: {size:.4f}")


def test_fixed_player_no_edge():
    """Test 6: Fixed Player sin edge positivo"""
    verdict = create_mock_verdict_no_edge()
    size = fixed_player.calculate_position_size(verdict, equity=10000.0)
    
    assert size is None, "Fixed debe retornar None sin edge positivo"


def test_make_order_from_verdict():
    """Test 7: Construcción de orden desde Verdict"""
    gemini = Gemini()
    verdict = create_mock_verdict_approved()
    size_fraction = 0.02
    
    order = gemini.make_order_from_verdict(verdict, size_fraction, ghost=False)
    
    # Verificar estructura de orden
    assert order is not None, "Orden no debe ser None"
    assert order.get("side") == "LONG", f"Side incorrecto: {order.get('side')}"
    assert order.get("size") == size_fraction, f"Size incorrecto: {order.get('size')}"
    assert order.get("trade_id") == verdict.trade_id, "Trade_id debe coincidir"
    assert order.get("ghost") == False, "Ghost debe ser False"
    assert "take_profit" in order, "Debe tener take_profit"
    assert "stop_loss" in order, "Debe tener stop_loss"
    print(f"    → Order: {order.get('side')} size={order.get('size'):.4f}")


def test_make_order_ghost():
    """Test 8: Construcción de orden GHOST"""
    gemini = Gemini()
    verdict = create_mock_verdict_approved()
    
    order = gemini.make_order_from_verdict(verdict, size_fraction=0.0, ghost=True)
    
    assert order.get("size") == 0.0, "Size debe ser 0 para GHOST"
    assert order.get("ghost") == True, "Ghost debe ser True"
    print(f"    → GHOST order created")


def test_legacy_api_compatibility():
    """Test 9: API legacy (evaluate_signals) sigue funcionando"""
    gemini = Gemini()
    signals = create_mock_signals_long()
    decision = gemini.evaluate_signals(signals, equity=10000.0)
    
    # Verificar que retorna Decision (legacy)
    assert isinstance(decision, Decision), "Debe retornar Decision"
    assert decision.action in ["BET", "GHOST", "SKIP"], f"Action inválida: {decision.action}"
    assert decision.order is not None or decision.action == "SKIP", "Order debe existir si no es SKIP"
    print(f"    → Legacy API: {decision.action}")


def test_empty_signals():
    """Test 10: Manejo de señales vacías"""
    gemini = Gemini()
    verdict = gemini.evaluate_signals_v2([], equity=10000.0)
    
    assert verdict.side is None, "Side debe ser None con señales vacías"
    assert verdict.trade_id is None, "Trade_id debe ser None con señales vacías"
    assert verdict.reason == "sin_señales", f"Razón incorrecta: {verdict.reason}"


def test_player_info_functions():
    """Test 11: Funciones de info de Players"""
    verdict = create_mock_verdict_approved()
    
    # Kelly info
    kelly_info = kelly_player.get_kelly_info(verdict)
    assert "p_conservative" in kelly_info, "Kelly info debe tener p_conservative"
    assert "f_kelly" in kelly_info, "Kelly info debe tener f_kelly"
    
    # Fixed info
    fixed_info = fixed_player.get_info(verdict)
    assert "fixed_size" in fixed_info, "Fixed info debe tener fixed_size"
    assert "has_edge" in fixed_info, "Fixed info debe tener has_edge"
    
    print(f"    → Kelly p_cons={kelly_info.get('p_conservative'):.4f}, f={kelly_info.get('f_kelly'):.4f}")
    print(f"    → Fixed has_edge={fixed_info.get('has_edge')}")


# ============================================================
# 🚀 MAIN
# ============================================================
def main():
    print("\n" + "=" * 60)
    print("🧪 INICIANDO TESTS - FASE 1: SEPARACIÓN GEMINI/PLAYER")
    print("=" * 60 + "\n")
    
    runner = TestRunner()
    
    # Ejecutar tests
    runner.run_test("Test 1: Estructura de Verdict", test_verdict_structure)
    runner.run_test("Test 2: Manejo de conflicto LONG/SHORT", test_verdict_conflict)
    runner.run_test("Test 3: Kelly Player con edge positivo", test_kelly_player_with_edge)
    runner.run_test("Test 4: Kelly Player sin edge", test_kelly_player_no_edge)
    runner.run_test("Test 5: Fixed Player con edge positivo", test_fixed_player_with_edge)
    runner.run_test("Test 6: Fixed Player sin edge", test_fixed_player_no_edge)
    runner.run_test("Test 7: Construcción de orden desde Verdict", test_make_order_from_verdict)
    runner.run_test("Test 8: Construcción de orden GHOST", test_make_order_ghost)
    runner.run_test("Test 9: API legacy compatible", test_legacy_api_compatibility)
    runner.run_test("Test 10: Señales vacías", test_empty_signals)
    runner.run_test("Test 11: Funciones de info", test_player_info_functions)
    
    # Resumen
    runner.print_summary()


if __name__ == "__main__":
    main()
