# 🚀 Primeros Pasos con Casino V2

> Tutorial paso a paso para principiantes

## 🎯 Objetivo de este tutorial

Al final de esta guía podrás:
- ✅ Ejecutar tu primer backtest
- ✅ Entender los resultados
- ✅ Hacer tu primera modificación
- ✅ Ejecutar live trading básico

**Tiempo estimado**: 30 minutos

---

## 📋 Prerrequisitos

- ✅ [Instalación completa](installation.md) terminada
- ✅ Python 3.10+ funcionando
- ✅ Dependencias instaladas
- ✅ Dataset de ejemplo disponible

Verificar instalación:

```bash
# Verificar que todo está listo
python -c "
import sys
print(f'✅ Python {sys.version.split()[0]}')

try:
    from gemini.gemini_core import Gemini
    from tables.table_ccxt_pro import TableCCXTPro
    print('✅ Módulos principales importados')
except ImportError as e:
    print(f'❌ Error de importación: {e}')
    sys.exit(1)

print('🎰 ¡Listo para empezar!')
"
```

---

## 🎲 Paso 1: Primer Backtest

### Configuración básica

```bash
# Asegurarse de que config.py esté configurado para backtest
cat config.py
```

Deberías ver:
```python
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"
```

### Ejecutar backtest

```bash
python main.py
```

### Analizar resultados

Deberías ver salida como:

```
🎰 Casino V2 — Backtest Mode
🔄 MODO: Single-Asset Backtest
🎮 Player seleccionado: PAROLI
📁 Dataset: tables/data/raw/LTCUSDT_1m__1d.csv

🟢 Iniciando sesión: backtest
============================================================
📌 Dataset: LTCUSDT_1m__1d.csv
🎮 Player:  PAROLI
------------------------------------------------------------
   Balance inicial       : 10000.00
   Velas procesadas      : 1440
   Trades BET            : 21
   Trades GHOST          : 774
   Trades SKIP           : 1344
   Wins / Losses         : 16 / 5
   WinRate (BET)         : 76.19%
   Comisiones totales    : 0.00
   Funding total         : 0.00
   Liquidaciones         : 0
   Balance final         : 10002.08
   PnL Total             : +2.08 (+0.02%)
============================================================
```

### ¿Qué significan estos números?

| Métrica | Significado | Tu resultado |
|---------|-------------|--------------|
| **Trades BET** | Trades reales ejecutados | ~21 |
| **Trades GHOST** | Entrenamiento sin riesgo | ~774 |
| **WinRate** | Porcentaje de trades ganadores | ~76% |
| **PnL Total** | Ganancia/perdida neta | +$2.08 |

---

## 🔍 Paso 2: Entender el Sistema

### Arquitectura básica

```
📊 Datos → 🎯 Sensores → 🧠 Gemini → 🎮 Player → 🃏 Croupier → 💰 Resultado
```

1. **Datos**: Precios OHLCV del mercado
2. **Sensores**: Detectan contextos técnicos (17 sensores)
3. **Gemini**: Valida si hay ventaja estadística
4. **Player**: Decide cuánto apostar (Paroli, Kelly, Fixed)
5. **Croupier**: Ejecuta la orden
6. **Resultado**: PnL y actualización de balance

### Tipos de trades

- **BET**: Trade real con riesgo de capital
- **GHOST**: Entrenamiento sin riesgo (aprende winrate)
- **SKIP**: No hay oportunidad o capital insuficiente

### Players disponibles

| Player | Estrategia | Riesgo |
|--------|------------|--------|
| **Paroli** | Aumenta size en wins | Alto |
| **Kelly** | Cálculo matemático óptimo | Medio |
| **Fixed** | Tamaño constante | Bajo |

---

## 🎮 Paso 3: Probar Diferentes Players

### Cambiar a Fixed Player

```bash
# Ejecutar con Fixed Player
python main.py --player=fixed
```

**Resultado esperado:**
- Menos trades BET (más conservador)
- Winrate similar o ligeramente menor
- PnL más bajo pero más consistente

### Comparar resultados

| Player | Trades BET | WinRate | PnL Total |
|--------|------------|---------|-----------|
| Paroli | ~21 | ~76% | +$2.08 |
| Fixed | ~15 | ~74% | +$1.50 |

---

## ⚙️ Paso 4: Modificar Configuración

### Crear configuración personalizada

```bash
# Crear config personalizado
cp config.py config_personal.py
```

Editar `config_personal.py`:

```python
# Configuración más agresiva para testing
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"

# Parámetros más agresivos
KELLY_FRACTION = 0.5          # 50% de Kelly (vs 0.2 default)
MAX_POSITION_SIZE = 0.1       # 10% máximo (vs 0.02 default)
TAKE_PROFIT = 0.02           # 2% target (vs 0.01 default)
STOP_LOSS = 0.02             # 2% stop (vs 0.01 default)

# Sensores más permisivos
MIN_SUPPORT = 100            # Menos datos requeridos (vs 500)
BAYES_CREDIBILITY_THRESHOLD = 0.6  # Menos estricto (vs 0.7)
```

