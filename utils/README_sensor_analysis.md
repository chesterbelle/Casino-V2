# Sensor Analysis Utility

Herramienta para analizar la memoria del sensor tracker y obtener insights sobre el performance de los sensores.

## Uso

### Análisis Básico
```bash
python utils/sensor_analysis.py
```

Muestra:
- Resumen general (total sensores, trades, win rate promedio)
- Top 10 sensores por score
- Bottom 10 sensores por score

### Análisis Detallado
```bash
python utils/sensor_analysis.py --detailed
```

Incluye además:
- Distribución de performance (Excellent/Good/Neutral/Poor/Terrible)
- Análisis de expectancy (positiva/negativa)
- Análisis de win rate (alto/bajo)
- Recomendaciones de mejora

### Personalizar Número de Sensores
```bash
python utils/sensor_analysis.py --top 20 --bottom 5
```

### Exportar a CSV
```bash
python utils/sensor_analysis.py --export
```

Genera `sensor_analysis.csv` con todos los datos para análisis en Excel/Google Sheets.

### Archivo Personalizado
```bash
python utils/sensor_analysis.py --stats-file path/to/custom_stats.json
```

## Métricas Analizadas

- **Score**: Puntaje compuesto (0.0 - 1.0)
  - Expectancy: 40%
  - Win Rate Short: 30%
  - Profit Factor: 20%
  - Streak Bonus: 10%

- **Win Rate Short**: Últimos 50 trades
- **Win Rate Medium**: Últimos 200 trades
- **Expectancy**: (WR × AvgWin) - (LR × AvgLoss)
- **Profit Factor**: GrossProfit / GrossLoss
- **Current Streak**: Racha actual (positiva/negativa)

## Categorías de Performance

- **Excellent** (≥0.7): Sensores de alto rendimiento
- **Good** (0.6-0.7): Sensores buenos
- **Neutral** (0.4-0.6): Sensores promedio
- **Poor** (0.3-0.4): Sensores de bajo rendimiento
- **Terrible** (<0.3): Sensores que deberían deshabilitarse

## Ejemplo de Salida

```
================================================================================
📊 SENSOR TRACKER ANALYSIS
================================================================================
Total Sensors:        52
Active Sensors:       45 (≥10 trades)
Total Trades:         1234
Avg Win Rate:         52.3%
================================================================================

🏆 TOP 10 SENSORS BY SCORE
--------------------------------------------------------------------------------
Rank   Sensor                         Score    WR       Exp        PF       Trades
--------------------------------------------------------------------------------
1      MACDCrossover                  0.723    58.2%    +0.0234    1.45     87
2      PinBarReversal                 0.698    55.1%    +0.0189    1.38     102
3      RSIReversion                   0.687    56.7%    +0.0176    1.42     94
...

⚠️  BOTTOM 10 SENSORS BY SCORE
--------------------------------------------------------------------------------
Rank   Sensor                         Score    WR       Exp        PF       Trades
--------------------------------------------------------------------------------
1      DojiIndecision                 0.245    38.2%    -0.0145    0.78     56
2      ThreeBar                       0.267    41.3%    -0.0098    0.85     43
...

💡 RECOMMENDATIONS
--------------------------------------------------------------------------------
⚠️  Consider disabling 5 terrible sensors (score < 0.3)
   - DojiIndecision (score: 0.245)
   - ThreeBar (score: 0.267)
   ...

✅ Focus on 8 excellent sensors (score ≥ 0.7)
   - MACDCrossover (score: 0.723)
   - PinBarReversal (score: 0.698)
   ...
```

## Integración con Workflow

1. **Después de backtest**: Analizar qué sensores funcionaron mejor
2. **Optimización**: Deshabilitar sensores terribles, enfocarse en excelentes
3. **Iteración**: Re-testear y comparar resultados
4. **Mejora continua**: Ajustar lógica de sensores basándose en insights
