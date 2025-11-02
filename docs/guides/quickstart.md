# 🚀 Quick Start

Guía para comenzar a usar Casino V2 en menos de 5 minutos.

---

## ⚡ Instalación Rápida

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/Casino-V2.git
cd Casino-V2
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

**Dependencias principales:**
- `pandas` - Manejo de datos
- `numpy` - Cálculos numéricos
- `scipy` (opcional) - Distribuciones bayesianas
- `python-dotenv` - Variables de entorno

---

## 🎯 Primer Backtest

### Opción 1: Con Dataset de Ejemplo

```bash
# Ejecutar con dataset incluido
python main.py
```

**Salida esperada:**
```
🎰 CASINO V2 - BACKTEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Dataset: LTCUSDT_15min_bull.csv
🕐 Timeframe: 15min
📈 Velas: 2,000
💰 Balance inicial: 10,000.00 USDT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ Procesando velas...
[████████████████████] 100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESULTADOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance final: 10,542.33 USDT
📈 PnL: +542.33 USDT (+5.42%)
🏆 Winrate: 57.6%
⚙️ Trades: 182
  ├─ BET: 155
  └─ GHOST: 27
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Opción 2: Con Tu Dataset

```bash
# Descargar datos de Binance
python utils/download_kline_dataset.py \
  --symbol BTCUSDT \
  --interval 15m \
  --limit 2000 \
  --tag my_backtest

# Configurar en config.py
# DATASET_PATH = "tables/data/raw/BTCUSDT_15min_my_backtest.csv"

# Ejecutar
python main.py
```

---

## 🎮 Probar Diferentes Players

### Kelly Player (Default)

```bash
python main.py
```

**Características:**
- Usa criterio de Kelly para sizing
- Ajusta posición según edge probabilístico
- Conservador (20% de Kelly óptimo por defecto)

### Fixed Player

```bash
python main.py --player=fixed
```

**Características:**
- Tamaño de posición fijo (1% por defecto)
- Más simple y predecible
- Útil para comparar estrategias

---

## 📊 Interpretar Resultados

### Archivos Generados

Después de ejecutar, encontrarás:

```
gemini/data/
├── decisions.csv         # Log de decisiones
├── memory_log.csv        # Historial de trades por estrategia
└── memory_state.json     # Estado de memoria (winrates)
```

### Métricas Clave

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| **Winrate** | % trades ganadores | > 55% |
| **PnL %** | Retorno sobre capital | > 0% |
| **GHOST trades** | Trades simulados (entrenamiento) | Disminuye con el tiempo |
| **BET trades** | Trades reales (apostando) | Aumenta con el tiempo |

### decisions.csv

```csv
timestamp,trade_id,action,side,reason,size,equity,strategy,p_hat,kelly,approved
2024-01-15T10:00:00,BTCUSDT-LONG-123,BET,LONG,apuesta_conservadora,0.015,10000,RSIReversion,0.58,0.024,yes
2024-01-15T10:15:00,BTCUSDT-SHORT-124,GHOST,SHORT,sin_aprobadas,0.0,10000,KeltnerReversion,0.52,0.0,no
```

**Columnas importantes:**
- `action`: BET (apuesta real) o GHOST (simulación)
- `reason`: Por qué se tomó la decisión
- `p_hat`: Probabilidad estimada de ganar
- `kelly`: Fracción de Kelly calculada
- `approved`: Si la estrategia tiene suficientes datos

---

## ⚙️ Configuración Básica

Edita `config.py` para ajustar parámetros:

```python
# TRADING PARAMETERS
TAKE_PROFIT = 0.01           # 1% target
STOP_LOSS = 0.01             # 1% stop
KELLY_FRACTION = 0.2         # 20% de Kelly óptimo
MAX_POSITION_SIZE = 0.02     # Máximo 2% por trade

# DATASET
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"

# MEMORY
MIN_SUPPORT = 500            # Mínimo trades para aprobar estrategia
MEMORY_WINDOW = 500          # Ventana de memoria por estrategia
```

Ver [Configuración Completa](configuration.md) para todas las opciones.

---

## 🔄 Normalización Automática de Símbolos

**Casino V2 incluye normalización automática de símbolos por exchange** para evitar errores comunes en live trading.

### Cómo Funciona

Cuando escribes un símbolo, el sistema lo convierte automáticamente al formato correcto:

| Exchange | Input | Normalizado | Ejemplo |
|----------|-------|-------------|---------|
| **Kraken** | `btc` | `PF_BTC` | `btc` → `PF_BTC` |
| **Hyperliquid** | `BTCUSDT` | `BTC` | `BTCUSDT` → `BTC` |
| **Binance** | `btc` | `BTCUSDT` | `btc` → `BTCUSDT` |

### Ejemplo en Acción

```bash
# Live trading con Kraken
python main.py
# Exchange: KRAKEN_DEMO
# Símbolo a operar [PF_XBTUSD]: btc
# Símbolo normalizado para Kraken: PF_BTC

# Sistema automáticamente usa PF_BTC para Kraken
```

### Beneficios

✅ **Menos errores**: No necesitas recordar formatos específicos
✅ **UX mejorada**: Escribe símbolos naturalmente
✅ **Consistencia**: Mismo símbolo funciona en todos los exchanges
✅ **Live trading seguro**: Evita errores de "símbolo no encontrado"

**Nota:** La normalización se registra en los logs para trazabilidad.

---

## 🔄 Próximos Pasos

1. ✅ **Entender la Arquitectura**
   - Lee [Overview](../architecture/overview.md)
   - Comprende [Gemini/Player](../architecture/gemini-player.md)

2. ✅ **Experimentar con Parámetros**
   - Ajusta `TAKE_PROFIT` y `STOP_LOSS`
   - Prueba diferentes `KELLY_FRACTION`
   - Compara resultados

3. ✅ **Crear Tu Propio Player**
   - Sigue [Creating Players](creating-players.md)
   - Implementa tu estrategia de sizing
   - Compara con Kelly y Fixed

4. ✅ **Trading en Vivo (Paper)**
   - Configura [Live Trading](live-trading.md)
   - Prueba en testnet primero
   - Monitorea resultados

---

## 🆘 ¿Problemas?

- 📖 [FAQ](faq.md) - Preguntas frecuentes
- 🐛 [Troubleshooting](troubleshooting.md) - Soluciones a problemas comunes
- 💬 [Issues](https://github.com/tu-usuario/Casino-V2/issues) - Reportar bugs

---

## 🎉 ¡Listo!

Ya tienes Casino V2 funcionando. Explora la [documentación completa](../README.md) para aprender más.

---

**← [Volver al índice](../README.md)**
