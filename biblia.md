# 📜 Biblia Técnica — Gemini V2

## 1. Propósito

Gemini V2 es el cerebro probabilista del **Casino Binance V2**. Su misión es decidir si apostar (`BET`) o no (`GHOST`) en cada vela, con el objetivo de mantener **Valor Esperado (EV) positivo** una vez descontados **comisiones** y **slippage**. El motor aplica teoría de utilidad esperada, credibilidad bayesiana y Kelly fraccional para filtrar señales y dimensionar la ficha.

## 2. Flujo General

1. **Sensores** (Reversión a la Media): RSI, Bollinger, Keltner generan señales por vela.
2. **Sensor Manager** consolida señales: agrupa por lado, calcula métricas (BBW, ATR, etc.) y entrega la lista al Gemini.
3. **Gemini Core** evalúa:
   - Clasificar contexto (bucket) con `BucketManager`.
   - Consultar memoria (`GeminiMemory`) para obtener winrate estimado y soporte.
   - Calcular credibilidad bayesiana (`Pr(p > p*)`) y Kelly neto.
   - Decidir `BET`, `GHOST` o `SKIP`.
4. **Croupier** ejecuta orden contra la mesa (`TableBacktest`), que simula TP/SL, costes netos y actualiza `BalanceManager`.
5. **GeminiMemory** registra el resultado por estrategia/bucket para entrenar a futuro.

```
Sensores → SensorManager → Gemini → Croupier → Table → Memory
```

## 3. Coste Neto y Punto de Equilibrio

El sistema solo apuesta cuando el winrate estimado supera el punto crítico:

### 3.1 Variables clave
- `TAKE_PROFIT = 0.012` (1.2 %)
- `STOP_LOSS = 0.008` (0.8 %)
- `COMMISSION_RATE = 0.0004` (0.04 % por lado)
- `SLIPPAGE_DEFAULT = 0.0005`

### 3.2 Coste total del trade
\[
 C = 2 \times \text{COMMISSION\_RATE} + \text{SLIPPAGE\_DEFAULT}
 = 0.0013
\]

### 3.3 Ganancia/Pérdida neta
\[
 R' = \text{TAKE\_PROFIT} - C = 0.0107 \quad ; \quad
 L' = \text{STOP\_LOSS} + C = 0.0093
\]

