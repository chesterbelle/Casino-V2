# 💐 GEMINI — Sistema Probabilístico de Gestión y Selección de Apuestas (Diseño)

> **Rol:** “cerebro matemático” del casino.  
> **Función:** decide **si** apostar y **cuánto** apostar en cada oportunidad, buscando **EV positivo** y control de riesgo **agnóstico a régimen** (bull/bear).

---

## 1) Objetivo

1. **Validar** oportunidades generadas por un módulo sensorial (reversión a la media/otras) usando un criterio **probabilístico** explícito.  
2. **Dimensionar** la “ficha” por operación según el **edge estimado** (Kelly fraccional prudente).  
3. **Abstenerse** cuando el edge cae por debajo del **punto de equilibrio** neto (costos reales incluidos).  

> Geminis no “predice precios”; **audita** y **optimiza** la esperanza matemática de un flujo de señales, actuando como **filtro** y **gestor de riesgo**.

> Nota: este documento replica el estilo y rigurosidad del diseño TGRD (Tri-Guard Range Detector) y lo integra como posible productor de señales; la filosofía de “jugar solo con ventaja” es compartida.

---

## 2) Fundamento teórico (EV, BEP y sizing)

- **Payoff neto** por trade (con comisiones/slippage/funding):
  - **R** = % cuando gana (neto), **L** = % cuando pierde (neto).  
- **Punto de equilibrio** de winrate:
  
  \[
  p^\*=\frac{L}{L+R}
  \]
  
  Si el **winrate real** \(p\) supera \(p^\*\), entonces el **EV por trade** es positivo:
  
  \[
  EV = p\cdot R - (1-p)\cdot L \quad\Rightarrow\quad EV>0 \iff p>p^\*
  \]

- **Dimensionamiento (Kelly fraccional, prudente)**  
  Con payoff efectivo \(b=\tfrac{R}{L}\) y probabilidad \(p\), Kelly ideal:
  \[
  f^\* = p - \frac{1-p}{b}
  \]
  Para robustez operativa se usa un **factor prudente** (p. ej. 0.3–0.5):
  \[
  f = \lambda \cdot f^\*, \quad \lambda\in(0,1)
  \]
  Se trunca a \(f\ge 0\).

---

## 3) Arquitectura

### 3.1 Sensores (productores de oportunidades)
**Entrada:** OHLCV.  
**Salida:** eventos \((t, \text{side}, \text{features})\) con “razón de entrada” documentada.  
Sensores típicos de reversión (agnósticos a régimen):

- **RSI(2)** extremo: LONG si < 10–15 / SHORT si > 85–90.  
- **Toque Keltner** (EMA20 ± \(1.25\times ATR_{20}\)).  
- **Compresión BBW**: \(BBW < p30\) local.  
- **Wick** grande (\(\ge 40\%\) del rango de la vela) en dirección de rechazo.  
- **%B** de Bollinger fuera de zona (sobre/infra-extensión).

**Score de reversión**: sumar condiciones por lado (0–N). **Disparar** si score ≥ 2 con **histeresis/debounce** (e.g., confirmar 1 cierre).

> Cualquier otro detector (p. ej. TGRD) puede enchufarse como fuente adicional de oportunidades.

---

### 3.2 Gemini (validador + gestor)

**Estimación de probabilidad** \( \hat p \):

- **Rolling empírico** sin look-ahead (e.g., ventana de 120 eventos).  
- **Opción bayesiana** (recomendada): \(p\sim\text{Beta}(\alpha,\beta)\).
  - Conjugada con éxitos/fracaso; permite **credibilidad**: aceptar solo si  
    \(\Pr\{p>p^\*\mid\text{datos}\} \ge \tau\) (p. ej. \(\tau=0.6\)).

**Condicionamiento por contexto (“buckets”)**:  
Estimamos \(\hat p\) **por bucket** en lugar de global:
- **BBW terciles** (L/M/H), **range_score** (2/3/≥4), **franja horaria** (4 bloques de 6h), **ATR/Close tercil**, **tipo de señal dominante** (RSI/Toque/…).

**Criterio de aceptación**
- Soporte mínimo por bucket: **n ≥ 20** (o credibilidad bayesiana mínima).  
- Aceptar si: \(\hat p > p^\*\) **y** soporte suficiente.  
- **Sizing**: \(f=\lambda\cdot\big(\hat p - \tfrac{1-\hat p}{b}\big)^+\) (con \(\lambda\) 0.3–0.5).  
- **Apagado total**: si \(\hat p \le p^\*\) o cae el soporte, **no se apuesta**.

---

## 4) Flujo de ejecución

1. **Ingesta** de velas → **cálculo de features** (ATR, BBW, RSI2, EMA20, Keltner, etc.).  
2. **Sensores** generan candidatos con `side`, `score`, `features`.  
3. **Gemini**:
   - mapea el candidato a un **bucket** de contexto;
   - obtiene \(\hat p\) y **soporte** del bucket;
   - **acepta** si \( \hat p>p^\* \) (y soporte/credibilidad suficientes);
   - asigna **ficha** (Kelly fraccional) y emite **orden**.  
4. **Ejecución** y **cierre**:
   - **Entrada**: open de \(t+1\);  
   - **Objetivos**: **TP=R** %, **SL=L** %, **time-stop** (e.g., 12–20 velas) a **midline**;  
   - **Log**: resultado, ret\_% neto y todas las features.  
5. **Aprendizaje**: actualizar historial por bucket (rolling o Beta).

---

## 5) Parámetros propuestos (agnósticos)

