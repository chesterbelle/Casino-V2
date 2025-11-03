# 🎯 Configuración de Nuevos Sensores (v0.2.0)

## Sensores Añadidos - Sprint 1

### **1. StochasticReversion** 📉
Detecta oversold/overbought usando oscilador estocástico.

```python
# config.py

ACTIVE_SENSORS = {
    # ... sensores existentes ...
    "StochasticReversion": True,  # ← NUEVO
}

SENSOR_PARAMS = {
    # ... parámetros existentes ...

    "StochasticReversion": {
        "k_period": 14,           # Periodo para %K
        "d_period": 3,            # Suavizado (%D)
        "low_threshold": 20.0,    # Oversold
        "high_threshold": 80.0,   # Overbought
    },
}
```

**Cuándo señala:**
- LONG: %K < 20 y %D < 20 (oversold extremo)
- SHORT: %K > 80 y %D > 80 (overbought extremo)

---

### **2. Supertrend** 📈
Indicador de tendencia basado en ATR. Muy robusto.

```python
ACTIVE_SENSORS = {
    # ... sensores existentes ...
    "Supertrend": True,  # ← NUEVO
}

SENSOR_PARAMS = {
    # ... parámetros existentes ...

    "Supertrend": {
        "atr_period": 10,      # Periodo ATR
        "multiplier": 3.0,     # Multiplicador (2-4 típico)
    },
}
```

**Cuándo señala:**
- LONG: Flip de downtrend → uptrend
- SHORT: Flip de uptrend → downtrend

**Nota:** Solo señala en CAMBIOS de tendencia (no continuación).

---

### **3. ADXFilter** 📊
Filtra sideways markets. Puede generar señales o solo filtrar.

```python
ACTIVE_SENSORS = {
    # ... sensores existentes ...
    "ADXFilter": True,  # ← NUEVO
}

SENSOR_PARAMS = {
    # ... parámetros existentes ...

    "ADXFilter": {
        "period": 14,              # Periodo DI/ADX
        "adx_threshold": 25.0,     # Mínimo para considerar tendencia
        "use_directional": True,   # True = genera señales, False = solo filtra
    },
}
```

**Modos:**

**A) Modo Señal (`use_directional=True`):**
- LONG: ADX > 25 y DI+ > DI-
- SHORT: ADX > 25 y DI- > DI+
- Nada: ADX < 25 (sideways)

**B) Modo Filtro (`use_directional=False`):**
- No genera señales propias
- Solo valida que ADX > threshold
- Útil para combinar con otros sensores

---

### **4. BollingerSqueeze** 💥
Detecta volatility breakouts después de compresión.

```python
ACTIVE_SENSORS = {
    # ... sensores existentes ...
    "BollingerSqueeze": True,  # ← NUEVO
}

SENSOR_PARAMS = {
    # ... parámetros existentes ...

    "BollingerSqueeze": {
        "period": 20,                # Periodo Bollinger
        "std_dev": 2.0,              # Desviaciones estándar
        "squeeze_threshold": 0.02,   # BBW < 2% = squeeze
        "volume_factor": 1.2,        # Volumen > 1.2x promedio
    },
}
```

**Cuándo señala:**
1. Detecta squeeze (BBW < 0.02)
2. Espera breakout (precio fuera de bandas)
3. Confirma con volumen (> 1.2x promedio)
4. LONG/SHORT según dirección del breakout

**Nota:** Señal MUY fuerte (`range_score=3`).

---

## 📝 Configuración Completa Ejemplo

```python
# config.py

# ============================================
# SENSORES ACTIVOS (v0.2.0 - 10 sensores)
# ============================================

ACTIVE_SENSORS = {
    # Mean Reversion (5)
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "StochasticReversion": True,      # ← NUEVO
    "BollingerSqueeze": True,         # ← NUEVO

    # Momentum / Trend (4)
    "EMACrossover": True,
    "MACDCrossover": True,
    "Supertrend": True,               # ← NUEVO
    "ADXFilter": True,                # ← NUEVO

    # Volume (1)
    "OBVBreakout": True,
}

# ============================================
# PARÁMETROS POR SENSOR
# ============================================

SENSOR_PARAMS = {
    # --- MEAN REVERSION ---

    "RSIReversion": {
        "period": 2,
        "low": 10.0,
        "high": 90.0,
    },

    "BollingerTouch": {
        "period": 20,
        "std_dev": 2.0,
    },

    "KeltnerReversion": {
        "ema_period": 20,
        "atr_period": 10,
        "atr_multiplier": 1.5,
    },

    "StochasticReversion": {  # ← NUEVO
        "k_period": 14,
        "d_period": 3,
        "low_threshold": 20.0,
        "high_threshold": 80.0,
    },

    "BollingerSqueeze": {     # ← NUEVO
        "period": 20,
        "std_dev": 2.0,
        "squeeze_threshold": 0.02,
        "volume_factor": 1.2,
    },

    # --- MOMENTUM / TREND ---

    "EMACrossover": {
        "fast_period": 9,
        "slow_period": 21,
    },

    "MACDCrossover": {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
    },

    "Supertrend": {           # ← NUEVO
        "atr_period": 10,
        "multiplier": 3.0,
    },

    "ADXFilter": {            # ← NUEVO
        "period": 14,
        "adx_threshold": 25.0,
        "use_directional": True,
    },

    # --- VOLUME ---

    "OBVBreakout": {
        "period": 20,
        "threshold": 1.5,
    },
}
```

