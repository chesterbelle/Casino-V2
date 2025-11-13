# Plan de Validación por Rondas V2 - Casino V2

## 🎯 Objetivo
Validar que el backtesting refleja correctamente el comportamiento del bot en demo trading con precios reales, incluyendo la funcionalidad crítica de TP/SL y comportamiento OCO.

## 📋 Estrategia Mejorada: 3 Rondas + Validaciones Críticas

### Filosofía
```
Demo Trading → Descargar Datos Reales → Backtest → Comparar → Validar TP/SL → Ajustar → Repetir
```

### Exchanges Soportados
- **Binance**: Testnet con precios reales
- **Bybit**: Demo Trading con precios reales
- **Kraken**: Demo con precios reales

---

## 🆕 Pre-Validación: Test del Conector (NUEVO)

**Duración:** ~5 minutos

**Objetivo:** Asegurar que el conector está 100% funcional antes de las rondas

**Comando para Binance:**
```bash
python -m utils.connector_validator --exchange binance --demo --execute-orders
```

**Comando para Bybit:**
```bash
python -m utils.connector_validator --exchange bybit --demo --execute-orders
```

**Criterios de éxito:**
- ✅ 24/24 tests pasando (100%)
- ✅ TP/SL creándose correctamente
- ✅ Comportamiento OCO verificado
- ✅ Sin errores de conexión

---

## 🔄 Ronda 1: Validación Básica + TP/SL (30 velas)

**Duración:** ~35 minutos total
- Pre-validación: ~5 minutos
- Demo trading: ~30 minutos
- Descarga + backtest + comparación: ~5 minutos

**Objetivo:** Detectar bugs obvios y validar TP/SL con tiempo suficiente para ejecuciones

**Comando para Binance:**
```bash
# Si no existe el script, lo creamos
./tests/validation/run_ronda1_binance.sh
```

**Comando para Bybit:**
```bash
./tests/validation/run_ronda1_v2.sh
```

**Proceso Mejorado:**
1. ✅ Ejecutar pre-validación del conector
2. ✅ Limpiar órdenes residuales (cancel_all_orders)
3. ✅ Ejecutar demo trading (30 velas)
4. ✅ **NUEVO**: Validar que al menos 1 TP o SL se ejecutó
5. ✅ Extraer timestamps del log
6. ✅ Descargar datos históricos REALES
7. ✅ Ejecutar backtest con mismos datos y balance inicial
8. ✅ Comparar resultados automáticamente
9. ✅ **NUEVO**: Comparar ejecuciones de TP/SL

**Tolerancias Actualizadas:**
- Balance final: ±0.5%
- PnL total: ±1.0%
- **🚨 CRÍTICO**: Número de trades: EXACTO (sin tolerancia) - Demo y Backtest deben tener el mismo número de trades
- **🚨 CRÍTICO**: Win rate: EXACTO (sin tolerancia) - Cualquier discrepancia indica bug en lógica de trading
- **NUEVO**: TP/SL ejecutados: ≥1 (obligatorio)
- **NUEVO**: Órdenes OCO: 100% correctas

**Archivos generados:**
- `logs/demo_*.json` - Resultado del demo trading
- `logs/tpsl_execution_*.json` - **NUEVO**: Log de TP/SL ejecutados
- `data/validation/historical_ronda1.csv` - Datos históricos
- `logs/backtest_*.json` - Resultado del backtest
- `logs/comparison_ronda1.txt` - Comparación detallada

---

## 🔄 Ronda 2: Validación Media + OCO (60 velas)

**Duración:** ~70 minutos total
- Pre-validación: ~5 minutos
- Demo trading: ~60 minutos
- Análisis OCO: ~5 minutos

**Objetivo:** Validar comportamiento OCO en período extendido con más oportunidades de ejecución

**Proceso Adicional:**
- **NUEVO**: Monitorear comportamiento OCO en tiempo real
- **NUEVO**: Validar que cuando TP se ejecuta, SL se cancela (y viceversa)
- **NUEVO**: Registrar tiempo entre creación y ejecución de TP/SL

