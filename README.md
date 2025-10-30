# 🎰 Casino V2 — Trading Probabilístico

> Sistema de trading modular basado en ventaja estadística, no en predicción.

[![Version](https://img.shields.io/badge/Versión-1.6-blue)](docs/CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-14/14_passing-brightgreen)](test_phase1.py)
[![Live Trading](https://img.shields.io/badge/Live-Trading_Supported-success)](docs/guides/hyperliquid_setup.md)

## 🚨 Para Desarrolladores

> **⚠️ IMPORTANTE**: Si vas a contribuir código, lee **[DEVELOPER.md](DEVELOPER.md)** ANTES de empezar. Es obligatorio.


---

## 🚀 Quick Start

### **Opción A: Backtest (Recomendado para empezar)**

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar modo backtest
# Editar config.py:
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"

# 3. Ejecutar backtest
python main.py
```

### **Opción B: Live Trading (Testnet)**

```bash
# 1. Configurar credenciales en .env
echo "HYPERLIQUID_API_KEY=tu_api_key" >> .env
echo "HYPERLIQUID_API_SECRET=tu_secret" >> .env

# 2. Configurar modo live
# Editar config.py:
MODE = "live"
EXCHANGE = "HYPERLIQUID"

# 3. Ejecutar live trading
python main.py
```

**📖 [Guía completa de instalación →](docs/guides/installation.md)**

**📖 [Tutorial paso a paso →](docs/guides/getting-started.md)**

---

## 💡 ¿Qué es Casino V2?

Casino V2 es un **motor de trading probabilístico avanzado** diseñado para:

### **🎯 Estado Actual (v1.6)**
- ✅ **Arquitectura Unificada**: Un solo `main.py` para live y backtest
- ✅ **Multi-Exchange Testnet**: Hyperliquid, Binance, Kraken
- ✅ **WebSocket Integration**: Datos en tiempo real completos
- ✅ **17 Sensores Activos**: Mean Reversion, Momentum, Volume
- ✅ **Sistema de Memoria**: Aprendizaje bayesiano funcional
- ✅ **Risk Management**: Conservador y probado

### **🚀 Visión Futura (v1.7+)**
- **🎰 Multi-Asset Trading**: Operar múltiples criptomonedas simultáneamente
- **⏱️ Multi-Timeframe Analysis**: Analizar diferentes marcos temporales
- **🔄 Real-Time Processing**: Procesar flujos de velas concurrentemente
- **🎯 Sensor-Driven Decisions**: Señales técnicas por activo
- **💰 Unified Risk Management**: Gestión holística del portfolio

### **🔬 Enfoque Probabilístico**
- ✅ No intenta predecir el mercado
- ✅ Busca **contextos con ventaja estadística** (EV > 0)
- ✅ Apuesta solo cuando las probabilidades están a favor
- ✅ Aprende de la experiencia empírica

**Filosofía:**
> *"No se trata de ganar todas las manos, sino de apostar cuando la ventaja está del lado del jugador."*

**Estado Actual:** Arquitectura modular single-asset como base sólida para expansión multi-asset.

---

## ✨ Features

### Core
- ✅ **Arquitectura Modular** - Separación Gemini (validación) / Player (sizing)
- ✅ **Sistema de Memoria** - Aprende winrate por estrategia/contexto
- ✅ **Bucket System** - Clasifica contextos de mercado
- ✅ **Bayesian Inference** - Credibilidad estadística robusta

### Players Disponibles
- 🎮 **Kelly Player** - Kelly Criterion conservador (default)
- 🎮 **Fixed Player** - Tamaño fijo por trade
- 🎮 **Paroli Player** - Progresión 1-4-8 que ignora el edge de Gemini (apuesta mientras exista `side`)
- 🎮 **Custom Players** - Crea tu propia estrategia

### Trading
- 📊 **Backtesting Robusto** - Fees, slippage, funding, liquidaciones
- 📈 **Live Trading Testnet** - Hyperliquid, Binance, Kraken (testnet)
- 🔌 **WebSocket Integration** - Datos en tiempo real eficientes
- 👻 **GHOST Trades** - Entrena sin riesgo cuando no hay datos
- 🎯 **Multi-Exchange Support** - Tres exchanges principales

### Análisis
- 📝 **Decision Logging** - Log detallado de cada decisión
- 📊 **Métricas por Estrategia** - Winrate, soporte, credibilidad
- 🔍 **Trazabilidad Completa** - Desde señal hasta resultado

---

## 🏗️ Arquitectura

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  Sensores │─────▶│  Gemini  │─────▶│  Player  │
│ (Detectan)│      │ (Valida) │      │ (Sizing) │
└──────────┘      └──────────┘      └──────────┘
                        │                  │
                        │◀─────────────────┘
                        ▼
                  ┌──────────┐
                  │ Croupier │
                  │(Ejecuta) │
                  └──────────┘
                        │
                        ▼
                  ┌──────────┐      ┌──────────┐
                  │   Mesa   │─────▶│ Balance  │
                  │  (Feed)  │      │ Manager  │
                  └──────────┘      └──────────┘
```

**🎰 Metáfora del Casino:**

| Rol | Módulo | Función |
|-----|--------|---------|
| 🎩 Jugador Racional | `gemini/` | Evalúa probabilidades |
| 🎮 Estratega | `players/` | Decide tamaño de apuesta |
| 👁️ Analistas | `sensors/` | Detectan contextos |
| 🧤 Crupier | `croupier/` | Ejecuta órdenes |
| 🪙 Mesa | `tables/` | Provee datos y ejecuta |
| 💰 Cajero | `balance_manager.py` | Administra capital |

**📐 [Ver arquitectura completa →](docs/architecture/overview.md)**

---

## 📖 Documentación

### 🚀 Para Empezar
- [Instalación Completa](docs/guides/installation.md) - Setup desde cero
- [Primeros Pasos](docs/guides/getting-started.md) - Tutorial paso a paso
- [Configuración Básica](docs/guides/configuration.md) - Config inicial

### 📈 Trading
- [Backtesting](docs/guides/backtesting.md) - Estrategias de simulación
- [Live Trading](docs/guides/live-trading.md) - Trading en testnet
- [Multi-Exchange Setup](docs/guides/exchange-setup.md) - Configurar exchanges
- [Crear Players](docs/guides/creating-players.md) - Custom sizing strategies

### 🏗️ Arquitectura
- [Sistema Completo](docs/architecture/overview.md) - Arquitectura v1.6
- [Gemini/Player](docs/architecture/gemini-player.md) - Separación de responsabilidades
- [WebSocket Integration](docs/architecture/websocket-integration.md) - Datos en tiempo real

### 📚 Referencia
- [Config Reference](docs/reference/config-reference.md) - Todas las configuraciones
- [API Gemini](docs/reference/api-gemini.md) - API de validación
- [API Players](docs/reference/api-players.md) - API de sizing
- [Sensores](docs/reference/sensors.md) - Guía de indicadores

### 🛠️ Desarrollo
- [Contributing](docs/development/contributing.md) - Guía de contribución
- [Testing](docs/development/testing.md) - Tests y validación
- [Troubleshooting](docs/development/troubleshooting.md) - Solución de problemas
- [Roadmap](docs/development/PENDIENTES.md) - Pendientes y features

---

## 🎯 Ejemplos

### Backtest Básico (v1.6)

```bash
# Configurar en config.py
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"

# Ejecutar
python main.py
```

**Salida de ejemplo:**
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

### Live Trading (Testnet)

```bash
# Configurar en config.py
MODE = "live"
EXCHANGE = "HYPERLIQUID"  # o "BINANCE_FUTURES_TESTNET" o "KRAKEN_DEMO"

# Ejecutar
python main.py
```

### Crear Custom Player

```python
# players/my_player.py

def calculate_position_size(verdict, equity, meta=None):
    """Mi estrategia personalizada."""
    if not verdict or not verdict.side:
        return None
    
    approved = [m for m in verdict.metrics if m.approved]
    if not approved:
        return None
    
    # Tu lógica aquí
    avg_p_hat = sum(m.p_hat for m in approved) / len(approved)
    
    if avg_p_hat > 0.57:
        return 0.02  # 2%
    elif avg_p_hat > 0.54:
        return 0.01  # 1%
    else:
        return None
```

```bash
python main.py --player=my_player
```

**📖 [Ver guía completa →](docs/guides/creating-players.md)**

---

## 🧪 Testing

```bash
# Tests de arquitectura (Fase 1)
python test_phase1.py
# ✅ 11/11 tests pasando

# Tests de mejoras
python test_mejoras_futurechanges.py
# ✅ 3/3 tests pasando
```

---

## 📊 Resultados de Ejemplo

| Métrica | Kelly Player | Fixed Player |
|---------|--------------|--------------|
| **Balance Final** | 10,542 USDT | 10,387 USDT |
| **ROI** | +5.42% | +3.87% |
| **Winrate** | 57.6% | 56.8% |
| **Trades** | 182 | 195 |
| **Avg Size** | 1.2% | 1.0% |
| **Max DD** | -3.2% | -2.8% |

*Ejemplo ilustrativo con LTCUSDT 15min (2000 velas)*

---

## ⚙️ Configuración

### Dataset

```python
# config.py
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_15min_bull.csv"
```

### Parámetros de Trading

```python
TAKE_PROFIT = 0.01           # 1% target
STOP_LOSS = 0.01             # 1% stop
KELLY_FRACTION = 0.2         # 20% de Kelly
MAX_POSITION_SIZE = 0.02     # 2% máximo
```

### Sistema de Memoria

```python
MIN_SUPPORT = 500            # Mínimo trades para aprobar
MEMORY_WINDOW = 500          # Ventana por estrategia
```

**📖 [Ver configuración completa →](docs/guides/configuration.md)**

---

## 🛠️ Herramientas

### Descargar Datos

```bash
python utils/download_kline_dataset.py \
  --symbol BTCUSDT \
  --interval 15m \
  --limit 2000
```

### Actualizar Funding Rates

```bash
python utils/fetch_funding_rates.py --symbol BTCUSDT
```

### Testear Conexión (Live)

```bash
python3 -m utils.test_aster_connection --symbol BTCUSDT --interval 1m
```

---

## 🗺️ Roadmap

### ✅ Completado (v1.6)
- ✅ Arquitectura unificada main.py
- ✅ Multi-exchange testnet (Hyperliquid, Binance, Kraken)
- ✅ WebSocket integration completa
- ✅ 17 sensores técnicos activos
- ✅ Sistema de memoria bayesiano
- ✅ Risk management conservador
- ✅ Tests automatizados (14/14 passing)

### 🔜 Próximas Features (v1.7)
- **Multi-Asset Trading** - Múltiples criptos simultáneas
- **Portfolio Management** - Balance unificado across assets
- **Multi-Timeframe Analysis** - Análisis concurrente
- **Risk Diversification** - Gestión de correlación
- **Live Multi-Asset** - Trading simultáneo en testnet

**📖 [Roadmap v1.7 Completo →](docs/development/ROADMAP_V1.7.md)**

**📖 [Ver roadmap completo →](docs/development/PENDIENTES.md)**

---

## 🤝 Contribuir

¡Contribuciones bienvenidas!

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/mi-feature`
3. Commit cambios: `git commit -am 'Add mi feature'`
4. Push: `git push origin feature/mi-feature`
5. Abre un Pull Request

**📖 [Ver guía de contribución →](docs/development/contributing.md)**

---

## 📝 Changelog

**v1.6** (Actual)
- ✅ Arquitectura unificada main.py
- ✅ Multi-exchange testnet (3 exchanges)
- ✅ WebSocket integration completa
- ✅ 17 sensores técnicos implementados
- ✅ Sistema de memoria bayesiano funcional
- ✅ Risk management conservador probado

**📖 [Ver changelog completo →](docs/CHANGELOG.md)**

---

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para detalles.

---

## 🆘 Soporte

- 📖 [Documentación](docs/README.md)
- 🐛 [Issues](https://github.com/tu-usuario/Casino-V2/issues)
- 💬 [Discussions](https://github.com/tu-usuario/Casino-V2/discussions)

---

## 🧠 Filosofía

> **"La casa siempre gana… excepto cuando la estadística está de tu lado."** 🎲

Casino V2 no promete ganancias garantizadas. Es una herramienta para:
- Explorar trading probabilístico
- Aprender sobre gestión de riesgo
- Experimentar con estrategias
- Entender ventaja estadística

**🎡 Metáfora de la ruleta:**  
Imagina cada trade como apostar una ficha a rojo o negro. Cuando los sensores detectan un contexto con ventaja, Gemini autoriza la apuesta y los players deciden cuánto arriesgar. Si la jugada sale bien, ganas una ficha completa (menos costos); si sale mal, el stop loss devuelve media ficha y limitas el daño. Toda la arquitectura —sensores, memoria y gestión de tamaño— existe para encontrar esas “ruletas cargadas” donde la estadística se inclina a tu favor y las pérdidas quedan contenidas.

**⚠️ Advertencia:** Trading con riesgo real puede resultar en pérdidas. Usa paper trading primero.

---

<div align="center">

**🎰 Casino V2 - La Era Gemini**

*Desarrollado con ❤️ para traders cuantitativos*

[Documentación](docs/README.md) • [Quick Start](docs/guides/quickstart.md) • [Roadmap](docs/development/PENDIENTES.md)

</div>