### 3.4 Umbral de winrate
\[
 p^\* = \frac{L'}{R' + L'} \approx 46.5\%
\]

Gemini exige que el **cuantil inferior (percentil 5)** de la distribución posterior Beta supere \(p^\*\) antes de apostar. Si \(R'\le0\), se bloquean las apuestas (`p^\*=1`).

## 4. Credibilidad Bayesiana

Para cada bucket/estrategia:
1. Contabiliza éxitos/fracaso en ventana deslizante (`WINDOW_SIZE=120`).
2. Calcula la posterior \( \text{Beta}(\alpha, \beta) \) con prior uniforme.
3. Estima la credibilidad: \( \Pr(p > p^\*) \).
4. Requiere:
   - `support >= MIN_SUPPORT` (60)
   - `credibility >= 0.7`
   - Cuantil inferior (percentil 5) > \(p^\*\)

Solo si pasa esos filtros se permite el cálculo de Kelly.

## 5. Kelly Fraccional

Se calcula con la versión neta:
\[
 f = \max\left(0,\ p_c - \frac{1 - p_c}{B}\right) \times KELLY\_FRACTION
\]
- `p_c`: cuantil conservador (0.05).
- `B = R'/L'`.
- `KELLY_FRACTION = 0.3`.
Si `f <= 0`, la señal se marca `GHOST`.

## 6. Sensores

Todos los sensores están en `sensors/reversion/` y se activan vía `SensorManager`. Parámetros actuales (configurables en `config.py`):

| Sensor            | Parámetro clave | Valor extremo | Señal |
|-------------------|-----------------|---------------|-------|
| RSI Reversion     | `period`        | 2             | RSI < 10 → LONG, RSI > 90 → SHORT |
| Bollinger Touch   | `std_dev`       | 2.5           | Precio ≤ banda inferior → LONG; ≥ superior → SHORT |
| Keltner Reversion | `multiplier`    | 2.0           | Precio < canal inferior → LONG; > superior → SHORT |

Las señales incluyen features (`rsi2`, `bbw`, `atr`, etc.) para el bucket.

## 7. Sensor Manager

- Instancia sensores activos según `ACTIVE_SENSORS`.
- Aplica cooldown (`SENSOR_COOLDOWN_BARS`).
- Consolida señales por lado, promediando métricas y construyendo el `contributors`.
- Devuelve una lista única por lado, que Gemini usa para crear participantes.

## 8. Bucket Manager

- Clasifica la señal en buckets `BBW={L/M/H}|RS{score}|H={franja}`.
- Las estadísticas se agrupan por clave `market|bucket|estrategia`.
- Si el bucket falla (`UNKNOWN`), la señal se descarta (`bucket_unknown`).

## 9. GeminiMemory

- Ventana deslizante por bucket/estrategia (`WINDOW_SIZE=120`).
- Registra cada trade en CSV (`memory_log`) y snapshot JSON (`memory_state`).
- Soporte mínimo (`MIN_SUPPORT=60`) antes de apostar.
- Actualiza `winrate`, `support`, `wins/losses`.

## 10. Registro de Decisiones

1. `gemini/data/gemini_decisions.csv`:
   - `p_hat`, `credibility`, `p_conservative`, `p_star`, `r_net`, `l_net`, `kelly`, `support`, motivo de aprobación/rechazo.
2. `gemini/data/gemini_trade_results.csv`:
   - `exit_reason` (TP, SL), `bars_held`, `entry_price`, `trigger_price`, `pnl`, `pnl_pct`, `fee`, `ghost`.

Herramienta auxiliar: `python3 utils/analyze_trade_results.py` genera un resumen por `exit_reason`.

## 11. Requisitos para Apuesta (`BET`)

En una vela se requiere simultáneamente:
1. Señales activas → Bucket válido → Lista de participantes.
2. Soporte ≥ `MIN_SUPPORT`.
3. Credibilidad bayesiana ≥ 0.7.
4. Cuantil inferior (5 %) > \(p^\*\).
5. Kelly neto > 0 tras escalar con `KELLY_FRACTION`.

Si algún paso falla, se genera `GHOST` o `SKIP`.

## 12. Pre-entrenamiento y Flujo Secuencial

- El backtest se ejecuta en secuencia (`Bull → Bear`), compartiendo memoria.
- La primera fase puede arrojar muchos `GHOST` mientras se acumula soporte.
- Se recomienda un periodo de precalentamiento si se quiere reducir la fase “en frío”.

## 13. Ajustes Clave

- **Criterios netos**: volver rentable EV requiere usar R'/L' (ya adoptado).
- **Sensores extremos**: thresholds agresivos mejoran `p_hat`, pero menos señales.
- **Kelly prudente**: usar `KELLY_FRACTION < 1` para limitar drawdown.
- **Logging constante**: analizar `decisions.csv` y `trade_results.csv` para ajustar estrategias.

## 14. Próximos pasos

1. Evaluar sensores adicionales o features contextuales (orden cruzado, horario, volumen).
2. Realizar pre-entrenamientos largos antes de evaluar periodos críticos.
3. Incluir métricas adicionales (drawdown, ratio Kelly/frecuencia) para afinar aún más.

---
Con esta guía, el algoritmo puede revisarse end-to-end: desde cómo se mide el edge hasta cómo se decide cada apuesta y se cuantifica su resultado. Mantener el EV neto positivo requiere tanto una lógica conservadora como señales con ventaja real sobre \(p^\* = 46.5\%\).