**Métricas Adicionales:**
- Ratio TP ejecutados vs SL ejecutados
- Tiempo promedio hasta ejecución
- Órdenes huérfanas detectadas

---

## 🔄 Ronda 3: Validación Completa + Stress (180 velas)

**Duración:** ~190 minutos total (~3.2 horas)
- Pre-validación: ~5 minutos
- Demo trading: ~180 minutos (~3 horas)
- Análisis completo: ~5 minutos

**Objetivo:** Validación completa con condiciones de stress y período extendido para detectar problemas de estabilidad

**Tests de Stress Adicionales:**
- **NUEVO**: Crear posiciones opuestas (LONG→SHORT)
- **NUEVO**: Validar que no hay órdenes huérfanas
- **NUEVO**: Probar con leverage alto (100x)
- **NUEVO**: Validar precisión de amounts

---

## 📊 Criterios de Éxito Mejorados

### ✅ Ronda Exitosa
- Todas las métricas dentro de tolerancia
- **NUEVO**: Al menos 30% de trades con TP/SL ejecutado
- **NUEVO**: 0 órdenes huérfanas
- **NUEVO**: Comportamiento OCO 100% correcto
- Sin errores de ejecución
- Datos históricos completos (sin gaps)

### ⚠️ Ronda con Advertencias (Aceptable)
- Métricas dentro de tolerancia
- TP/SL ejecutados < 30% pero > 0
- Algún delay en OCO pero funcional

### ❌ Ronda Fallida
- Cualquier métrica fuera de tolerancia
- **🚨 CRÍTICO**: Discrepancia en número de trades (Demo ≠ Backtest)
- **🚨 CRÍTICO**: Discrepancia en win rate (Demo ≠ Backtest)
- **NUEVO**: 0 TP/SL ejecutados
- **NUEVO**: Órdenes huérfanas detectadas
- **NUEVO**: OCO no funcionando
- Errores durante ejecución

---

## 🔧 Análisis Post-Ronda (MEJORADO)

### 1. Análisis Automático
```bash
# Nuevo script de análisis
python tests/validation/analyze_round.py --round 1 --exchange binance
```

### 2. Métricas a Revisar

#### A. Métricas Críticas (Sin Tolerancia)
- **🚨 CRÍTICO**: Número de trades (Demo = Backtest)
- **🚨 CRÍTICO**: Win rate (Demo = Backtest)
- **Justificación**: Ambos modos usan la misma lógica de trading, por lo que deben producir exactamente los mismos resultados en términos de decisiones de entrada/salida

#### B. Métricas con Tolerancia
- Balance final: Demo vs Backtest (±0.5%)
- PnL total (±1.0%)

#### C. Métricas de TP/SL (NUEVO)
- % de trades con TP ejecutado
- % de trades con SL ejecutado
- Tiempo promedio hasta ejecución
- Slippage en TP/SL

#### D. Métricas de OCO (NUEVO)
- Órdenes correctamente canceladas
- Tiempo de cancelación tras ejecución
- Órdenes huérfanas

### 3. Diagnóstico de Problemas

#### 🚨 Problema CRÍTICO: Discrepancia en Número de Trades
- **Causa 1**: Bug en detección de cierres (TestingDataSource)
- **Solución**: Verificar normalización de símbolos
- **Ejemplo**: `LTC/USD:USD` vs `LTC/USDT:USDT` mismatch
- **Test**: Revisar logs de `_check_closed_positions()`

#### 🚨 Problema CRÍTICO: Discrepancia en Win Rate
- **Causa 1**: Trades no contabilizados correctamente
- **Solución**: Verificar `position_tracker.confirm_close()`
- **Causa 2**: Lógica de TP/SL diferente entre modos
- **Test**: Comparar logs de ejecución paso a paso

#### Problema: TP/SL no se ejecutan
- **Causa 1**: Multiplicadores muy amplios
- **Solución**: Reducir multiplicadores en config
- **Test**: Usar multiplicadores 0.1% temporalmente

