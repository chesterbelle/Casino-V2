# 🎮 Crear Custom Players

Tutorial completo para crear tu propia estrategia de position sizing.

---

## 🎯 ¿Qué es un Player?

Un **Player** es un módulo que decide **cuánto apostar** basándose en el análisis probabilístico de Gemini.

**Responsabilidad:** Convertir `Verdict` (probabilidades) en `size` (fracción de equity).

---

## 📋 Requisitos

### Firma de Función

```python
def calculate_position_size(
    verdict: Verdict,
    equity: float,
    meta: Optional[dict] = None
) -> Optional[float]:
    """
    Args:
        verdict: Veredicto de Gemini (probabilidades, métricas)
        equity: Capital disponible en USDT
        meta: Metadata adicional (opcional)
    
    Returns:
        float: Fracción de equity [0.0, 1.0]
        None: No apostar
    """
```

### Imports Necesarios

```python
from typing import Optional
import config

# Si necesitas acceder a Verdict
import sys
sys.path.insert(0, '..')
from gemini.gemini_core import Verdict
```

---

## 🚀 Tutorial Paso a Paso

### Paso 1: Crear Archivo

```bash
# Crear nuevo player
touch players/my_custom_player.py
```

### Paso 2: Implementar Template

```python
# players/my_custom_player.py

from typing import Optional
import config

def calculate_position_size(verdict, equity, meta=None):
    """
    Mi estrategia personalizada de sizing.
    """
    # 1. Validación básica
    if not verdict or not verdict.side:
        return None
    
    # 2. Filtrar estrategias aprobadas
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # 3. Tu lógica aquí
    # TODO: Implementar tu estrategia
    
    return 0.01  # Placeholder: 1% fijo
```

### Paso 3: Implementar Lógica

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Estrategia: Size basado en credibilidad promedio.
    
    - Credibilidad > 0.8 → 2%
    - Credibilidad > 0.6 → 1%
    - Credibilidad <= 0.6 → No apostar
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Calcular credibilidad promedio
    avg_credibility = sum(m.credibility for m in approved) / len(approved)
    
    # Decidir size según credibilidad
    if avg_credibility > 0.8:
        size = 0.02
    elif avg_credibility > 0.6:
        size = 0.01
    else:
        return None
    
    # Respetar límite máximo
    return min(size, config.MAX_POSITION_SIZE)
```

### Paso 4: Testear

```python
# test_my_player.py

from players import my_custom_player as player
from gemini.gemini_core import Gemini

gemini = Gemini()
signals = [...]  # Tu señal de prueba

verdict = gemini.evaluate_signals_v2(signals, 10000.0)
size = player.calculate_position_size(verdict, 10000.0)

print(f"Size calculado: {size}")
assert size is None or (0.0 <= size <= 0.02)
```

### Paso 5: Usar en Main

```bash
python main.py --player=my_custom_player
```

---

## 💡 Ejemplos de Estrategias

### 1. Threshold Player

**Concepto:** Apostar solo si p̂ > umbral

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Solo apuesta si p̂ > 55%.
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Calcular p̂ promedio
    avg_p_hat = sum(m.p_hat for m in approved) / len(approved)
    
    # Threshold: 55%
    if avg_p_hat > 0.55:
        return 0.01
    else:
        return None
```

---

### 2. Tiered Player

**Concepto:** Size escalonado según edge

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Size escalonado:
    - p̂ > 60% → 3%
    - p̂ > 57% → 2%
    - p̂ > 54% → 1%
    - p̂ <= 54% → No apostar
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    avg_p_hat = sum(m.p_hat for m in approved) / len(approved)
    
    if avg_p_hat > 0.60:
        size = 0.03
    elif avg_p_hat > 0.57:
        size = 0.02
    elif avg_p_hat > 0.54:
        size = 0.01
    else:
        return None
    
    return min(size, config.MAX_POSITION_SIZE)
```

---

### 3. Volatility-Adjusted Player

**Concepto:** Reducir size en alta volatilidad

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Ajusta size según volatilidad del mercado.
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Kelly base
    positive_kelly = [m.kelly for m in approved if m.kelly > 0]
    if not positive_kelly:
        return None
    
    base_size = min(positive_kelly) * config.KELLY_FRACTION
    
    # Ajustar por volatilidad
    volatility = meta.get("volatility", 0.02) if meta else 0.02
    
    if volatility > 0.04:
        multiplier = 0.5
    elif volatility > 0.03:
        multiplier = 0.75
    else:
        multiplier = 1.0
    
    adjusted_size = base_size * multiplier
    return min(adjusted_size, config.MAX_POSITION_SIZE)
```

---

### 4. Confidence Ensemble Player

