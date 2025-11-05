# ✅ PRE-TESTING CHECKLIST v1.9.3

**Fecha:** 2025-11-05
**Versión:** 1.9.3
**Objetivo:** Validar que el código está listo para las pruebas mandatorias

---

## 🔍 REVISIÓN EXHAUSTIVA COMPLETADA

### ✅ 1. Flujo de Ejecución de Órdenes con TP/SL

**Estado:** ✅ VERIFICADO

**CCXTAdapter.execute_order():**
- ✅ Pasa `take_profit_multiplier` y `stop_loss_multiplier` en params (genérico)
- ✅ NO usa parámetros específicos de exchange
- ✅ Mantiene agnosticidad

**KrakenConnector.create_order():**
- ✅ Detecta multiplicadores genéricos en params
- ✅ Obtiene precio de entrada (limit o market)
- ✅ Calcula precios absolutos: `entry_price * multiplier`
- ✅ Traduce a `takeProfitPrice` y `stopLossPrice` (Kraken-specific)
- ✅ Remueve multiplicadores genéricos de params
- ✅ Envía orden con parámetros traducidos

**Resultado:**
```
✅ TP: $105404.76 (+2.00%)
✅ SL: $101271.24 (-2.00%)
📋 Clean params being sent: {'takeProfitPrice': 105404.76, 'stopLossPrice': 101271.24}
✅ Orden creada | BTC/USD BUY 0.001 @ market
```

---

### ✅ 2. Paroli Player - Filtrado de Ciclos

**Estado:** ✅ VERIFICADO

**Lógica de Filtrado:**
- ✅ Filtra posiciones por `player == "paroli"`
- ✅ Filtra por `symbol == current_symbol`
- ✅ Filtra por `timeframe == current_timeframe`
- ✅ Soporta objetos `OpenPosition` (testing/live)
- ✅ Soporta diccionarios (backtest)
- ✅ NO apuesta si hay ciclo activo en (symbol, timeframe)

**Corrección Aplicada:**
- ✅ Logs de debugging cambiados de INFO a DEBUG
- ✅ Output de testing será más limpio

---

### ✅ 3. Metadata de Posiciones

**Estado:** ✅ VERIFICADO

**BuildOrderStage:**
- ✅ Agrega `player` (nombre del player)
- ✅ Agrega `timeframe` (del metadata)
- ✅ Agrega `cycle_step` (del estado de Paroli)

**TradingSession:**
- ✅ Pasa `symbol` al metadata
- ✅ Pasa `timeframe` al metadata
- ✅ Pasa `open_positions` al metadata

**BacktestDataSource:**
- ✅ Guarda metadata en posiciones (dict)
- ✅ Incluye `player`, `timeframe`, `cycle_step`

**PositionTracker:**
- ✅ Extrae metadata de la orden
- ✅ Asigna a `OpenPosition` dataclass
- ✅ Incluye `player`, `timeframe`, `cycle_step`

---

### ✅ 4. BacktestDataSource - Simulación de TP/SL

**Estado:** ✅ VERIFICADO

**Lógica de Simulación:**
- ✅ Usa `high`/`low` de vela para simular ejecución intra-candle
- ✅ Prioriza SL sobre TP (realista)
- ✅ Calcula PnL correctamente: `(exit_price - entry_price) * amount`
- ✅ Aplica fees de salida
- ✅ Retorna margin reservado al balance
- ✅ Aplica PnL neto (puede ser negativo)
- ✅ Determina WIN/LOSS por PnL real, no por exit_reason

**Fórmulas:**
```python
# Long
pnl = (exit_price - entry_price) * amount

# Short
pnl = (entry_price - exit_price) * amount

# Net PnL
net_pnl = pnl - exit_fee

# Balance update
balance += entry_notional  # Return margin
balance += net_pnl         # Apply PnL
```

---

### ✅ 5. Detección de Trades Cerrados (Testing Mode)

**Estado:** ✅ VERIFICADO

**TradingSession._check_and_process_closed_trades():**
- ✅ Fetch trades del exchange (`fetch_my_trades`)
- ✅ Filtra por `reduceOnly=True` (TP/SL orders)
- ✅ Extrae `realizedPnl` de Kraken
- ✅ Evita duplicados con `processed_trade_ids`
- ✅ Llama a `handle_trade_outcome()` para actualizar Paroli

**Corrección Aplicada:**
- ✅ Logs de debugging eliminados
- ✅ Output de testing será más limpio

---

### ✅ 6. Herramientas de Testing

**Estado:** ✅ VERIFICADAS

**Herramientas Disponibles:**
- ✅ `utils/download_ohlcv.py` - Descarga OHLCV general
- ✅ `utils/download_exact_period.py` - Descarga período exacto
- ✅ `utils/compare_results.py` - Compara backtest vs testing

**download_exact_period.py:**
- ✅ Acepta timestamps de inicio/fin
- ✅ Descarga de Kraken Futures
- ✅ Guarda en formato CSV compatible con backtest
- ✅ Incluye preview de datos

**Uso:**
```bash
python utils/download_exact_period.py <start_ts> <end_ts> <output.csv>
```

---

## 📋 CHECKLIST FINAL PRE-TESTING