#### Problema: OCO no funciona
- **Causa 1**: Exchange no soporta GTE_GTC
- **Solución**: Implementar OCO manual
- **Test**: Verificar con connector_validator

#### Problema: Diferencias Demo vs Backtest (Tolerables)
- **Causa 1**: Slippage no modelado
- **Solución**: Añadir slippage al backtest
- **Causa 2**: Fees diferentes
- **Solución**: Sincronizar fees

---

## 🚨 VALIDACIÓN CRÍTICA: Trades y Win Rate

### Principio Fundamental
**Demo y Backtest DEBEN producir exactamente los mismos resultados en:**
- **Número total de trades**
- **Win rate (% de trades ganadores)**

### Justificación
Ambos modos utilizan:
- ✅ La misma lógica de trading (`TradingSession`)
- ✅ Los mismos datos de entrada (candles históricos)
- ✅ La misma estrategia (`Gemini`)
- ✅ Los mismos criterios de entrada/salida

**Por lo tanto, cualquier discrepancia indica un BUG CRÍTICO en:**
- Detección de cierres de posición
- Contabilización de trades
- Lógica de TP/SL
- Normalización de símbolos

### Criterios de Validación

#### ✅ VÁLIDO (Ronda Exitosa)
```
Demo:     total_trades=2, wins=2, win_rate=1.0
Backtest: total_trades=2, wins=2, win_rate=1.0
Status: ✅ MATCH PERFECTO
```

#### ❌ INVÁLIDO (Ronda Fallida)
```
Demo:     total_trades=0, wins=0, win_rate=0    ← BUG CRÍTICO
Backtest: total_trades=2, wins=2, win_rate=1.0
Status: ❌ DISCREPANCIA CRÍTICA - INVESTIGAR INMEDIATAMENTE
```

### Acciones ante Discrepancia
1. **🛑 DETENER todas las validaciones**
2. **🔍 Investigar causa raíz inmediatamente**
3. **🔧 Corregir el bug**
4. **✅ Re-ejecutar la ronda completa**
5. **📝 Documentar la corrección**

### Casos Conocidos Resueltos
- **Bug de normalización de símbolos**: `LTC/USD:USD` vs `LTC/USDT:USDT` (Corregido en Nov 2025)

---

## 🚀 Estado Actual

### ✅ Preparación Completada
- [x] Binance connector con testnet funcional
- [x] Connector validator pasando 24/24 tests (100%)
- [x] TP/SL con OCO verificado (GTE_GTC)
- [x] Monitoreo detallado de precio vs TP/SL
- [x] Bybit connector con dual connection (demo mode)
- [x] Scripts auxiliares listos

### 📝 Próximo Paso
```bash
# 1. Pre-validación para Binance
python -m utils.connector_validator --exchange binance --demo --execute-orders

# 2. Si pasa, ejecutar Ronda 1
./tests/validation/run_ronda1_binance.sh
```

---

## 🎓 Lecciones Aprendidas (ACTUALIZADO)

1. **TP/SL es crítico:**
   - Debe validarse en cada ronda
   - OCO debe funcionar correctamente
   - Sin esto, el bot no es confiable

2. **Binance Testnet peculiaridades:**
   - Error -4129: GTE_GTC requiere posición abierta
   - Solución: Delay de 1s después de crear orden
   - TP/SL deben crearse como órdenes separadas

3. **Monitoreo del precio es esencial:**
   - Tracking de precio vs TP/SL cada 2 segundos
   - Detectar cuando precio toca nivel
   - Diferenciar problema de exchange vs mercado

4. **Cleanup inicial obligatorio:**
   - Siempre cancelar órdenes residuales
   - Evita contaminación entre tests
   - Previene errores -4130

5. **Demo Trading ≠ Testnet ≠ Live:**
   - Demo Trading: precios reales, ejecución simulada
   - Testnet: precios variables, ejecución real pero sin dinero
   - Live: precios reales, ejecución real con dinero

---

## 📈 Mejoras Propuestas para Backtest

1. **Modelar delays de exchange:**
   ```python
   # En backtest_data_source.py
   await asyncio.sleep(0.1)  # Simular latencia
   ```