---

## 🎯 Recomendaciones de Uso

### **Para Empezar (Conservador)**
Activa solo los 4 nuevos:

```python
ACTIVE_SENSORS = {
    # Antiguos desactivados temporalmente
    "RSIReversion": False,
    "BollingerTouch": False,
    "KeltnerReversion": False,
    "EMACrossover": False,
    "MACDCrossover": False,
    "OBVBreakout": False,

    # Solo nuevos (testing)
    "StochasticReversion": True,
    "Supertrend": True,
    "ADXFilter": True,
    "BollingerSqueeze": True,
}
```

**Ventajas:**
- Fácil identificar comportamiento de nuevos sensores
- Menos señales = más fácil de analizar
- Testing aislado

---

### **Para Producción (Agresivo)**
Activa todos (10 sensores):

```python
ACTIVE_SENSORS = {
    # Todos activos
    "RSIReversion": True,
    "BollingerTouch": True,
    "KeltnerReversion": True,
    "StochasticReversion": True,
    "BollingerSqueeze": True,
    "EMACrossover": True,
    "MACDCrossover": True,
    "Supertrend": True,
    "ADXFilter": True,
    "OBVBreakout": True,
}
```

**Ventajas:**
- Máxima cobertura de contextos
- Más señales = más trades
- Diversificación de estrategias

**Desventajas:**
- Más ruido potencial
- Conflictos entre sensores
- Requiere más datos para entrenar

---

### **Híbrido (Recomendado)**
Mean Reversion + Momentum fuerte:

```python
ACTIVE_SENSORS = {
    # Mean Reversion: mejores
    "RSIReversion": True,
    "StochasticReversion": True,      # Complementa RSI
    "BollingerSqueeze": True,         # Breakouts fuertes

    # Momentum: robustos
    "Supertrend": True,               # Tendencia clara
    "ADXFilter": True,                # Filtra sideways

    # Desactivados (menos útiles)
    "BollingerTouch": False,
    "KeltnerReversion": False,
    "EMACrossover": False,
    "MACDCrossover": False,
    "OBVBreakout": False,
}
```

---

## 🧪 Testing de Nuevos Sensores

### **1. Test Unitario**

```bash
# Crear test simple
python -c "
from sensors.mean_reversion import StochasticReversion

sensor = StochasticReversion()
candle = {
    'timestamp': '2024-01-01T00:00:00',
    'symbol': 'BTCUSDT',
    'timeframe': '15m',
    'high': 42100,
    'low': 41900,
    'close': 42000,
    'volume': 100
}

signal = sensor.check_signal(candle)
print('Signal:', signal)
"
```

### **2. Backtest con Solo Nuevos Sensores**

```bash
# Configurar config.py con solo nuevos sensores
# Ejecutar backtest
python main.py
```

### **3. Comparar Antes/Después**

```bash
# Backtest con sensores antiguos
python main.py > results_old.txt

# Cambiar config: activar nuevos sensores
# Backtest con nuevos sensores
python main.py > results_new.txt

# Comparar
diff results_old.txt results_new.txt
```

---

## 📊 Métricas Esperadas

Con los 4 nuevos sensores:

| Métrica | Antes (6 sensores) | Después (10 sensores) |
|---------|-------------------|----------------------|
| **Señales/día** | 5-8 | 12-20 |
| **GHOST %** | 70-80% | 40-60% (mejorar con datos) |
| **Estrategias aprobadas** | 2-3 | 6-8 |
| **Winrate** | 52-55% | 54-57% (esperado) |

---

## ⚠️ Troubleshooting

### Sensor no genera señales

**Causa:** Parámetros muy estrictos

**Solución:**
```python
# Ejemplo: Stochastic muy estricto
"StochasticReversion": {
    "low_threshold": 30.0,   # Menos estricto (antes 20)
    "high_threshold": 70.0,  # Menos estricto (antes 80)
}
```

### Demasiadas señales

**Causa:** Sensores muy agresivos

**Solución:**
```python
# Usar ADXFilter para filtrar
"ADXFilter": {
    "adx_threshold": 30.0,  # Más estricto (antes 25)
}
```

### Memoria sin entrenar

**Causa:** Pocos datos históricos

**Solución:**
```bash
# Descargar más datos
python utils/download_kline_dataset.py --limit 50000
```

---

## 🚀 Próximos Pasos

1. ✅ Implementar los 4 sensores (DONE)
2. ⬜ Configurar en `config.py`
3. ⬜ Backtest inicial (datos pequeños)
4. ⬜ Ajustar parámetros
5. ⬜ Backtest masivo (6-12 meses)
6. ⬜ Entrenar memoria
7. ⬜ Producción

---

**¿Listo para probar? Edita `config.py` y ejecuta `python main.py`** 🎯