**Concepto:** Promediar Kelly de estrategias más confiables

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Promedia Kelly de estrategias con credibilidad > 70%.
    """
    if not verdict or not verdict.side:
        return None
    
    # Filtrar aprobadas con alta credibilidad
    confident = [
        m for m in verdict.metrics 
        if m.approved and m.credibility > 0.7 and m.kelly > 0
    ]
    
    if not confident:
        return None
    
    # Promedio ponderado por credibilidad
    total_cred = sum(m.credibility for m in confident)
    weighted_kelly = sum(
        m.kelly * (m.credibility / total_cred) 
        for m in confident
    )
    
    size = weighted_kelly * config.KELLY_FRACTION
    return min(size, config.MAX_POSITION_SIZE)
```

---

### 5. Drawdown-Aware Player

**Concepto:** Reducir size durante drawdown

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Reduce size si equity < peak.
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Kelly base
    positive_kelly = [m.kelly for m in approved if m.kelly > 0]
    if not positive_kelly:
        return None
    
    base_size = min(positive_kelly) * config.KELLY_FRACTION
    
    # Ajustar por drawdown
    peak = meta.get("peak_equity", equity) if meta else equity
    drawdown_pct = (peak - equity) / peak if peak > 0 else 0.0
    
    if drawdown_pct > 0.15:
        multiplier = 0.5  # Reducir 50% si DD > 15%
    elif drawdown_pct > 0.10:
        multiplier = 0.75  # Reducir 25% si DD > 10%
    else:
        multiplier = 1.0
    
    adjusted_size = base_size * multiplier
    return min(adjusted_size, config.MAX_POSITION_SIZE)
```

---

## 🧪 Testing de Players

### Test Unitario

```python
# test_my_player.py

import sys
sys.path.insert(0, '.')

from players import my_custom_player as player
from gemini.gemini_core import Gemini, Verdict, ParticipantMetrics, Participant

def test_basic_sizing():
    """Test que player retorna size válido."""
    # Mock verdict
    verdict = Verdict(
        trade_id="test_123",
        side="LONG",
        reason="aprobado",
        metrics=[
            ParticipantMetrics(
                participant=Participant("TestStrategy", "BUCKET_A", "BTCUSDT", "15min"),
                support=500,
                p_hat=0.58,
                credibility=0.75,
                p_conservative=0.55,
                kelly=0.024,
                approved=True,
                reason="approved",
                p_star=0.50,
                r_net=0.009,
                l_net=0.011
            )
        ],
        participants=[],
        meta={}
    )
    
    size = player.calculate_position_size(verdict, 10000.0)
    
    assert size is not None, "Size no debe ser None con estrategia aprobada"
    assert 0.0 <= size <= 0.02, f"Size debe estar en [0, 0.02], got {size}"
    print(f"✅ Test pasado: size = {size}")

if __name__ == "__main__":
    test_basic_sizing()
```

### Backtest Comparativo

```bash
# Comparar tu player con Kelly
python main.py --player=kelly > results_kelly.txt
python main.py --player=my_custom_player > results_custom.txt

# Comparar resultados
diff results_kelly.txt results_custom.txt
```

---

## 📊 Métricas Disponibles en Verdict

```python
# Acceso a métricas por estrategia
for metric in verdict.metrics:
    print(f"Estrategia: {metric.participant.strategy}")
    print(f"  p̂: {metric.p_hat:.2%}")
    print(f"  Credibilidad: {metric.credibility:.2%}")
    print(f"  Kelly: {metric.kelly:.4f}")
    print(f"  Soporte: {metric.support}")
    print(f"  Aprobada: {metric.approved}")
```

---

## ⚙️ Configuraciones Útiles

```python
# config.py - Variables disponibles

# Límites
MAX_POSITION_SIZE = 0.02      # 2% máximo

# Kelly
KELLY_FRACTION = 0.2          # 20% de Kelly óptimo

# Risk/Reward
TAKE_PROFIT = 0.01            # 1%
STOP_LOSS = 0.01              # 1%

# Bayesian
BAYES_ALPHA = 1.0
BAYES_BETA = 1.0
BAYES_CREDIBILITY_THRESHOLD = 0.6

# Memory
MIN_SUPPORT = 500             # Mínimo trades para aprobar
```

---

## 🎯 Best Practices

### 1. Siempre Validar

```python
# ✅ BIEN
if not verdict or not verdict.side:
    return None

if not approved_metrics:
    return None

# ❌ MAL (puede crashear)
size = min(m.kelly for m in verdict.metrics)
```

### 2. Respetar Límites

```python
# ✅ BIEN
return min(calculated_size, config.MAX_POSITION_SIZE)

# ❌ MAL (puede exceder límite)
return calculated_size
```

### 3. Documentar Lógica

```python
# ✅ BIEN
def calculate_position_size(verdict, equity, meta=None):
    """
    Estrategia: Kelly ajustado por volatilidad.
    
    Lógica:
    1. Calcula Kelly base
    2. Reduce si volatilidad > 3%
    3. Límite máximo 2%
    
    Returns:
        float [0, 1] o None
    """
```

### 4. Ser Conservador

```python
# ✅ BIEN - Conservador cuando hay duda
if avg_p_hat < 0.52 or credibility < 0.6:
    return None  # No apostar

# ⚠️ RIESGOSO - Apostar con poca confianza
if avg_p_hat > 0.50:
    return 0.03  # 3% con apenas 50%
```

---

## 🔧 Troubleshooting

### Player retorna None siempre

**Causa:** Estrategias no aprobadas (< MIN_SUPPORT)

**Solución:**
```python
# Ver qué pasa con las métricas
for m in verdict.metrics:
    print(f"{m.participant.strategy}: support={m.support}, approved={m.approved}")
```

### Size muy pequeño

**Causa:** Kelly muy bajo o KELLY_FRACTION muy conservador

**Solución:**
```python
# Ajustar en config.py
KELLY_FRACTION = 0.5  # Más agresivo (50% de Kelly)
```

### Crashes con KeyError

**Causa:** Acceso a campo que no existe

**Solución:**
```python
# ✅ BIEN - Usar .get() con default
volatility = meta.get("volatility", 0.02) if meta else 0.02

# ❌ MAL
volatility = meta["volatility"]  # Crashea si no existe
```

---

## 📚 Recursos

- [Arquitectura Gemini/Player](../architecture/gemini-player.md)
- [API Reference](../reference/api-players.md)
- [Ejemplos de Players](../../players/)

---

**← [Volver al índice](../README.md)**