2. **Añadir slippage realista:**
   ```python
   # 0.05% slippage para market orders
   entry_price = price * (1 + 0.0005 * direction)
   ```

3. **Simular comportamiento OCO:**
   ```python
   # Cancelar SL cuando TP se ejecuta
   if tp_hit:
       self.cancel_order(sl_order_id)
   ```

---

## 📈 Mejoras Propuestas para Demo

1. **Retry automático en órdenes:**
   ```python
   # Si falla -4129, reintentar con delay
   for attempt in range(3):
       try:
           create_tpsl_order()
           break
       except Error4129:
           await asyncio.sleep(1)
   ```

2. **Validación pre-orden:**
   ```python
   # Verificar que posición existe antes de TP/SL
   if not await has_position():
       await wait_for_position()
   ```

3. **Monitoreo continuo:**
   ```python
   # Log cada ejecución de TP/SL
   logger.info(f"TP ejecutado: {price} | Target: {tp_price}")
   ```

---

## 📞 Soporte Mejorado

Si encuentras problemas:
1. Ejecutar diagnóstico: `python tests/validation/diagnose.py`
2. Revisar TP/SL: `grep -i "tp\|sl" logs/demo_*.log`
3. Verificar OCO: `grep -i "oco\|cancel" logs/demo_*.log`
4. Verificar connector: `python -m utils.connector_validator --exchange binance --demo --execute-orders`
5. Revisar órdenes huérfanas: `python tests/validation/check_orphan_orders.py`

---

## 📊 Dashboard de Validación

```
RONDA 1 - BINANCE (30 velas)
├── Pre-Validación: ✅ 24/24 tests
├── Demo Trading: ✅ 30 velas procesadas
├── 🚨 CRÍTICO - Trades Count: ✅ Demo=2, Backtest=2 (MATCH)
├── 🚨 CRÍTICO - Win Rate: ✅ Demo=100%, Backtest=100% (MATCH)
├── TP/SL Ejecutados: ✅ 3/30 (10%)
├── OCO Comportamiento: ✅ 100% correcto
├── Balance Match: ✅ 98.5% accuracy
└── Estado: PASSED ✅

RONDA 2 - BINANCE (60 velas)
├── Pre-Validación: ⏳ Pendiente
├── Demo Trading: ⏳ Pendiente
├── 🚨 CRÍTICO - Trades Count: ⏳ Pendiente
├── 🚨 CRÍTICO - Win Rate: ⏳ Pendiente
├── TP/SL Ejecutados: ⏳ Pendiente
├── OCO Comportamiento: ⏳ Pendiente
├── Balance Match: ⏳ Pendiente
└── Estado: PENDING ⏳

RONDA 3 - BINANCE (180 velas)
├── Pre-Validación: ⏳ Pendiente
├── Demo Trading: ⏳ Pendiente (~3 horas)
├── 🚨 CRÍTICO - Trades Count: ⏳ Pendiente
├── 🚨 CRÍTICO - Win Rate: ⏳ Pendiente
├── TP/SL Ejecutados: ⏳ Pendiente
├── OCO Comportamiento: ⏳ Pendiente
├── Stress Tests: ⏳ Pendiente
└── Estado: PENDING ⏳
```

### 🚨 Ejemplo de Falla Crítica
```
RONDA 2 - BINANCE (EJEMPLO DE BUG)
├── Pre-Validación: ✅ 24/24 tests
├── Demo Trading: ✅ 60 velas procesadas
├── 🚨 CRÍTICO - Trades Count: ❌ Demo=0, Backtest=3 (MISMATCH)
├── 🚨 CRÍTICO - Win Rate: ❌ Demo=0%, Backtest=100% (MISMATCH)
├── TP/SL Ejecutados: ✅ 4/60 (7%)
├── OCO Comportamiento: ✅ 100% correcto
├── Balance Match: N/A (No aplicable por bug crítico)
└── Estado: FAILED ❌ - BUG CRÍTICO DETECTADO
```
