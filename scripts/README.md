# 🤖 Scripts Automatizados - Casino V2

> ℹ️ Todos los scripts ejecutables se movieron a `utils/`.  
> Puedes llamarlos como módulos (`python3 -m utils.cli …`) o ejecutar directamente
> los nuevos archivos (`python3 utils/train_memory.py`, etc.).

La lógica principal reside en `utils/cli.py`, que centraliza cada comando.
Recomendamos invocar los comandos con:

```bash
python3 -m utils.cli <comando>
```

---

## 📋 Scripts Disponibles

### **🚀 Pipeline Completo (Recomendado)**

```bash
python3 -m utils.cli full-pipeline
```

También disponible como:

```bash
python3 utils/full_pipeline.py
```

**Ejecuta todo el proceso:**
1. ✅ Descarga datos de entrenamiento
2. ✅ Entrena memoria (GHOST mode)
3. ✅ Analiza resultados
4. ✅ Valida estrategias (BET mode)

**Duración estimada:** 2-6 horas (dependiendo de datos)

---

### **📥 1. Descargar Datos**

```bash
python3 -m utils.cli download-training-data
```

o de forma directa:

```bash
python3 utils/download_training_data.py
```

**Qué hace:**
- Descarga datos históricos de 5 símbolos (BTC, ETH, LTC, BNB, SOL)
- 35,000 velas por símbolo (~1 año en 15min)
- Guarda en `tables/data/raw/`

**Personalizar:**
```bash
python3 -m utils.cli download-training-data \
    --symbols BTCUSDT ETHUSDT SOLUSDT \
    --interval 5m \
    --days 120 \
    --tag custom
```

---

### **🧠 2. Entrenar Memoria**

```bash
python3 -m utils.cli train-memory
```

o con el ejecutable directo:

```bash
python3 utils/train_memory.py
```

**Qué hace:**
- Ejecuta backtests en modo GHOST (sin apostar)
- Entrena la memoria de **todas** las estrategias
- Guarda en `gemini/data/memory_state.json`

**Opciones:**
```bash
# Entrenar con todos los datasets
python3 -m utils.cli train-memory

# Solo datasets de training
python3 -m utils.cli train-memory --pattern "*training.csv"

# Solo un símbolo específico
python3 -m utils.cli train-memory --pattern "BTCUSDT*.csv"
```

**Duración:** 1-3 horas dependiendo de cantidad de datos

---

### **📊 3. Analizar Memoria**

```bash
python3 -m utils.cli analyze-memory
```

**Qué hace:**
- Muestra estadísticas de memoria entrenada
- Top estrategias por winrate
- Estrategias aprobadas vs pendientes
- Recomendaciones

**Salida ejemplo:**
```
📊 ANÁLISIS DE MEMORIA ENTRENADA
════════════════════════════════
  Total estrategias: 124
  Aprobadas (>= 500 trades): 18
  Pendientes: 106

✅ TOP ESTRATEGIAS APROBADAS:
 # Estrategia                                            Trades   Winrate
 1 🟢 BTCUSDT@15min|BBW=L|RSI=1|H=M|StochasticReversion  587     58.43%
 2 🟢 ETHUSDT@15min|BBW=M|RSI=2|H=L|Supertrend           523     57.02%
 ...
```

---

### **✅ 4. Validar Estrategias**

```bash
python3 -m utils.cli validate-strategies
```

o usando el archivo dedicado:

```bash
python3 utils/validate_strategies.py
```

**Qué hace:**
- Ejecuta backtests con BET **real** (apuesta)
- Usa estrategias ya entrenadas
- Guarda resultados en `results/validation_XXXXXX/`

**Importante:** 
- Solo ejecutar después de entrenar memoria
- Revisa resultados antes de live trading

---

## 🎯 Flujo Recomendado

### **Primera Vez (Setup Completo):**

```bash
# 1. Pipeline completo automático
python3 -m utils.cli full-pipeline

# (El script irá pausando entre fases para que revises)
```

### **Entrenar con Más Datos:**

