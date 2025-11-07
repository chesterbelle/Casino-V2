# Plan de Validación: Backtesting vs Testing en Vivo

## 🎯 Objetivo

Validar que **main.py con Player Paroli** produce los mismos resultados cuando se ejecuta en:
- **Modo Testing** (live testnet con Kraken)
- **Modo Backtesting** (con los mismos datos históricos)

Esto asegura que el sistema de backtesting es confiable y produce resultados consistentes con el trading en vivo.

---

## 📋 Metodología

### Fase 1: Ejecución en Modo Testing (Live Testnet)
```bash
python main.py --mode=testing --player=paroli --symbol=BTC/USD:USD --interval=1m --max-candles=60
```

**Qué hace:**
1. Conecta a Kraken Futures testnet
2. Obtiene balance inicial automáticamente
3. Ejecuta Player Paroli durante 60 velas de 1 minuto
4. Registra todas las operaciones y resultados en logs
5. Guarda estado final

**Duración:** 60 minutos (1 hora)

### Fase 2: Descarga y Preparación de Datos
```bash
python tests/validation/download_historical_data.py \
    --start "2024-11-06T20:00:00Z" \
    --end "2024-11-06T21:00:00Z" \
    --output data/validation/BTC_USD_60candles.csv
```

**Qué hace:**
1. Descarga datos OHLCV de Kraken para el período exacto
2. Valida que los datos coinciden con los usados en testing
3. Guarda en formato CSV para backtesting

**Duración:** 1-2 minutos

### Fase 3: Ejecución en Modo Backtesting
```bash
python main.py --mode=backtest --player=paroli --data=data/validation/BTC_USD_60candles.csv --max-candles=60
```

**Qué hace:**
1. Carga datos históricos descargados
2. Usa mismo balance inicial que testing (configurado en system.py)
3. Ejecuta Player Paroli con los mismos datos
4. Registra todas las operaciones y resultados en logs

**Duración:** Segundos (backtesting es instantáneo)

### Fase 4: Comparación de Resultados
```bash
python tests/validation/compare_results.py \
    --testing-log logs/testing_20241106_2000.log \
    --backtest-log logs/backtest_20241106_2100.log
```

**Qué hace:**
1. Parsea logs de ambos modos
2. Compara órdenes ejecutadas (cantidad, precio, timing)
3. Compara balance final
4. Compara métricas de rendimiento
5. Genera reporte de diferencias

**Duración:** Segundos

---

## 🛠️ Herramientas a Desarrollar

### 1. Script de Testing en Vivo con Logging
**Archivo:** `test_live_60_candles.py`

**Funcionalidad:**
- Conecta a Kraken testnet
- Registra balance inicial
- Ejecuta estrategia durante 60 velas de 1m
- Guarda log detallado de:
  - Cada vela recibida (OHLCV)
  - Cada señal generada
  - Cada orden ejecutada
  - Balance después de cada operación
  - Timestamp de cada evento
- Guarda datos en formato JSON para comparación

**Output:**
```json
{
  "test_info": {
    "exchange": "kraken",
    "symbol": "BTC/USD:USD",
    "timeframe": "1m",
    "start_time": "2024-11-06T20:00:00Z",
    "end_time": "2024-11-06T21:00:00Z",
    "initial_balance": 10000.0,
    "final_balance": 10150.0
  },
  "candles": [
    {
      "timestamp": 1699300800000,
      "open": 101000.0,
      "high": 101100.0,
      "low": 100900.0,
      "close": 101050.0,
      "volume": 1234.56
    }
  ],
  "signals": [
    {
      "timestamp": 1699300860000,
      "candle_index": 5,
      "signal": "LONG",
      "confidence": 0.85,
      "indicators": {...}
    }
  ],
  "orders": [
    {
      "timestamp": 1699300861000,
      "candle_index": 5,
      "order_id": "abc123",
      "side": "buy",
      "amount": 0.001,
      "entry_price": 101050.0,
      "tp_price": 101555.25,
      "sl_price": 100746.97,
      "status": "filled"
    }
  ],
  "balance_history": [
    {
      "timestamp": 1699300800000,
      "candle_index": 0,
      "balance": 10000.0
    }
  ]
}
```

---

### 2. Script de Descarga de Datos Históricos
**Archivo:** `download_historical_data.py`

**Funcionalidad:**
- Descarga datos OHLCV de Kraken para el período exacto
- Valida que los datos coinciden con los del testing
- Guarda en formato compatible con backtesting

**Validaciones:**
- Número de velas = 60
- Timestamps coinciden
- Precios OHLCV coinciden (±0.01% tolerancia por slippage)

---

### 3. Script de Backtesting con Logging
**Archivo:** `test_backtest_60_candles.py`

**Funcionalidad:**
- Carga datos históricos descargados
- Configura mismo balance inicial que testing
- Ejecuta misma estrategia
- Guarda log en mismo formato que testing