- **Costos netos**: fijar **R** y **L** con comisiones, slippage y funding ya incluidos (p. ej. R=1.42 %, L=1.58 % → \(p^\*\approx 52.66\%\)).  
- **Ventana** rolling: 120 eventos por bucket (walk-forward).  
- **Soporte mínimo**: 20 eventos por bucket (o credibilidad bayesiana \(\ge 60\%\)).  
- **Kelly prudente**: \(\lambda \in [0.3, 0.5]\).  
- **Time-stop**: 12–20 velas; **midline** (EMA20).  
- **Debounce/histeresis** sensorial: evitar micro-repeticiones (cool-down).

---

## 6) Esquema de datos (para backtest/producción)

**Archivo:** `casino_signals_log.csv` (1 fila = 1 oportunidad)

| Columna         | Descripción breve |
|---|---|
| `timestamp`     | tiempo del evento (apertura del trade en \(t+1\)). |
| `side`          | LONG / SHORT. |
| `price_entry`   | precio de entrada. |
| `atr`           | ATR20 local. |
| `bbw`           | ancho de bandas relativo. |
| `rsi2`          | RSI(2). |
| `touch_dn/up`   | 1 si tocó Keltner inferior/superior. |
| `cond_bbw`      | 1 si \(BBW<p30\). |
| `range_score`   | entero (0–N) sensores cumplidos por lado. |
| `bucket_id`     | hash/clave compuesta (e.g. `BBW=L|RS=3|TOD=Tarde`). |
| `ret_pct`       | retorno neto del trade (%). |
| `win`           | 1 si ganó, 0 si perdió. |

**Archivo:** `gemini_decisions.csv` (decisión y sizing por evento aceptado)

| Columna     | Descripción |
|---|---|
| `timestamp` | idem arriba |
| `bucket_id` | bucket de contexto |
| `p_hat`     | prob. estimada sin look-ahead (previa al trade) |
| `support`   | #observaciones válidas en el bucket |
| `accepted`  | 1/0 |
| `kelly`     | fracción de equity arriesgada |
| `equity`    | equity tras el trade |

---

## 7) Evaluación y reporting

**Unidades de evaluación**: bloques mensuales (purgados), bull y bear por separado y juntos.

- **KPIs por bloque y globales**:
  - **Winrate** de aceptados + **IC95%** (Wilson).  
  - **EV** neto por trade y **por mes**.  
  - **N** de eventos, **aceptados** y **tasa de aceptación**.  
  - **Max Drawdown**, **Retorno total**, **Sharpe/Sortino** por trade.  
- **Sensibilidad de costos**:
  - +0.02 % y +0.05 % de slippage sobre **R**/**L**.  
- **Monte Carlo (bootstrap)** con **retornos sobre equity** de trades aceptados (1,000 corridas) para banda probable de equity final.  
- **Comparativa** con:
  - **Gemini simple (global)** vs **Gemini por bucket**.  
  - **Con** y **sin** time-stop.  
  - **Kelly 30 %** vs **Kelly 50 %**.

---

## 8) Criterios de refutación (no-edge)

- Si **≥ 40 %** de los bloques **no** superan \(p^\*\) en el **límite inferior** del IC95 %, se considera **no sostenible**.  
- Si al aplicar **p95** de slippage el **EV** global se acerca a **0** o negativo, se considera **no robusto**.  
- Si **Kelly** produce **streaks** que superan el DD presupuestado, bajar \(\lambda\) o exigir mayor soporte/credibilidad.

---

## 9) Integración con otros jugadores

- **A (SMA20/50)** y **B (TGRD)** pueden seguir operando como productores de candidatos.  
- **Gemini** unifica criterios con **mismo \(p^\*\)** y **mismo Kelly fraccional**, **agnósticos** a régimen.  
- **Política Pit Boss** (opcional): cuando B (rango “premium”) está activo, **capar** exposición de A; Gemini aplica el **mismo filtro** y sizing sobre ambos flujos.

---

## 10) Pseudocódigo (alto nivel)

```text
for cada nueva vela t:
  actualizar features (ATR, BBW, RSI2, EMA20, Keltner...)
  candidatos = sensores(t)  // score >= 2, debounce cumplido

  for c in candidatos:
    bucket = hash(BBW tercil, range_score, hora, tipo_señal,...)
    (p_hat, support) = estadística_previa(bucket)   // sin incluir c

    if (support >= MIN_SUPPORT) and (p_hat > p_star):
        f = max(0, lambda * (p_hat - (1 - p_hat)/b))
        ejecutar_orden(c.side, size = f * equity)
    else:
        skip

  // al cierre del trade (TP/SL/time-stop):
  loggear resultado (win, ret_pct) y actualizar bucket
```

---

## 11) Recomendaciones finales de implementación

- **Agnóstico por defecto**: **no** separar parámetros por bull/bear; que la **selección** (p̂ por bucket) haga el trabajo.  
- **Persistencia** por bucket: guardá **p_hat, soporte** y **última actualización** para continuidad en producción.  
- **Validación walk-forward** y **hold-out** de meses completos; no re-optimizar umbrales por régimen.  
- **Alertas** operativas: si **p̂** global o por bucket cae cerca de \(p^\*\) por X trades, **disminuir** \(\lambda\) o **pausar**.

---

### Apéndice: ejemplo de umbrales iniciales (no tuneados)
- RSI2: 15 / 85  
- Keltner: 1.25 × ATR20  
- BBW: p30 local  
- Debounce: 1 vela de confirmación  
- Time-stop: 16 velas → midline  
- Kelly: \(\lambda=0.5\) (arrancar con 0.3 si el DD es sensible)

---

**Resultado esperado:** un sistema que **apuesta poco cuando no hay ventaja**, **sube ficha cuando el edge regresa**, y mantiene **EV+** con **riesgo controlado**, reutilizando cualquier sensorial (incluido TGRD) como “radar de mesas favorables”.