```bash
# 1. Descargar más símbolos/períodos
python3 -m utils.cli download-training-data --symbols BTCUSDT ETHUSDT

# 2. Re-entrenar (acumula sobre memoria existente)
python3 -m utils.cli train-memory

# 3. Ver cómo mejoró
python3 -m utils.cli analyze-memory
```

### **Solo Validación (después de cambios):**

```bash
# Si modificaste config, sensores, etc.
python3 -m utils.cli validate-strategies
```

---

## 📁 Estructura de Archivos Generados

```
Casino-V2/
├── tables/data/raw/
│   ├── BTCUSDT_15m_training.csv      # Datos descargados
│   ├── ETHUSDT_15m_training.csv
│   └── ...
├── gemini/data/
│   ├── memory_log.csv                # Log de todos los trades
│   ├── memory_state.json             # Estado de memoria (winrates)
│   └── decisions.csv                 # Log de decisiones
├── logs/
│   ├── training_BTCUSDT_15m.log      # Logs de entrenamiento
│   └── ...
└── results/
    └── validation_20250115_143022/   # Resultados de validación
        ├── validation_BTCUSDT.txt
        └── ...
```

---

## ⚙️ Configuración

Los scripts usan configuración inteligente:

### **Durante Entrenamiento (GHOST):**
```python
FORCE_GHOST_ALL = True         # No apuesta real
MIN_SUPPORT = 500              # Mínimo trades para aprobar
ACTIVE_SENSORS = {... todos activos ...}
```

### **Durante Validación (BET):**
```python
FORCE_GHOST_ALL = False        # Apuesta simulada
STARTING_BALANCE = 10000       # Capital inicial
# Usa estrategias ya entrenadas
```

---

## 🐛 Troubleshooting

### **Error: "No se encontraron datasets"**

```bash
# Ejecuta primero la descarga
python3 -m utils.cli download-training-data
```

### **Error: "utils/download_kline_dataset.py no encontrado"**

```bash
# Asegúrate de estar en la raíz del proyecto
cd /ruta/a/Casino-V2
python3 -m utils.cli full-pipeline
```

### **Entrenamiento muy lento**

Reduce cantidad de datos:
```bash
python3 -m utils.cli download-training-data --days 120 --interval 15m
```

### **Pocas estrategias aprobadas**

Necesitas más datos:
```bash
python3 -m utils.cli download-training-data --symbols BTCUSDT ETHUSDT SOLUSDT ADAUSDT
```

---

## 📊 Métricas de Éxito

### **Después de Entrenamiento:**

✅ **BUENO:**
- Estrategias aprobadas: > 15
- Winrate promedio: > 55%
- % GHOST en validación: < 30%

⚠️ **REGULAR:**
- Estrategias aprobadas: 8-15
- Winrate promedio: 52-55%
- % GHOST: 30-50%

❌ **NECESITA MÁS DATOS:**
- Estrategias aprobadas: < 8
- Winrate promedio: < 52%
- % GHOST: > 50%

---

## 🚀 Próximos Pasos

Después de validar exitosamente:

1. **Paper Trading**
   ```bash
   # Configurar en config.py
   MODE = "live"
   EXCHANGE = "BINANCE_FUTURES_TESTNET"
   ```

2. **Live Trading** (⚠️ dinero real)
   ```bash
   # Solo después de paper trading exitoso
   MODE = "live"
   EXCHANGE = "BINANCE_FUTURES"
   ```

---

## 💡 Tips

- **Primera vez:** Usa `python3 -m utils.cli full-pipeline` (más fácil)
- **Re-entrenar:** Solo `python3 -m utils.cli train-memory` (más rápido)
- **Validar cambios:** Solo `python3 -m utils.cli validate-strategies`
- **Analizar siempre:** `python3 -m utils.cli analyze-memory` después de entrenar

---

## 🔗 Documentación Relacionada

- [Configuración de Sensores](../docs/guides/new_sensors_config.md)
- [Arquitectura](../docs/architecture/overview.md)
- [Quick Start](../docs/guides/quickstart.md)

---

**¿Listo para entrenar? Ejecuta:**

```bash
python3 -m utils.cli full-pipeline
```

o bien:

```bash
python3 utils/full_pipeline.py
```

🎰 ¡Buena suerte!
