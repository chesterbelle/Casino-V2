# 🎰 Casino V2 — Trading Probabilístico

> Sistema de trading modular basado en ventaja estadística, no en predicción.

[![Version](https://img.shields.io/badge/Versión-0.1.2-blue)](docs/CHANGELOG.md)
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
- 📈 **Live Trading** - Binance, Kraken, ASTERDEx (paper/real)
- 👻 **GHOST Trades** - Entrena sin riesgo cuando no hay datos

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
- [Quick Start](docs/guides/quickstart.md) - Primeros pasos en 5 minutos
- [Crear Players](docs/guides/creating-players.md) - Custom sizing strategies

### 🏗️ Arquitectura
- [Overview](docs/architecture/overview.md) - Visión general
- [Gemini/Player](docs/architecture/gemini-player.md) - Separación de responsabilidades

### 🛠️ Desarrollo
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

**v0.1.2** (Actual)
- ✅ Mejoras de calidad de código (3 fixes)
- ✅ Migración a arquitectura modular
- ✅ Tests actualizados (14/14)

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
