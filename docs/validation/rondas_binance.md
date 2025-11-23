# Plan de Validación por Rondas - Casino V2 (Binance)

## 🎯 Objetivo
Validar que el backtesting refleja correctamente el comportamiento del bot en demo/trading con datos de Binance.

## 📋 Estrategia: 3 Rondas Progresivas

### Filosofía
```
Demo Trading → Descargar Datos Reales → Backtest → Comparar → Ajustar → Repetir
```

Cada ronda debe pasar antes de avanzar a la siguiente.

---

## 🔄 Ronda 1: Detección Rápida (10 velas)

**Duración:** ~15 minutos total
- Demo trading: ~10 minutos
- Descarga + backtest + comparación: ~5 minutos

**Objetivo:** Detectar bugs obvios rápidamente

**Comando:**
```bash
./tests/validation/run_ronda1_binance.sh
```

**Proceso:**
1. ✅ Ejecutar demo trading (10 velas de 1m en Binance demo/testnet)
2. ✅ Extraer timestamps del log
3. ✅ Descargar datos históricos REALES de Binance para los timestamps relevantes
4. ✅ Ejecutar backtest con los mismos datos y balance inicial
5. ✅ Comparar resultados automáticamente

**Tolerancias:**
- Balance final: ±0.5%
- PnL total: ±1.0%
- Número de trades: ±1
- Win rate: ±5%

**Archivos generados:**
- `logs/demo_*.json` - Resultado del demo trading
- `data/validation/historical_ronda1.csv` - Datos históricos
- `logs/backtest_*.json` - Resultado del backtest
- `logs/comparison_ronda1.txt` - Comparación detallada

---

## 🔄 Ronda 2: Validación Media (30 velas)

**Duración:** ~35 minutos total
- Demo trading: ~30 minutos
- Descarga + backtest + comparación: ~5 minutos

**Objetivo:** Validar comportamiento en período más largo

**Comando:**
```bash
./tests/validation/run_ronda2_binance.sh
```

**Proceso:** Igual que Ronda 1, pero con 30 velas

**Tolerancias:** Mismas que Ronda 1

---

## 🔄 Ronda 3: Validación Completa (60 velas)

**Duración:** ~65 minutos total
- Demo trading: ~60 minutos
- Descarga + backtest + comparación: ~5 minutos

**Objetivo:** Validación completa del sistema

**Comando:**
```bash
./tests/validation/run_ronda3_binance.sh
```

**Proceso:** Igual que Ronda 1, pero con 60 velas

**Tolerancias:** Mismas que Ronda 1

---

## 📊 Criterios de Éxito

### ✅ Ronda Exitosa
- Todas las métricas dentro de tolerancia
- Sin errores de ejecución
- Datos históricos completos (sin gaps)
- Logs generados correctamente

### ❌ Ronda Fallida
- Cualquier métrica fuera de tolerancia
- Errores durante ejecución
- Gaps en datos históricos
- Comportamiento inconsistente

---

## 🔧 Si una Ronda Falla

1. **Analizar logs de comparación:**
   ```bash
   cat logs/comparison_ronda1.txt
   ```

2. **Revisar diferencias:**
   - ¿Balance final muy diferente?
   - ¿Número de trades diferente?
   - ¿Precios de entrada/salida diferentes?

3. **Posibles causas:**
   - Timing de órdenes (demo vs backtest)
   - Slippage en demo trading
   - Fees diferentes
   - Bugs en lógica del bot
   - Datos históricos incompletos

4. **Ajustar y repetir:**
   - Corregir bugs encontrados
   - analizr ronda y esperar indicaciones para continuar
   - Re-ejecutar la misma ronda

---

## 🚀 Estado Actual

### ✅ Preparación Completada
- [x] Binance connector configurado para demo/testnet
- [x] Connector validator pasando sus tests relevantes (local)
- [x] Scripts de Ronda 1, 2 y 3 adaptados para Binance
- [x] Scripts auxiliares listos (download, compare)
- [x] Directorios creados
- [x] **Scripts corregidos para período exacto** (sin margen de 5 min)
- [x] **Balance inicial automático** (extrae del demo log)

### 📝 Próximo Paso
```bash
# Ejecutar Ronda 1 para Binance (corregida)
./tests/validation/run_ronda1_binance.sh
```

### 🔧 Mejoras Implementadas (2025-11-22)

1. **Período Exacto**: Eliminado margen de 5 minutos en descarga de datos
2. **Balance Consistente**: Backtest usa el mismo balance inicial que demo
3. **Extracción Automática**: Scripts extraen timestamps y balance del demo log

Estas mejoras aseguran que la comparación Demo vs Backtest sea precisa y significativa.

---

## 📚 Herramientas

### Scripts Principales
- `tests/validation/run_ronda1_binance.sh` - Ronda 1 completa
- `tests/validation/run_ronda2_binance.sh` - Ronda 2 completa (TODO si no existe)
- `tests/validation/run_ronda3_binance.sh` - Ronda 3 completa (TODO si no existe)

### Scripts Auxiliares
- `tests/validation/download_historical_data.py` - Descarga datos de Binance (modular para exchange)
- `tests/validation/compare_results.py` - Compara resultados
- `utils/connector_validator.py` - Valida connector

### Configuración
- Exchange: **Binance (demo / testnet)**
- Symbol: **LTC/USDT:USDT** (Futures USDT-M)
- Interval: **1m**
- Player: **paroli**

---

---

## 📞 Soporte

Si encuentras problemas:
1. Revisar logs en `logs/`
2. Verificar connector:
```bash
python -m utils.connector_validator --exchange binance --demo
```
3. Verificar datos:
```bash
cat data/validation/historical_ronda1.csv | head
```