### Ejecutar con configuración personalizada

```bash
# Usar config personalizado
python main.py --config=config_personal.py
```

**Resultado esperado:**
- Más trades BET (más agresivo)
- Mayor volatilidad en PnL
- Potencialmente mejor o peor resultado

---

## 📊 Paso 5: Analizar Resultados Detallados

### Ver logs detallados

```bash
# Ejecutar con más verbosidad
python main.py --verbose 2>&1 | head -50
```

### Examinar archivos de salida

```bash
# Ver archivos generados
ls -la gemini/data/
ls -la results/

# Ver decisiones de Gemini
head -20 gemini/data/gemini_decisions.csv

# Ver resultados de trades
head -20 gemini/data/gemini_trade_results.csv
```

### Analizar winrate por sensor

```bash
# Ver estadísticas de memoria
python -c "
import pandas as pd
df = pd.read_csv('gemini/data/memory_log.csv')
print('Top 5 estrategias por winrate:')
print(df.nlargest(5, 'winrate')[['strategy', 'winrate', 'total_trades']])
"
```

---

## 🔌 Paso 6: Live Trading Básico

### ⚠️ Importante: Solo testnet

**Nunca uses mainnet para testing inicial**

### Configurar para live trading

```bash
# Cambiar a modo live (pero con timeout de seguridad)
echo "MODE = 'live'" > config.py
echo "EXCHANGE = 'HYPERLIQUID'" >> config.py

# Ejecutar con timeout de 5 minutos
timeout 300 python main.py
```

### ¿Qué esperar?

```
✅ Conexión WebSocket exitosa
📊 Datos OHLCV llegando en tiempo real
🎯 Señal detectada por sensor X
🎲 Trade ejecutado: BUY 0.01 BTC @ $50000
💰 Balance actualizado: 10050.00
```

### Si no hay trades

Es normal en live trading:
- Mercado puede estar quieto
- Sensores necesitan datos históricos
- Umbrales conservadores evitan señales falsas

---

## 🎯 Paso 7: Crear tu Primer Custom Player

### Crear player simple

```bash
# Crear archivo players/my_player.py
cat > players/my_player.py << 'EOF'
def calculate_position_size(verdict, equity, meta=None):
    """
    Mi primer player personalizado.
    Reglas simples: 1% si winrate > 70%, nada si no.
    """
    if not verdict or not verdict.side:
        return None
    
    # Buscar métricas aprobadas
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Calcular winrate promedio
    avg_winrate = sum(m.p_hat for m in approved) / len(approved)
    
    # Mi lógica simple
    if avg_winrate > 0.7:  # 70% winrate mínimo
        position_size = equity * 0.01  # 1% del equity
        return position_size
    else:
        return None
EOF
```

### Probar tu player

```bash
# Cambiar a backtest primero
echo "MODE = 'backtest'" > config.py

# Ejecutar con tu player
python main.py --player=my_player
```

### Mejorar tu player

```python
def calculate_position_size(verdict, equity, meta=None):
    """
    Player mejorado con más lógica.
    """
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Calcular métricas
    avg_winrate = sum(m.p_hat for m in approved) / len(approved)
    total_trades = sum(m.total_trades for m in approved)
    
    # Lógica más sofisticada
    if avg_winrate > 0.75 and total_trades > 100:
        # Alto confidence: 2%
        return equity * 0.02
    elif avg_winrate > 0.7 and total_trades > 50:
        # Medio confidence: 1%
        return equity * 0.01
    elif avg_winrate > 0.65:
        # Bajo confidence: 0.5%
        return equity * 0.005
    else:
        return None
```

---

## 📈 Paso 8: Próximos Pasos

### Para profundizar

1. **Leer documentación completa**
   - [Arquitectura del sistema](../architecture/overview.md)
   - [Guía de sensores](../reference/sensors.md)
   - [API de Players](../reference/api-players.md)

2. **Experimentar más**
   - Probar diferentes datasets
   - Crear múltiples custom players
   - Analizar resultados detallados

3. **Live trading avanzado**
   - Configurar múltiples exchanges
   - Monitorear performance real
   - Optimizar parámetros

### Recursos adicionales

- 📖 [Documentación completa](../README.md)
- 🐛 [Issues en GitHub](https://github.com/chesterbelle/Casino-V2/issues)
- 💬 [Discusiones](https://github.com/chesterbelle/Casino-V2/discussions)

---

## 🎉 ¡Felicitaciones!

Has completado el tutorial básico de Casino V2:

- ✅ Ejecutaste tu primer backtest
- ✅ Entendiste los resultados
- ✅ Probaste diferentes players
- ✅ Modificaste configuración
- ✅ Creaste tu primer custom player
- ✅ Probaste live trading básico

**¡Ahora eres un trader probabilístico!** 🎰

---

**📖 [← Instalación](installation.md)** | **🔐 [Config Exchanges →](exchange-setup.md)** | **🆘 [Troubleshooting →](../development/troubleshooting.md)**