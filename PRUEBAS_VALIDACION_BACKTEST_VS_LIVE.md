# 🎯 ROADMAP v1.9.3 - Testing & Validation

**Versión:** 1.9.3
**Nombre:** Testing & Validation
**Fecha Inicio:** 2025-11-05
**Objetivo:** Validar que la lógica del bot funciona idénticamente en backtest y testing/live modes

---

## 🎯 OBJETIVOS PRINCIPALES

### 1. **Validar Lógica del Bot** ✅
- La misma lógica (Paroli, Gemini, Sensores) se ejecuta idénticamente en ambos modos
- Progresión Paroli 1x→4x→8x funciona correctamente
- TP/SL se respetan (simulados en backtest, reales en testing/live)

### 2. **Confirmar Datos Reales en Testing/Live** ✅
- TODO viene del exchange real (precios, balance, posiciones, órdenes)
- NUNCA se simula nada en testing/live mode
- TP/SL ejecutados por el exchange, no por el bot

### 3. **Backtest Realista y Confiable** ✅
- Backtest tan realista que podamos confiar en él
- Resultados comparables con testing/live (±5-10% por slippage/fees)
- Base sólida para validar estrategias futuras

---

## 🔄 METODOLOGÍA: TESTING POR RONDAS

```
RONDA N:
├─ 1. Testing Mode (60 velas 1m) → Resultados A
├─ 2. Descargar CSV del mismo período
├─ 3. Backtest Mode (mismo CSV) → Resultados B
├─ 4. Comparar A vs B
├─ 5. Analizar diferencias
├─ 6. Diseñar soluciones
├─ 7. Implementar correcciones
└─ 8. Repetir hasta brecha aceptable
```

---

## 📋 FASES DEL ROADMAP

### **FASE 1: PREPARACIÓN** 🛠️

#### 1.1 Crear Herramientas de Testing
- [ ] **Script:** `utils/download_ohlcv.py`
  - Descarga OHLCV de Kraken del período exacto
  - Input: timestamp inicio/fin o last-n-candles
  - Output: CSV compatible con backtest

- [ ] **Script:** `utils/compare_results.py`
  - Parsea logs de testing y backtest
  - Compara métricas clave
  - Genera reporte de diferencias

- [ ] **Script:** `utils/test_round.sh` (opcional)
  - Automatiza ronda completa
  - Ejecuta: testing → download → backtest → compare

#### 1.2 Documentar Baseline
- [ ] Estado actual del sistema
- [ ] Configuración de testing
- [ ] Parámetros de Paroli
- [ ] TP/SL configurados

---

### **FASE 2: RONDA 1 - TESTING INICIAL** 🧪

#### 2.1 Testing Mode
- [ ] **Comando:**
  ```bash
  python main.py --mode=testing --player=paroli \
      --symbol=BTC/USD --interval=1m --max-candles=60 \
      2>&1 | tee logs/round1_testing.log
  ```
- [ ] **Capturar:**
  - Balance inicial/final
  - Número de señales
  - Número de órdenes
  - Progresión Paroli (steps)
  - Wins/Losses
  - Timestamp inicio/fin

#### 2.2 Descargar Dataset
- [ ] **Comando:**
  ```bash
  python utils/download_ohlcv.py \
      --symbol=BTC/USD --interval=1m \
      --start=<timestamp_inicio> --end=<timestamp_fin> \
      --output=data/round1_comparison.csv
  ```
- [ ] **Verificar:**
  - 60 velas exactas
  - Timestamps coinciden
  - Precios OHLC correctos

#### 2.3 Backtest Mode
- [ ] **Comando:**
  ```bash
  python main.py --mode=backtest --player=paroli \
      --csv=data/round1_comparison.csv \
      2>&1 | tee logs/round1_backtest.log
  ```
- [ ] **Capturar:**
  - Balance inicial/final
  - Número de señales
  - Número de órdenes
  - Progresión Paroli (steps)
  - Wins/Losses

#### 2.4 Comparación y Análisis
- [ ] **Comando:**
  ```bash
  python utils/compare_results.py \
      --testing=logs/round1_testing.log \
      --backtest=logs/round1_backtest.log \
      --output=reports/round1_comparison.md
  ```
- [ ] **Analizar:**
  - ¿Mismo número de señales?
  - ¿Mismo número de órdenes?
  - ¿Misma progresión Paroli?
  - ¿Balance final similar (±10%)?
  - ¿Wins/Losses coinciden?

#### 2.5 Diagnóstico
- [ ] **Identificar diferencias críticas:**
  - Si señales difieren → Problema en sensores
  - Si órdenes difieren → Problema en BuildOrderStage
  - Si steps difieren → Problema en handle_trade_outcome
  - Si balance difiere >10% → Problema en TP/SL o fees

#### 2.6 Diseño de Soluciones
- [ ] **Documentar causas raíz**
- [ ] **Proponer correcciones específicas**
- [ ] **Priorizar fixes críticos**

#### 2.7 Implementación
- [ ] **Aplicar correcciones**
- [ ] **Commit con mensaje descriptivo**
- [ ] **Preparar para Ronda 2**

---

### **FASE 3: RONDA 2 - VALIDACIÓN DE CORRECCIONES** 🔄

#### 3.1 Testing Mode (con correcciones)
- [ ] Ejecutar mismo test que Ronda 1
- [ ] Nuevo período de 60 velas

#### 3.2 Descargar Dataset
- [ ] Descargar CSV del nuevo período

#### 3.3 Backtest Mode
- [ ] Ejecutar backtest con nuevo CSV

#### 3.4 Comparación y Análisis
- [ ] Comparar resultados
- [ ] Verificar que correcciones funcionaron
- [ ] Medir reducción de brecha

