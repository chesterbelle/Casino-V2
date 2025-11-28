# Propuesta de Sensores para Scalping de Alta Frecuencia (1m)

**Objetivo:** Capturar movimientos rápidos de precio (0.6% - 1.0%) con alta precisión (>60%) en timeframes de 1 minuto, adaptándose a la volatilidad de criptomonedas.

---

## 1. Adaptive RSI Scalper (RSI Adaptativo)
**Concepto:** Los niveles fijos de RSI (30/70) son ineficientes: dan falsas señales en tendencias fuertes y entran tarde en mercados laterales. Este sensor ajusta dinámicamente sus umbrales basándose en la volatilidad reciente (ATR).

**Lógica:**
- Calcular ATR (14 periodos).
- **Baja Volatilidad (Rango):** Estrechar umbrales a 40/60.
    - *Razón:* En rangos pequeños, el precio rebota antes de llegar a extremos.
- **Alta Volatilidad (Tendencia):** Ampliar umbrales a 20/80.
    - *Razón:* En tendencias fuertes, el precio se mantiene "sobrecomprado" mucho tiempo; necesitamos extremos reales para apostar en contra.

**Ventaja:** Reduce Stop Loss por entrar demasiado pronto en "cuchillos cayendo".

---

## 2. Momentum Burst (Explosión de Momento)
**Concepto:** Scalping puro. Detectar la *aceleración* repentina del precio para entrar en la dirección del movimiento (o en contra si es exhaustivo).

**Lógica:**
- Medir el cambio de RSI en 1 sola vela (`RSI_actual - RSI_previo`).
- **Señal:** Si RSI salta > 15 puntos en 1 minuto.
- **Dirección:**
    - Si RSI < 50 y salta hacia arriba: **LONG** (Inicio de rebote).
    - Si RSI > 80 y salta hacia arriba: **SHORT** (Blow-off top / Agotamiento).

**Ventaja:** Captura el movimiento *mientras* sucede, no después. Ideal para TPs cortos (0.6%).

---

## 3. Bollinger Band Rejection (Rechazo de Bandas)
**Concepto:** La reversión a la media más fiable. No basta con tocar la banda; el precio debe ser *rechazado* por ella.

**Lógica:**
- Vela $N$ tiene Máximo > Banda Superior (o Mínimo < Banda Inferior).
- Vela $N$ cierra **DENTRO** de las bandas.
- **Señal:** Entrar en la apertura de la Vela $N+1$.

**Ventaja:** Filtra los casos donde el precio "camina" por la banda (band walking) rompiendo stops. Espera la confirmación visual del rechazo.

---

## 4. VSA Reversal (Volume Spread Analysis Lite)
**Concepto:** Esfuerzo vs Resultado. Detectar manipulación o absorción institucional.

**Lógica:**
- **Volumen:** Muy alto (Top 10% de las últimas 50 velas).
- **Cuerpo de Vela (Spread):** Muy pequeño (Doji o Spinning Top, < 20% del rango total high-low).
- **Interpretación:** Hubo mucha actividad (volumen) pero el precio no avanzó (cuerpo pequeño). Alguien está absorbiendo la ordenes. El reverso es inminente.

**Ventaja:** Detecta techos y suelos de mercado con alta precisión, filtrando movimientos sin volumen real.