**Output:** Mismo formato JSON que el testing en vivo

---

### 4. Script de Comparación
**Archivo:** `compare_testing_vs_backtest.py`

**Funcionalidad:**
- Carga ambos archivos JSON
- Compara métricas clave:
  - Balance inicial/final
  - Número de operaciones
  - Precios de entrada/salida
  - Timing de señales
  - PnL por operación
  - Métricas de rendimiento
- Genera reporte de diferencias

**Output:**
```
================================================================================
COMPARACIÓN: Testing vs Backtesting
================================================================================

📊 DATOS GENERALES:
  Testing:
    - Período: 2024-11-06 20:00:00 - 21:00:00
    - Velas: 60
    - Balance inicial: $10,000.00
    - Balance final: $10,150.00

  Backtesting:
    - Período: 2024-11-06 20:00:00 - 21:00:00
    - Velas: 60
    - Balance inicial: $10,000.00
    - Balance final: $10,145.00

📈 OPERACIONES:
  Testing: 5 operaciones
  Backtesting: 5 operaciones
  ✅ Coinciden

📊 COMPARACIÓN OPERACIÓN POR OPERACIÓN:
  Operación #1:
    Testing:    LONG @ $101,050 | TP: $101,555 | SL: $100,747
    Backtesting: LONG @ $101,050 | TP: $101,555 | SL: $100,747
    ✅ Coinciden

  Operación #2:
    Testing:    SHORT @ $101,200 | Exit: $101,100 | PnL: +$0.10
    Backtesting: SHORT @ $101,200 | Exit: $101,105 | PnL: +$0.095
    ⚠️  Diferencia en exit price: $5 (slippage)

💰 BALANCE FINAL:
  Testing:    $10,150.00
  Backtesting: $10,145.00
  Diferencia: -$5.00 (-0.05%)
  ✅ Dentro de tolerancia (±0.1%)

📊 MÉTRICAS:
  Win Rate:
    Testing:    60% (3/5)
    Backtesting: 60% (3/5)
    ✅ Coinciden

  Avg PnL:
    Testing:    $30.00
    Backtesting: $29.00
    Diferencia: -$1.00 (-3.3%)

🎯 RESULTADO FINAL: ✅ VALIDACIÓN EXITOSA
  - Diferencias dentro de tolerancia esperada
  - Slippage y fees explican discrepancias menores
```

---

## 📝 Configuración de la Prueba

### Parámetros Comunes
```python
COMMON_CONFIG = {
    "exchange": "kraken",
    "symbol": "BTC/USD:USD",
    "timeframe": "1m",
    "num_candles": 60,
    "initial_balance": 10000.0,  # USD
    "strategy": "SimpleMovingAverageCrossover",  # O la estrategia que uses
    "strategy_params": {
        "fast_period": 5,
        "slow_period": 20,
        "tp_percent": 0.005,  # 0.5%
        "sl_percent": 0.003,  # 0.3%
    }
}
```

### Tolerancias Aceptables
```python
TOLERANCES = {
    "price_difference": 0.001,  # 0.1% - Para diferencias de precio por slippage
    "balance_difference": 0.001,  # 0.1% - Para diferencias de balance final
    "timing_difference": 5,  # 5 segundos - Para diferencias de timing
}
```

---

## 🔄 Flujo de Ejecución

### Paso 1: Testing en Vivo
```bash
# Ejecutar testing en vivo durante 60 velas
python test_live_60_candles.py --exchange kraken --symbol "BTC/USD:USD" --timeframe 1m --candles 60

# Output: test_live_results_20241106_2000.json
```

### Paso 2: Descargar Datos Históricos
```bash
# Descargar datos del mismo período
python download_historical_data.py --exchange kraken --symbol "BTC/USD:USD" --timeframe 1m --start "2024-11-06T20:00:00Z" --end "2024-11-06T21:00:00Z"

# Output: historical_data_20241106_2000.json
```

### Paso 3: Ejecutar Backtesting
```bash
# Ejecutar backtesting con los datos descargados
python test_backtest_60_candles.py --data historical_data_20241106_2000.json --initial-balance 10000

# Output: test_backtest_results_20241106_2000.json
```

### Paso 4: Comparar Resultados
```bash
# Comparar ambos resultados
python compare_testing_vs_backtest.py --live test_live_results_20241106_2000.json --backtest test_backtest_results_20241106_2000.json

# Output: comparison_report_20241106_2000.txt
```

---

## 📊 Métricas a Comparar

### 1. Métricas de Operaciones
- ✅ Número total de operaciones
- ✅ Timing de cada operación (timestamp)
- ✅ Precio de entrada de cada operación
- ✅ Precio de salida de cada operación
- ✅ TP/SL configurados
- ✅ Razón de cierre (TP, SL, manual)
- ✅ PnL por operación

### 2. Métricas de Balance
- ✅ Balance inicial
- ✅ Balance después de cada operación
- ✅ Balance final
- ✅ Drawdown máximo
- ✅ Peak balance