#### 3.5 Decisión
- [ ] **SI brecha ≤10%:** → Continuar a Fase 4
- [ ] **SI brecha >10%:** → Ronda 3 (repetir Fase 3)

---

### **FASE 4: RONDA N** (si es necesario) 🔁

- [ ] Repetir ciclo de Fase 3
- [ ] Aplicar nuevas correcciones
- [ ] Continuar hasta brecha aceptable

---

### **FASE 5: VALIDACIÓN FINAL** ✅

#### 5.1 Test Largo - Testing Mode
- [ ] **Comando:**
  ```bash
  python main.py --mode=testing --player=paroli \
      --symbol=BTC/USD --interval=1m --max-candles=200 \
      2>&1 | tee logs/final_testing.log
  ```
- [ ] Capturar resultados completos

#### 5.2 Test Largo - Backtest Mode
- [ ] Descargar CSV de las 200 velas
- [ ] Ejecutar backtest con mismo dataset
- [ ] Capturar resultados completos

#### 5.3 Comparación Final
- [ ] Generar reporte completo
- [ ] Validar brecha ≤10%
- [ ] Documentar hallazgos

#### 5.4 Documentación
- [ ] Crear `TESTING_RESULTS_v1.9.3.md`
- [ ] Documentar todas las rondas
- [ ] Listar correcciones aplicadas
- [ ] Conclusiones y recomendaciones

#### 5.5 Release
- [ ] Actualizar CHANGELOG
- [ ] Commit final
- [ ] Tag v1.9.3
- [ ] Push a GitHub

---

## 📊 MÉTRICAS DE ÉXITO

### **Métricas Críticas (deben coincidir 100%):**
- ✅ Número de señales detectadas
- ✅ Número de órdenes ejecutadas
- ✅ Sides de las órdenes (LONG/SHORT)
- ✅ Progresión Paroli (steps: 0→1→2→0)

### **Métricas Tolerables (±5-10%):**
- ⚠️ Balance final (por slippage/fees reales)
- ⚠️ PnL exacto
- ⚠️ Entry/Exit prices exactos

### **Criterio de Brecha Aceptable:**
```
Balance final: ±10% máximo
Trades ejecutados: ±1 trade máximo
Steps de Paroli: Idénticos
Wins/Losses: Idénticos (si hay cierres)
```

---

## 🚨 REGLAS DE DEBUGGING

### **Si Paroli NO apuesta, verificar:**
1. ✅ ¿Los sensores detectaron señales?
2. ✅ ¿Las señales tienen side (LONG/SHORT)?
3. ✅ ¿Hay equity disponible?
4. ✅ ¿Ya hay posición abierta (max positions)?

### **NUNCA culpar a:**
- ❌ Gemini no entrenado
- ❌ Falta de datos en buckets
- ❌ Gemini dice GHOST
- ❌ Confidence baja

**Paroli IGNORA todo eso. Si hay side, apuesta.**

---

## 🛠️ HERRAMIENTAS CREADAS

### 1. `utils/download_ohlcv.py`
```
Descarga OHLCV de Kraken del período exacto
Input: --symbol, --interval, --start, --end (o --last-n-candles)
Output: CSV compatible con backtest
```

### 2. `utils/compare_results.py`
```
Compara logs de testing vs backtest
Input: --testing, --backtest
Output: Reporte markdown con diferencias
```

### 3. `utils/test_round.sh` (opcional)
```
Automatiza ronda completa
Ejecuta: testing → download → backtest → compare
```

---

## 📁 ESTRUCTURA DE ARCHIVOS

```
Casino-V2/
├── logs/
│   ├── round1_testing.log
│   ├── round1_backtest.log
│   ├── round2_testing.log
│   ├── round2_backtest.log
│   └── final_testing.log
├── data/
│   ├── round1_comparison.csv
│   ├── round2_comparison.csv
│   └── final_comparison.csv
├── reports/
│   ├── round1_comparison.md
│   ├── round2_comparison.md
│   └── final_comparison.md
└── utils/
    ├── download_ohlcv.py
    ├── compare_results.py
    └── test_round.sh
```

---

## 📝 NOTAS IMPORTANTES

### **Sobre Paroli:**
- Solo validamos con Paroli en esta versión
- Paroli apuesta SIEMPRE que hay side
- Ignora buckets, training, confidence de Gemini
- Perfecto para testing agresivo

### **Sobre los Datos:**
- Testing/Live: NUNCA simula, TODO del exchange
- Backtest: Simula TP/SL con high/low de velas
- Diferencias esperadas por slippage/fees reales

### **Sobre las Rondas:**
- Cada ronda es independiente (nuevo período)
- Iteramos hasta cerrar brecha
- No hay límite de rondas (hasta lograr objetivo)

---

## 🎯 CRITERIO DE FINALIZACIÓN

La versión 1.9.3 se considera **COMPLETA** cuando:

1. ✅ Brecha entre testing y backtest ≤10%
2. ✅ Progresión Paroli funciona idénticamente
3. ✅ TP/SL se ejecutan correctamente en ambos modos
4. ✅ Documentación completa de resultados
5. ✅ Confianza en backtest para validar estrategias futuras

---

## 🚀 PRÓXIMOS PASOS (POST v1.9.3)

- **v1.9.4:** Validar otros players (Kelly, Martingale)
- **v1.9.5:** Validar múltiples timeframes (5m, 15m, 1h)
- **v2.0:** Multi-asset expansion

---

**Última Actualización:** 2025-11-05
**Estado:** 🟡 En Progreso
**Fase Actual:** Fase 1 - Preparación