### Código
- [x] TP/SL embebidos en orden principal (Kraken)
- [x] Paroli filtra ciclos por (player, symbol, timeframe)
- [x] Metadata de posiciones completo
- [x] BacktestDataSource simula TP/SL correctamente
- [x] Testing mode detecta trades cerrados
- [x] Logs de debugging limpios (nivel DEBUG)

### Arquitectura
- [x] CCXTAdapter agnóstico (multiplicadores genéricos)
- [x] KrakenConnector traduce a formato específico
- [x] Separación de responsabilidades mantenida
- [x] Documentación completa en docstrings

### Herramientas
- [x] Script de descarga de datos funcional
- [x] Script de comparación funcional
- [x] Estructura de directorios preparada

### Configuración
- [x] Kraken Futures Demo configurado
- [x] Paroli configurado (progresión 1-4-8)
- [x] TP/SL configurados (verificar en config)

---

## 🚀 PRÓXIMOS PASOS

### 1. Verificar Configuración de TP/SL
```bash
# Verificar que config.yaml tenga TP/SL configurados
cat config.yaml | grep -A 5 "take_profit\|stop_loss"
```

### 2. Ejecutar RONDA 1 - Testing Mode
```bash
python main.py --mode=testing --player=paroli \
    --symbol=BTC/USD --interval=1m --max-candles=60 \
    2>&1 | tee logs/round1_testing.log
```

**Capturar:**
- Timestamp inicio/fin
- Balance inicial/final
- Número de señales
- Número de órdenes
- Progresión Paroli (steps)
- Wins/Losses

### 3. Descargar Dataset Exacto
```bash
# Extraer timestamps del log de testing
START_TS=$(grep "Session started" logs/round1_testing.log | awk '{print $NF}')
END_TS=$(grep "Session ended" logs/round1_testing.log | awk '{print $NF}')

# Descargar datos
python utils/download_exact_period.py $START_TS $END_TS data/round1_testing.csv
```

### 4. Ejecutar RONDA 1 - Backtest Mode
```bash
python main.py --mode=backtest --player=paroli \
    --csv=data/round1_testing.csv \
    2>&1 | tee logs/round1_backtest.log
```

### 5. Comparar Resultados
```bash
python utils/compare_results.py \
    --testing=logs/round1_testing.log \
    --backtest=logs/round1_backtest.log \
    --output=reports/round1_comparison.md
```

### 6. Analizar Diferencias
- ¿Mismo número de señales?
- ¿Mismo número de órdenes?
- ¿Misma progresión Paroli?
- ¿Balance final similar (±10%)?
- ¿Wins/Losses coinciden?

---

## ⚠️ PUNTOS CRÍTICOS A MONITOREAR

### Durante Testing Mode:
1. **TP/SL se crean correctamente:**
   - Buscar logs: `✅ TP:` y `✅ SL:`
   - Verificar `takeProfitPrice` y `stopLossPrice` en params

2. **Posiciones se cierran:**
   - Buscar logs: `🟢 Position closed` o `🔴 Position closed`
   - Verificar `exit_reason`: `take_profit` o `stop_loss`

3. **Paroli NO apuesta con ciclo activo:**
   - Si hay posición abierta en (symbol, timeframe)
   - Paroli debe retornar 0.0

4. **Progresión Paroli avanza correctamente:**
   - WIN: step 0→1→2, luego reset a 0
   - LOSS: reset a 0 inmediatamente

### Durante Backtest Mode:
1. **Simulación de TP/SL:**
   - Verificar que posiciones cierran en high/low de velas
   - Verificar PnL calculado correctamente

2. **Mismas señales que Testing:**
   - Gemini debe detectar las mismas señales
   - Sensores deben dar los mismos resultados

3. **Misma progresión Paroli:**
   - Steps deben ser idénticos
   - Wins/Losses deben coincidir

---

## 📊 MÉTRICAS DE ÉXITO

### Críticas (deben coincidir 100%):
- ✅ Número de señales detectadas
- ✅ Número de órdenes ejecutadas
- ✅ Sides de las órdenes (LONG/SHORT)
- ✅ Progresión Paroli (steps: 0→1→2→0)

### Tolerables (±5-10%):
- ⚠️ Balance final (por slippage/fees reales)
- ⚠️ PnL exacto
- ⚠️ Entry/Exit prices exactos

### Criterio de Brecha Aceptable:
```
Balance final: ±10% máximo
Trades ejecutados: ±1 trade máximo
Steps de Paroli: Idénticos
Wins/Losses: Idénticos (si hay cierres)
```

---

## ✅ CÓDIGO LISTO PARA TESTING

**Resumen:**
- ✅ Todas las revisiones completadas
- ✅ Correcciones aplicadas
- ✅ Logs limpiados
- ✅ Herramientas verificadas
- ✅ Documentación actualizada

**Estado:** 🟢 LISTO PARA RONDA 1

**Próxima Acción:** Ejecutar testing mode según ROADMAP_v1.9.3.md

---

**Última Actualización:** 2025-11-05
**Revisado Por:** Cascade AI
**Commits:**
- `5e84f13` - fix(tp-sl): Implement connector-agnostic TP/SL approach
- `2c0a0a3` - docs: Add architecture documentation
- `aeabee9` - refactor: Clean up debug logs for testing preparation
