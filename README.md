# 🎰 Casino V2 — Trading Probabilístico

> Sistema de trading modular basado en ventaja estadística, no en predicción.

[![Version](https://img.shields.io/badge/Versión-1.6-blue)](docs/CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-14/14_passing-brightgreen)](test_phase1.py)


---

## 🚀 Quick Start

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar primer backtest
python main.py

# 3. Probar con Fixed Player
python main.py --player=fixed
```

**📖 [Guía completa de inicio →](docs/guides/quickstart.md)**

---

## 💡 ¿Qué es Casino V2?

Casino V2 es un **motor de trading probabilístico avanzado** diseñado para:

### **🎯 Visión Principal**
- **🎰 Multi-Asset Trading**: Operar múltiples criptomonedas simultáneamente en un mismo exchange
- **⏱️ Multi-Timeframe Analysis**: Analizar diferentes marcos temporales concurrentemente
- **🔄 Real-Time Processing**: Procesar flujos de velas en tiempo real para todas las parejas
- **🎯 Sensor-Driven Decisions**: Tomar decisiones de trading basadas en señales técnicas por activo
- **💰 Unified Risk Management**: Gestionar capital y riesgo de manera holística across assets

### **🔬 Enfoque Probabilístico**
- ✅ No intenta predecir el mercado
- ✅ Busca **contextos con ventaja estadística** (EV > 0)
- ✅ Apuesta solo cuando las probabilidades están a favor
- ✅ Aprende de la experiencia empírica

**Filosofía:**
> *"No se trata de ganar todas las manos, sino de apostar cuando la ventaja está del lado del jugador."*

**Estado Actual:** v1.6 - Arquitectura modular con WebSocket integration completada.

---

## ✨ Features

### Core
- ✅ **Arquitectura Modular** - Separación Gemini (validación) / Player (sizing)
- ✅ **Sistema de Memoria** - Aprende winrate por estrategia/contexto
- ✅ **Bucket System** - Clasifica contextos de mercado
- ✅ **Bayesian Inference** - Credibilidad estadística robusta
- ✅ **WebSocket Integration** - Datos en tiempo real para live trading

### Players Disponibles
- 🎮 **Kelly Player** - Kelly Criterion conservador (default)
- 🎮 **Fixed Player** - Tamaño fijo por trade
- 🎮 **Paroli Player** - Progresión 1-4-8 que ignora el edge de Gemini (apuesta mientras exista `side`)
- 🎮 **Custom Players** - Crea tu propia estrategia

### Trading
- 📊 **Backtesting Robusto** - Fees, slippage, funding, liquidaciones
- 📈 **Live Trading** - Binance, Kraken, Hyperliquid (paper/real con WebSocket)
- 👻 **GHOST Trades** - Entrena sin riesgo cuando no hay datos

### Análisis
- 📝 **Decision Logging** - Log detallado de cada decisión
- 📊 **Métricas por Estrategia** - Winrate, soporte, credibilidad
- 🔍 **Trazabilidad Completa** - Desde señal hasta resultado
- 📡 **WebSocket Monitoring** - Estado de conexiones y datos en tiempo real

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

## 🎭 Analogías del Casino

Casino V2 usa analogías del casino para explicar conceptos complejos de trading algorítmico de manera intuitiva:

### **1. 🎯 Jugador (Player)**
- **Analogía**: El apostador que decide cuánto arriesgar
- **Función Técnica**: Algoritmo de money management (Kelly, Fixed, etc.)
- **Responsabilidad**: Calcular `size_fraction` basado en equity disponible
- **Ejemplo**: "El jugador pide apostar 2% del bankroll"

### **2. 👁️ Gemini (Spotter/Observador)**
- **Analogía**: Spotter que vigila mesas y avisa cuándo están calientes
- **Función Técnica**: Sistema de aprendizaje que evalúa señales
- **Responsabilidad**: Generar `Verdict` con side y confidence
- **Ejemplo**: "Gemini dice 'la estrategia RSI en BTC está pagando bien'"

### **3. 🎲 Croupier (Router)**
- **Analogía**: El dealer que recibe órdenes del spotter y las enruta a la mesa apropiada
- **Función Técnica**: `croupier/croupier.py` - `route_order()`
- **Responsabilidad**: Enrutar órdenes al destino correcto
- **Ejemplo**: "El croupier toma la orden del spotter y la lleva a la mesa correcta"

### **4. 🪙 Mesa/Table (Ejecutor)**
- **Analogía**: La mesa específica donde se ejecuta la acción
- **Función Técnica**: `tables/table_*.py` - `execute_order()`
- **Responsabilidad**: Ejecutar órdenes y manejar posiciones
- **Ejemplo**: "La mesa recibe la orden del croupier y ejecuta la apuesta"

### **5. 🃏 Señales (Signals)**
- **Analogía**: Cartas que llegan a la mesa
- **Función Técnica**: Datos técnicos procesados por sensores
- **Ejemplo**: "Llegan cartas de RSI, MACD, Supertrend"

### **6. 💰 Fichas (Size Fraction)**
- **Analogía**: Cantidad de fichas apostadas
- **Función Técnica**: Porcentaje del equity a arriesgar
- **Ejemplo**: "Apostar 1% del bankroll = 1 ficha"

### **7. 📊 Verdict (Decisión del Spotter)**
- **Analogía**: Aviso del spotter sobre mesa caliente
- **Función Técnica**: `Verdict(side='BUY', confidence=0.8)`
- **Ejemplo**: "Verdict: BUY con 80% confidence"

### **8. 👻 Ghost Trades**
- **Analogía**: Carta que se registra pero no se juega
- **Función Técnica**: Trade simulado para aprendizaje
- **Ejemplo**: "Carta mala pero se registra para aprender"

### **9. 🏢 Pisos del Casino (Trading Modes)**
- **Analogía**: Diferentes pisos del casino con diferentes reglas y riesgos
- **Piso 1**: Ruleta Americana (Backtest) - simulación histórica, sin riesgo
- **Piso 2**: Ruleta Francesa (Paper Trading) - datos reales, sin dinero
- **Piso 3**: Ruleta Europea (Live Trading) - dinero real, máximo riesgo
- **Función Técnica**: `MODE` en config.py determina el piso

### **10. 🎰 Casino (Sistema Completo)**
- **Analogía**: El establecimiento completo de juegos
- **Función Técnica**: Todo el sistema de trading algorítmico
- **Ejemplo**: "El casino que combina spotters, jugadores, dealers y mesas"

### **11. 🎯 Sensores**
- **Analogía**: Los dados o ruletas que generan números aleatorios
- **Función Técnica**: Indicadores técnicos que generan señales
- **Ejemplo**: "Los dados tiran números, los sensores generan señales"

**📐 [Ver arquitectura completa →](docs/architecture/overview.md)**

---

## 📖 Documentación

### 🚀 Para Empezar
- [Quick Start](docs/guides/quickstart.md) - Primeros pasos en 5 minutos
- [Crear Players](docs/guides/creating-players.md) - Custom sizing strategies

### 🏗️ Arquitectura
- [Overview](docs/architecture/overview.md) - Visión general
- [Gemini/Player](docs/architecture/gemini-player.md) - Separación de responsabilidades
- [WebSocket Integration](docs/architecture/websocket-integration.md) - Datos en tiempo real

### 🛠️ Desarrollo
- [Developer Guide](DEVELOPER.md) - ⚠️ **OBLIGATORIO** para desarrolladores
- [Workflow](docs/workflow.md) - Cómo desarrollamos
- [Roadmap](docs/development/PENDIENTES.md) - Estado actual y features pendientes

---

## 🎯 Ejemplos

### Backtest Básico (Kelly Player)

```bash
python main.py
```

**Salida:**
```
🎰 CASINO V2 - BACKTEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance final: 10,542.33 USDT (+5.42%)
🏆 Winrate: 57.6%
⚙️ Trades: 182 (155 BET + 27 GHOST)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Backtest con Fixed Player

```bash
python main.py --player=fixed
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

**📖 [Ver ejemplos de configuración en el código →](config.py)**

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


**📖 [Ver roadmap completo →](docs/development/PENDIENTES.md)**

---

## 🤝 Contribuir

¡Contribuciones bienvenidas!

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/mi-feature`
3. Commit cambios: `git commit -am 'Add mi feature'`
4. Push: `git push origin feature/mi-feature`
5. Abre un Pull Request

**📖 [Ver ejemplos en el código y tests →](test_phase1.py)**

---

## 📝 Changelog

**v1.6** (Actual - WebSocket Integration)
- ✅ WebSocket integration completa para live trading
- ✅ Soporte multi-exchange (Binance, Kraken, Hyperliquid)
- ✅ 17 sensores técnicos implementados y activos
- ✅ Arquitectura modular con PositionTracker
- ✅ Tests automatizados (14/14 + WebSocket)

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
Cada trade es como apostar a rojo o negro en una ruleta. Los sensores detectan contextos con ventaja estadística, Gemini autoriza la apuesta, los players deciden cuánto arriesgar. Si sale bien, ganas (menos costos); si sale mal, el stop loss limita el daño. El sistema busca "ruletas cargadas" donde la estadística favorece al jugador.

**⚠️ Advertencia:** Trading con riesgo real puede resultar en pérdidas. Usa paper trading primero.

---

<div align="center">

**🎰 Casino V2 - La Era Gemini**

*Desarrollado con ❤️ para traders cuantitativos*

[Documentación](docs/README.md) • [Quick Start](docs/guides/quickstart.md) • [Roadmap](docs/development/PENDIENTES.md)

</div>
