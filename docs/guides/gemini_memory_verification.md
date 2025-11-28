# Guía de Verificación de Memoria Gemini

Esta guía explica cómo inspeccionar, verificar y analizar la memoria y el comportamiento de aprendizaje de Gemini.

## 1. Herramientas de Análisis Rápido

La forma más sencilla de ver el estado actual de la memoria es usar el script de utilidad `analyze_buckets.py`.

### Ejecución
```bash
# Desde la raíz del proyecto
python3 utils/analyze_buckets.py

# O si usas el entorno virtual
.venv/bin/python3 utils/analyze_buckets.py
```

### Interpretación de la Salida
El script mostrará una tabla con las siguientes columnas:

| Columna | Descripción |
| :--- | :--- |
| **Strategy / Bucket** | La combinación de Estrategia y Contexto de Mercado (ej: `RSI_Reversion|BBW=L|...`). |
| **Winrate** | Tasa de victorias actual en la ventana de memoria. |
| **Wins / Losses** | Conteo absoluto de victorias y derrotas. |
| **Total** | Total de observaciones en la ventana. |
| **Status** | Estado heurístico: <br> - `Building Support`: Menos de 20 muestras. <br> - `✅ Positive`: Winrate > 52% (aprox BEP). <br> - `❌ Negative`: Winrate bajo. |

## 2. Logs Detallados de Señales

Para entender **por qué** Gemini tomó una decisión y qué valores tenían los sensores (ATR, BBW, RSI, etc.) en ese momento, revisa el log de señales.

**Archivo:** `gemini/data/casino_signals_log.csv`

Este archivo se actualiza cada vez que Gemini evalúa una señal, independientemente de si resulta en un trade real o no.

### Columnas Clave
-   **timestamp**: Momento exacto de la señal.
-   **trade_id**: ID único para correlacionar con resultados.
-   **bucket_id**: El bucket asignado a la señal.
-   **atr, bbw, rsi2, etc.**: Valores crudos de los indicadores técnicos.

**Tip:** Puedes abrir este CSV en Excel o Google Sheets para filtrar por `bucket_id` y ver qué características tienen las señales ganadoras vs perdedoras.

## 3. Auditoría de Memoria (Raw Data)

Gemini mantiene dos archivos de memoria principales en `gemini/data/`:

1.  **`memory_state.json`**:
    -   **Propósito**: Estado actual "en caliente" (RAM persistida).
    -   **Uso**: Carga rápida al inicio. Contiene los contadores de ventanas deslizantes.
    -   **Verificación**: Abre este archivo para ver la estructura JSON cruda si sospechas corrupción en `analyze_buckets.py`.

2.  **`memory_log.csv`**:
    -   **Propósito**: Histórico inmutable de todos los trades finalizados.
    -   **Uso**: Reconstrucción de memoria desde cero (Cold Start).
    -   **Verificación**: Si borras `memory_state.json`, Gemini reconstruirá su conocimiento leyendo este archivo línea por línea.

## Flujo de Trabajo Recomendado

1.  **Monitoreo Diario**: Ejecuta `analyze_buckets.py` para ver qué estrategias están funcionando bien (`✅ Positive`).
2.  **Depuración de Trades**: Si ves un trade extraño, copia su `trade_id` y búscalo en `casino_signals_log.csv` para ver qué "vio" el bot (valores de sensores).
3.  **Análisis Profundo**: Importa `casino_signals_log.csv` y `gemini_trade_results.csv` en una herramienta de análisis (Pandas, Excel) y haz un join por `trade_id` para correlacionar características (ATR, BBW) con el resultado (PnL).