### 3. Métricas de Rendimiento
- ✅ Win rate
- ✅ Profit factor
- ✅ Sharpe ratio
- ✅ Max drawdown %
- ✅ Total return %

### 4. Métricas de Señales
- ✅ Número de señales generadas
- ✅ Timing de cada señal
- ✅ Indicadores en cada señal
- ✅ Señales ejecutadas vs ignoradas

---

## ⚠️ Diferencias Esperadas (Tolerables)

### 1. Slippage
- **Testing:** Puede haber slippage real en ejecución
- **Backtesting:** Usa precio de cierre de vela
- **Tolerancia:** ±0.1% en precio de ejecución

### 2. Timing
- **Testing:** Ejecución puede tomar algunos segundos
- **Backtesting:** Ejecución instantánea
- **Tolerancia:** ±5 segundos en timestamps

### 3. Fees
- **Testing:** Fees reales del exchange
- **Backtesting:** Fees simulados (deben ser iguales)
- **Tolerancia:** Deben coincidir exactamente

### 4. Datos de Mercado
- **Testing:** Datos en tiempo real (pueden tener pequeñas variaciones)
- **Backtesting:** Datos históricos descargados
- **Tolerancia:** ±0.01% en precios OHLCV

---

## 🚨 Diferencias Inaceptables (Bugs)

### 1. Lógica de Estrategia
- ❌ Señales diferentes con mismos datos
- ❌ Indicadores calculados diferente
- ❌ Condiciones de entrada/salida diferentes

### 2. Gestión de Balance
- ❌ Balance inicial diferente
- ❌ Cálculo de PnL diferente
- ❌ Gestión de fees diferente

### 3. Ejecución de Órdenes
- ❌ Órdenes no ejecutadas en backtesting
- ❌ TP/SL no respetados
- ❌ Lógica de cierre diferente

---

## 📁 Estructura de Archivos

```
Casino-V2/
├── tests/
│   ├── validation/
│   │   ├── test_live_60_candles.py          # Testing en vivo
│   │   ├── download_historical_data.py       # Descarga de datos
│   │   ├── test_backtest_60_candles.py       # Backtesting
│   │   ├── compare_testing_vs_backtest.py    # Comparación
│   │   └── validation_config.py              # Configuración común
│   └── validation_results/
│       ├── test_live_results_*.json          # Resultados testing
│       ├── historical_data_*.json            # Datos históricos
│       ├── test_backtest_results_*.json      # Resultados backtesting
│       └── comparison_report_*.txt           # Reportes de comparación
└── docs/
    └── PLAN_VALIDACION_BACKTESTING.md        # Este documento
```

---

## ✅ Criterios de Éxito

La validación será **EXITOSA** si:

1. ✅ Número de operaciones coincide (±0)
2. ✅ Balance final difiere menos de 0.1%
3. ✅ Win rate coincide exactamente
4. ✅ Precios de entrada difieren menos de 0.1%
5. ✅ Timing de señales difiere menos de 5 segundos
6. ✅ PnL total difiere menos de 0.1%
7. ✅ Todas las señales se generan en los mismos momentos

---

## 🔧 Implementación

### Orden de Desarrollo

1. **Fase 1:** Crear `validation_config.py` con configuración común
2. **Fase 2:** Crear `test_live_60_candles.py` para testing en vivo
3. **Fase 3:** Crear `download_historical_data.py` para descarga de datos
4. **Fase 4:** Crear `test_backtest_60_candles.py` para backtesting
5. **Fase 5:** Crear `compare_testing_vs_backtest.py` para comparación
6. **Fase 6:** Ejecutar prueba completa y analizar resultados
7. **Fase 7:** Documentar hallazgos y ajustar si es necesario

---

## 📅 Estimación de Tiempo

- **Desarrollo de scripts:** 4-6 horas
- **Ejecución de prueba:** 1 hora (60 velas de 1m)
- **Análisis de resultados:** 1-2 horas
- **Ajustes si es necesario:** 2-4 horas
- **Total:** 8-13 horas

---

## 🎯 Próximos Pasos

1. ✅ Revisar y aprobar este plan
2. ⏳ Crear estructura de carpetas
3. ⏳ Implementar `validation_config.py`
4. ⏳ Implementar `test_live_60_candles.py`
5. ⏳ Implementar `download_historical_data.py`
6. ⏳ Implementar `test_backtest_60_candles.py`
7. ⏳ Implementar `compare_testing_vs_backtest.py`
8. ⏳ Ejecutar prueba completa
9. ⏳ Analizar resultados y documentar

---

## 📝 Notas Adicionales

- Los scripts deben ser reutilizables para futuras validaciones
- Considerar agregar más períodos de prueba (120 velas, 240 velas, etc.)
- Considerar probar con diferentes estrategias
- Considerar probar con diferentes timeframes (5m, 15m, 1h)
- Los resultados deben guardarse para referencia futura
