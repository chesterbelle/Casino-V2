# 🎰 VISIÓN - Casino V2

> **La Biblia del Proyecto**
>

MANUAL DE INGENIERÍA PARA LLMs (IA) - CASINO V2

Este documento establece el marco de referencia y los principios arquitectónicos esenciales de Casino V2. Cualquier sugerencia o modificación de código debe respetar la Filosofía de Probabilidad y la Separación de Responsabilidades Modular.

1. 🎯 PRINCIPIO FUNDAMENTAL: SIMULACIÓN DE JUEGO CON VENTAJA TÁCTICA

El principio central de Casino V2 no es solo buscar el EV>0, sino la simulación de un juego de azar (Ruleta) utilizando el Perpetual Trading para explotar dos ventajas críticas que son imposibles en un casino físico: 1) Identificación de Alpha y 2) Ausencia de Límites de Apuesta.

Mapeo de Componentes Ruleta → Perpetual Trading

La justificación arquitectónica reside en la capacidad de mapear las reglas del juego de la ruleta a la ejecución del perpetual trading mediante la manipulación de las órdenes:

    La Ruleta (El Juego): El perpetual trading se usa como el mecanismo de apuesta. Cada vela o unidad de tiempo se considera una ronda de apuesta.

    Apuesta Simple (1:1): La simulación de un pago simple (1 a 1) se logra al configurar estratégicamente el Take Profit (TP) y el Stop Loss (SL) a distancias idénticas del precio de entrada. Si el precio toca el TP, se gana; si toca el SL, se pierde (simulando una apuesta 1 a 1 modificada).

    La Banca Ilimitada: La ausencia de límites de apuesta en el perpetual trading (más allá del margin disponible) es crucial, ya que permite la implementación rigurosa de sistemas de apuestas progresivas (ej., Paroli) que requieren la posibilidad de aumentar exponencialmente el tamaño de la apuesta, algo inviable en casinos tradicionales con límites de mesa.

Ventajas Operativas Clave

    Inyección de Alpha (Análisis Técnico): A diferencia de la ruleta física, donde P(Eˊxito)=48.6% (debido al cero verde, una desventaja constante para el jugador), el mercado financiero exhibe patrones analizables. Gemini y los Sensores existen únicamente para identificar contextos donde P(Eˊxito) puede ser temporalmente manipulada por encima del 50%. Este es el origen del EV>0.

    Modelos Avanzados de Sizing: La capacidad de ignorar los límites de apuesta del casino permite al Player implementar lógicas de gestión de capital agresivas (ej., Criterio de Kelly, Progresión Paroli) para optimizar el crecimiento compuesto del equity a tasas que la gestión de riesgo tradicional no permite.

2. 🧱 ARQUITECTURA: SEPARACIÓN DE RESPONSABILIDADES

La arquitectura se mantiene modular para aislar el alpha (Gemini) del riesgo (Croupier) y de la ejecución (Mesa), manteniendo la integridad del sistema.

A. Capa de Decisión (Alpha) y Aprendizaje

    GEMINI (El Oráculo): Motor de Decisión probabilística. Evalúa las señales de los Sensores y la Memoria para emitir un Verdict (action+confidence).

    Los Sensores: Módulos de Detección de Patrones. Transforman los datos OHLCV en señales técnicas. Proveen el input para la decisión de Gemini.

    El Bucket y La Memoria: Sistema de Aprendizaje Bayesiano. Clasifica el contexto de mercado en un Bucket para guardar el winrate histórico y ajustar la confianza de Gemini.

B. Capa de Riesgo y Financiera

    EL PLAYER (Jugador): Estrategia de Position Sizing. Recibe el Verdict y calcula la fracción del equity a arriesgar (tamaño de la apuesta).

    EL CROUPIER: Gestor de Órdenes y Riesgo (Compliance). Valida que la orden del Player sea posible (balance, límites) antes de enviarla a La Mesa.

C. Capa de Ejecución y Mercado

    LA MESA (Table): Interfaz de Input/Output (I/O) con el exchange. Maneja la conectividad, obtiene datos OHLCV y ejecuta las órdenes físicas.

3. ⚙️ REGLAS DE ORO PARA EL DESARROLLO (IA)

    Separación de Lógica: La lógica de riesgo en croupier/croupier.py. La lógica de sizing en players/*_player.py. NO mezclar el alpha (Gemini) con la lógica financiera (Player).

    Inmutabilidad del Verdict: El Verdict de Gemini debe ser un objeto inmutable que se pasa al Player y al Croupier. Ningún componente intermedio debe modificar la acción o la confianza asignada.

    Objetivo de Optimización: Las optimizaciones deben dirigirse a aumentar P(Eˊxito) dentro de un Bucket o a reducir el drawdown, manteniendo el foco en la ventaja estadística a largo plazo.
---

## 🎰 LAS ANALOGÍAS: Nuestro Lenguaje

### **¿Por Qué Usamos Analogías de Casino?**

Porque:
1. **Son intuitivas** - Todos entienden qué hace un croupier
2. **Separan responsabilidades** - Cada rol tiene una función clara
3. **Evitan confusión técnica** - "Player" es más claro que "PositionSizingStrategy"
4. **Mantienen la filosofía viva** - Recordamos constantemente que es probabilístico
5. **Facilitan la comunicación** - Pedro y Cascade hablan el mismo idioma

**Importante**: No son solo nombres bonitos. Cada analogía representa un concepto fundamental del sistema.

---

## 🎲 LA MESA (DataSource)

### **En un Casino Real**
La mesa es el espacio físico donde se juega, donde están las fichas (el dinero), donde el croupier trabaja, donde sucede toda la acción.

### **En Casino V2**
**La Mesa es la fuente de datos y ejecución de órdenes.** Es el "mundo" donde se obtienen velas, se ejecutan órdenes, está el balance y las posiciones.

### **Arquitectura v2.0: DataSource**

A partir de v2.0, la Mesa se implementa como una **clase abstracta `DataSource`** con 3 tipos de mesa intercambiables:

```
DataSource (Plantilla abstracta)
├── next_candle() → Obtiene siguiente vela
├── execute_order() → Ejecuta orden
├── get_balance() → Balance disponible
├── get_equity() → Equity total
├── connect() → Conecta a la fuente
└── disconnect() → Desconecta

         ↓ Implementado por ↓

┌────────────────────┬────────────────────┬────────────────────┐
│  BacktestDataSource│ TestingDataSource  │  LiveDataSource    │
├────────────────────┼────────────────────┼────────────────────┤
│ Mesa de Práctica   │ Mesa Demo          │ Mesa Real          │
│ - Lee CSV/Parquet  │ - Exchange demo    │ - Exchange real    │
│ - Simula TP/SL     │ - Dinero virtual   │ - Dinero real      │
│ - Sin riesgo       │ - Pruebas seguras  │ - Producción       │
│ - Instant replay   │ - WebSocket real   │ - WebSocket real   │
└────────────────────┴────────────────────┴────────────────────┘
```

### **Por Qué se Llama Así**
Porque es el **espacio donde todo sucede**. Sin mesa, no hay juego. Es donde las decisiones se vuelven realidad.

### **Qué Hace Cada Tipo de Mesa**

#### **BacktestDataSource** (Mesa de Práctica)
- Carga datos históricos (CSV, Parquet)
- Simula ejecución de órdenes con slippage/fees
- Simula TP/SL usando high/low de velas
- Tracking de balance y posiciones en memoria
- Ejecución instantánea (sin delays)

**Archivo**: `core/data_sources/backtest.py`

#### **TestingDataSource** (Mesa Demo)
- Conecta a exchange en modo demo (Kraken Demo)
- Usa `TableCCXTPro` + `KrakenConnector` internamente
- Dinero virtual, riesgo cero
- WebSocket real para datos en vivo
- Ejecución real en testnet

**Archivo**: `core/data_sources/testing.py`

#### **LiveDataSource** (Mesa Real)
- Conecta a exchange en modo producción
- Usa `TableCCXTPro` + `KrakenConnector` internamente
- Dinero real, riesgo real
- WebSocket real para datos en vivo
- Ejecución real en mainnet

**Archivo**: `core/data_sources/live.py`

### **Conectores y Adaptadores**

Las mesas `TestingDataSource` y `LiveDataSource` usan internamente:

```
TestingDataSource / LiveDataSource
         ↓
    TableCCXTPro (Wrapper CCXT)
    ├── Balance management
    ├── Position tracking
    ├── Order validation
    ├── TP/SL logic
    └── Logging
         ↓
    KrakenConnector (Adaptador específico)
    ├── connect()
    ├── fetch_ohlcv()
    ├── fetch_balance()
    ├── create_order()
    └── close()
         ↓
    CCXT Library → Exchange API
```

**Archivos**:
- `tables/table_ccxt_pro.py` - Wrapper CCXT (lógica de negocio)
- `tables/connectors/kraken_connector.py` - Adaptador Kraken (driver específico)

### **Ventajas de la Arquitectura DataSource**

1. **Mismo código, diferentes mesas** - `TradingSession` funciona con cualquier tipo
2. **Testeo seguro** - Backtest → Testing → Live (progresión segura)
3. **Modularidad** - Fácil agregar nuevos exchanges o fuentes
4. **Inmutabilidad** - Interfaz consistente garantiza comportamiento predecible

---

## 🎩 EL CROUPIER

### **En un Casino Real**
El croupier gestiona el juego, valida las apuestas, ejecuta el juego, paga premios, mantiene el orden, aplica las reglas de la casa.

### **En Casino V2**
**El Croupier es el gestor de órdenes y riesgo.** Es el "guardián" que valida, gestiona, aplica reglas, mantiene registro.

### **Por Qué se Llama Así**
Tiene las **mismas responsabilidades** que un croupier real:
- Valida apuestas → Valida balance suficiente
- Gestiona el juego → Gestiona ejecución de órdenes
- Aplica reglas → Aplica límites de riesgo
- Mantiene orden → Logging y registro

### **Qué Hace**
1. Recibir decisión del Player
2. Validar que es posible (balance, límites)
3. Crear la orden correctamente
4. Ejecutarla en la Mesa
5. Registrar el resultado

**Archivo**: `croupier/croupier.py`

---

## 🎮 EL PLAYER (Jugador)

### **En un Casino Real**
El jugador decide cuánto apostar en cada mano, tiene una estrategia, gestiona su bankroll, busca maximizar ganancias minimizando riesgo.

### **En Casino V2**
**El Player es la estrategia de position sizing.** Es el "cerebro financiero" que decide cuánto del capital arriesgar.

### **Por Qué se Llama Así**
Es literalmente el **jugador** que apuesta, tiene estrategia, gestiona bankroll, busca optimizar.

### **Qué Hace**
Recibe un Verdict de Gemini (BUY/SELL + confianza) y calcula cuánto del equity apostar (fracción 0.0 - 1.0).

**Tipos**:
- **Kelly Player** (agresivo) - Kelly Criterion, maximiza crecimiento
- **Paroli Player** (conservador) - Progresión positiva
- **Fixed Player** (simple) - Tamaño fijo

**Archivos**: `players/kelly_player.py`, `players/paroli_player.py`, `players/fixed_player.py`

---

## 🔮 GEMINI (El Oráculo)

### **En un Casino Real**
No existe, pero sería el "sistema" que dice cuándo las probabilidades están a favor, el que cuenta cartas, el que detecta patrones.

### **En Casino V2**
**Gemini es el motor de decisión probabilística.** Es el "cerebro estratégico" que analiza, detecta ventaja, decide, asigna confianza.

### **Por Qué se Llama Gemini**
**Gemini** = Géminis = **Dualidad**. Representa la dualidad del mercado (alcista/bajista, compra/venta), decisiones binarias con matices.

### **Qué Hace**
1. Recibir señales de Sensores
2. Evaluar ventaja estadística
3. Decidir: BUY, SELL, o HOLD
4. Asignar confianza (0.0 - 1.0)
5. Aprender de resultados (memoria bayesiana)

**Archivo**: `gemini/gemini_core.py`
**Memoria**: `gemini/memory.py`

---

## 👁️ LOS SENSORES

### **En un Casino Real**
Los ojos del jugador profesional que cuenta cartas o busca patrones.

### **En Casino V2**
**Detectores de patrones técnicos.** Son los "ojos" que observan el mercado, detectan señales, identifican patrones.

### **Por Qué se Llaman Así**
Literalmente **"sienten" el mercado**. Cada sensor especializado en algo (RSI, MACD, etc.).

### **Qué Hacen**
1. Recibir velas OHLCV
2. Calcular indicadores técnicos
3. Detectar patrones
4. Generar señales (BUY/SELL/NEUTRAL)
5. Enviar señales a Gemini

**Archivos**: `sensors/momentum_trend_following/sensor_*.py`, `sensors/sensor_manager.py`

---

## 🎯 EL VERDICT (Veredicto)

**El Verdict es la decisión final de Gemini.** Dice QUÉ hacer, QUÉ TAN seguro estamos, y POR QUÉ.

**Estructura**:
```python
Verdict(
    action="BUY" | "SELL" | "HOLD",
    confidence=0.75,  # 0.0 - 1.0
    meta={"bucket": "...", "signals": {...}}
)
```

**Por Qué es Importante**: Separa la decisión (Gemini) del sizing (Player).

---

## 🪣 EL BUCKET (Cubo/Contexto)

**Un Bucket es una clasificación de contextos de mercado.** Agrupa situaciones similares para aprender winrate por tipo de contexto.

**Ejemplo**: "Mercado alcista + alta volatilidad + RSI sobreventa" = un bucket específico.

**Qué Hace**:
1. Gemini clasifica cada situación en un bucket
2. Memoria guarda winrate por bucket
3. Gemini ajusta confianza basado en historial

**Archivo**: `gemini/memory.py`

---

## 🔄 EL FLUJO COMPLETO: La Partida (v2.0)

```
1. LA MESA (DataSource) entrega vela
   → BacktestDataSource: Lee del CSV
   → TestingDataSource: Fetch de Kraken Demo
   → LiveDataSource: Fetch de Kraken Real
   ↓
2. PIPELINE procesa vela (4 stages)
   ↓
   2.1 ProcessSignalsStage
       → Sensores analizan vela
       → RSI=30, MACD=cruce alcista, etc.
       → Genera señales
   ↓
   2.2 EvaluateStage (Gemini)
       → Evalúa señales
       → Decide: Verdict(BUY, confidence=0.75)
       → Clasifica en bucket, consulta memoria
   ↓
   2.3 BuildOrderStage (Player)
       → Recibe Verdict + equity
       → Calcula size: 0.015 (1.5% del equity)
       → Construye orden: {symbol, side, amount, tp, sl}
   ↓
   2.4 ExecuteStage
       → Valida balance y límites (Croupier)
       → Ejecuta en la Mesa (DataSource)
   ↓
3. LA MESA ejecuta orden
   → BacktestDataSource: Simula ejecución
   → TestingDataSource: Envía a Kraken Demo
   → LiveDataSource: Envía a Kraken Real
   ↓
4. TODO SE REGISTRA
   → Logs para auditoría
   → Memoria para aprendizaje
```

---

## 💬 DICCIONARIO PEDRO-CASCADE

| Pedro dice | Cascade entiende |
|------------|------------------|
| "Mejora el Croupier" | Modificar `croupier/croupier.py` |
| "La Mesa no conecta" | Problema en `core/data_sources/*.py` o `tables/table_*.py` |
| "Mesa de Backtest" | `BacktestDataSource` en `core/data_sources/backtest.py` |
| "Mesa Demo/Testing" | `TestingDataSource` en `core/data_sources/testing.py` |
| "Mesa Real/Live" | `LiveDataSource` en `core/data_sources/live.py` |
| "Gemini no decide bien" | Revisar `gemini/gemini_core.py` |
| "El Player apuesta mucho" | Ajustar `players/*_player.py` |
| "Los Sensores fallan" | Revisar `sensors/*/sensor_*.py` |
| "Backtest" | Modo simulación (`BacktestDataSource`) |
| "Testing" | Modo demo (`TestingDataSource`) |
| "Live" | Modo real (`LiveDataSource`) |
| "Kelly" | Kelly Player (agresivo) |
| "Paroli" | Paroli Player (conservador) |
| "El Verdict" | Decisión de Gemini |
| "El Bucket" | Clasificación de contexto |
| "La Memoria" | Sistema bayesiano de aprendizaje |
| "DataSource" | La Mesa (plantilla abstracta) |
| "TableCCXTPro" | Wrapper CCXT (usado por Testing/Live) |
| "KrakenConnector" | Adaptador específico de Kraken |

---

## 🎯 VISIÓN A FUTURO

### *versión actual* **v1.9.1 —
-esta version no agregara funcionalidad nueva pero esta pensada para debugear errores de logica  y limpieza de codigo
-verificacion de logica de los jugadores kelly y paroli y actualizacion de sus docstrings
-verificacion de la logica de GEMiNI
- dejar el modo backtesting lo mas blindando posible para que nos de el rendimiento mas cercano a la realidad(esta es la prioridad de la version)


### **v2.0 Multi-Timeframe** 🔮
- Implementar `HyperliquidConnector`
- Soporte para múltiples timeframes simultáneos (1m, 5m, 1h, 4h)
- Decisiones más robustas con múltiples perspectivas temporales

### **v2.1 - Multi-Assets** 🚀
- Capacidad de rotar entre diferentes assets
- Portfolio management
- Correlación entre assets

### **v2.2 - Adaptive Gemini** 🧠
- Gemini mejorado que aprende patrones nuevos
- Adaptación dinámica a condiciones de mercado

---

## 📋 REGLAS DE ORO

1. **No Predecimos** - Buscamos ventaja estadística
2. **Separación de Responsabilidades** - Cada componente hace UNA cosa
3. **Aprendizaje Continuo** - La Memoria mejora con cada trade
4. **Tests Obligatorios** - Si cambias código, tests deben pasar
5. **Las Analogías Importan** - Mantienen la filosofía clara
6. **Consistencia > Perfección** - Largo plazo es lo que importa

---

## 📁 ESTRUCTURA DE CARPETAS

### **Regla de Oro**: Cada cosa en su lugar

```
Casino-V2/
├── core/                      # Configuración y núcleo del sistema
│   ├── config.py             # Configuración global (parámetros)
│   ├── version.py            # Versión única del proyecto
│   ├── data_sources/         # 🎲 LAS MESAS (DataSource)
│   │   ├── base.py          # Plantilla abstracta DataSource
│   │   ├── backtest.py      # BacktestDataSource (mesa práctica)
│   │   ├── testing.py       # TestingDataSource (mesa demo)
│   │   └── live.py          # LiveDataSource (mesa real)
│   └── trading/              # 🎯 PIPELINE Y SESIÓN
│       ├── context.py        # TradingContext (estado inmutable)
│       ├── pipeline.py       # Pipeline (orquestador)
│       ├── session.py        # TradingSession (sesión unificada)
│       └── stages/           # Etapas del pipeline
│           ├── process_signals.py  # 1️⃣ Detecta señales
│           ├── evaluate.py         # 2️⃣ Gemini evalúa
│           ├── build_order.py      # 3️⃣ Player construye
│           └── execute.py          # 4️⃣ Ejecuta en mesa
│
├── gemini/                    # Motor de decisión (Gemini)
│   ├── gemini_core.py        # Lógica principal de decisión
│   ├── memory.py             # Sistema bayesiano de aprendizaje
│   ├── bucket_manager.py     # Clasificación de contextos
│   ├── decision_logger.py    # Logging de decisiones
│   └── data/                 # Datos de memoria (winrates, etc.)
│
├── players/                   # Estrategias de position sizing
│   ├── kelly_player.py       # Kelly Criterion (agresivo)
│   ├── paroli_player.py      # Paroli (conservador)
│   └── fixed_player.py       # Tamaño fijo (testing)
│
├── croupier/                  # Gestor de órdenes y riesgo
│   └── croupier.py           # Validación y ejecución de órdenes
│
├── tables/                    # Conectores y adaptadores CCXT
│   ├── table_ccxt_pro.py     # Wrapper CCXT (usado por Testing/Live)
│   ├── connectors/           # Adaptadores específicos de exchanges
│   │   ├── kraken_connector.py    # Driver Kraken
│   │   └── resilient_connector.py # Wrapper con resiliencia
│   ├── balance_manager.py    # Gestión de balance
│   ├── position_tracker.py   # Seguimiento de posiciones
│   ├── exchange_state_sync.py # Sincronización con exchange
│   └── data/                 # Datos históricos para backtest
│
├── sensors/                   # Detectores de señales técnicas
│   ├── sensor_manager.py     # Coordinador de sensores
│   ├── momentum_trend_following/  # Sensores de momentum
│   │   ├── sensor_rsi.py
│   │   ├── sensor_macd.py
│   │   └── ...
│   ├── mean_reversion/       # Sensores de reversión
│   ├── fractales/            # Sensores de fractales
│   └── volumen_flujo_capital/  # Sensores de volumen
│
├── utils/                     # Utilidades y herramientas (van a producción)
│   ├── exchanges/            # Cargadores de credenciales por exchange
│   │   ├── kraken_env_loader.py
│   │   ├── binance_env_loader.py
│   │   └── hyperliquid_env_loader.py
│   ├── analysis/             # Herramientas de análisis
│   ├── data/                 # Utilidades de datos
│   ├── training/             # Herramientas de entrenamiento
│   └── diagnose_sync.py      # Diagnóstico de sincronización
│
├── tests/                     # Tests unitarios (NO van a producción)
│   ├── test_phase1.py        # Tests básicos del sistema
│   ├── test_gemini.py        # Tests de Gemini
│   ├── test_players.py       # Tests de Players
│   └── test_exchange_sync.py # Tests de sincronización
│
├── logs/                      # Logs de ejecución
│   ├── decisions/            # Logs de decisiones de Gemini
│   ├── trades/               # Logs de trades ejecutados
│   └── system/               # Logs del sistema
│
└── docs/                      # Documentación
    ├── VISION.md             # 🔥 LA BIBLIA (este archivo)
    ├── CHANGELOG.md          # Historial de cambios
    ├── NUEVA_ARQUITECTURA_v2.0.md  # Arquitectura v2.0
    └── reports/              # Reportes de implementación
```

### **Dónde poner cada tipo de archivo**

| Tipo de archivo | Carpeta | Ejemplo |
|-----------------|---------|---------|
| **Configuración global** | `core/` | `config.py`, `version.py` |
| **Mesas (DataSource)** | `core/data_sources/` | `backtest.py`, `testing.py`, `live.py` |
| **Pipeline y sesión** | `core/trading/` | `session.py`, `pipeline.py`, `context.py` |
| **Stages del pipeline** | `core/trading/stages/` | `evaluate.py`, `build_order.py` |
| **Lógica de decisión** | `gemini/` | `gemini_core.py`, `memory.py` |
| **Estrategias de sizing** | `players/` | `kelly_player.py` |
| **Gestión de órdenes** | `croupier/` | `croupier.py` |
| **Conectores CCXT** | `tables/` | `table_ccxt_pro.py` |
| **Adaptadores exchanges** | `tables/connectors/` | `kraken_connector.py` |
| **Detectores técnicos** | `sensors/` | `sensor_rsi.py` |
| **Credenciales de exchanges** | `utils/exchanges/` | `kraken_env_loader.py` |
| **Herramientas de análisis** | `utils/analysis/` | Análisis de resultados |
| **Scripts de mantenimiento** | `utils/` | `diagnose_sync.py` |
| **Tests** | `tests/` | `test_gemini.py` |
| **Documentación** | `docs/` | `VISION.md`, `ROADMAP.md` |

### **⚠️ Errores comunes a evitar**

❌ **NO poner tests en `utils/`** - Los tests van en `tests/` (no se despliegan)
❌ **NO poner scripts en raíz** - Los scripts van en `utils/`
❌ **NO mezclar lógica de negocio en `utils/`** - Utils es solo para utilidades
❌ **NO poner configuración en múltiples lugares** - Solo en `core/config.py`
❌ **NO crear carpeta `scripts/`** - Ya no existe, todo va en `utils/`

### **✅ Reglas de organización**

1. **Un archivo, una responsabilidad** - No mezclar conceptos
2. **Carpetas por función, no por tipo** - `gemini/` agrupa todo de Gemini
3. **Tests reflejan estructura** - `tests/test_gemini.py` para `gemini/gemini_core.py`
4. **Datos cerca de quien los usa** - `gemini/data/` para datos de Gemini
5. **Utils solo para código reutilizable** - No lógica de negocio

---

## 🔧 REFERENCIA TÉCNICA

### **Archivos Críticos**
- `core/config.py` - Configuración global
- `core/version.py` - Versión única
- `core/data_sources/base.py` - Plantilla DataSource (La Mesa)
- `core/trading/session.py` - TradingSession unificada
- `core/trading/pipeline.py` - Pipeline modular
- `gemini/gemini_core.py` - Motor de decisión
- `tables/table_ccxt_pro.py` - Wrapper CCXT (usado por Testing/Live)
- `croupier/croupier.py` - Gestión de órdenes
- `gemini/memory.py` - Aprendizaje bayesiano

### **Configuración (core/config.py)**
```python
MODE = "backtest" | "live"
EXCHANGE = "KRAKEN_DEMO" | "BINANCE_TESTNET" | "HYPERLIQUID"
PLAYER_TYPE = "kelly" | "paroli" | "fixed"
SYMBOL = "BTC/USD"
TIMEFRAME = "1m" | "5m" | "15m" | "1h"
```

---

## 🔄 PRINCIPIO DE SINCRONIZACIÓN (v1.9.1+)

### **Regla de Oro: El Sistema NUNCA Debe Operar con Supuestos**

A partir de v1.9.1, Casino V2 implementa sincronización de estado real del exchange para garantizar que todas las decisiones se basen en datos confirmados, no aproximados.

### **Estado Rico del Exchange**

El sistema ahora obtiene y utiliza:

1. **Balance Real**: Obtenido directamente del exchange, no estimado
2. **Equity Real**: `balance + unrealized_pnl` de posiciones abiertas
3. **Fills Confirmados**: Solo aprender de trades ejecutados realmente
4. **Precios Reales**: Usar precios de fill, no precios de vela
5. **Posiciones Verificadas**: Sincronizadas con el exchange

### **Arquitectura de Sincronización**

```
Exchange (Fuente de Verdad)
    ↓ REST API / WebSocket
ExchangeStateSync (Sincronizador)
    ↓ Estado real confirmado
TableCCXTPro (Mesa enriquecida)
    ↓ Vela + equity real + fills confirmados
Gemini + Players (Decisiones informadas)
```

### **Componentes de Sincronización**

#### **ExchangeStateSync**
Componente que sincroniza estado real del exchange:
- `sync_equity()` → Balance + unrealized PnL = Equity real
- `sync_positions()` → Posiciones abiertas/cerradas verificadas
- `sync_fills(since)` → Fills confirmados desde timestamp

#### **PositionTracker Modo Híbrido**
Sistema de confirmación de cierres en 3 modos:
- **simulation**: Simula cierres con OHLC (backtest)
- **confirmed**: Solo cierra con confirmación del exchange (live estricto)
- **hybrid**: Detecta TP/SL + espera confirmación (recomendado)

#### **Vela Enriquecida**
`TableCCXTPro.next_candle()` ahora retorna:
```python
{
    # OHLCV (como antes)
    "timestamp": ...,
    "open": ..., "high": ..., "low": ..., "close": ...,

    # NUEVO: Estado real del exchange
    "equity": float,  # balance + unrealized_pnl (REAL)
    "balance": float,  # balance libre (REAL)
    "unrealized_pnl": float,  # PnL no realizado (REAL)
    "positions": List[Position],  # Posiciones reales
    "recent_fills": List[Fill],  # Fills confirmados
    "state_source": "exchange_confirmed"  # FLAG
}
```

### **Impacto en Componentes**

#### **Gemini**
- Recibe equity REAL para calcular métricas
- Aprende de cierres CONFIRMADOS por el exchange
- `Verdict` basado en datos verificados

#### **Players**
- Calculan sizing con equity REAL (no aproximado)
- Kelly Criterion usa equity confirmado
- Paroli opera sobre balance real

#### **PositionTracker**
- Detecta TP/SL tocados (simulación rápida)
- Marca como "PENDING_CONFIRMATION"
- Confirma con `confirm_close()` usando datos reales del exchange

### **Ejemplo de Flujo**

**Antes (v1.9)**:
```
Vela: high=50200
TP level: 50100
Sistema: "TP tocado @ 50100" (teórico)
Cierra inmediatamente
PnL: +100 USD (calculado)
Gemini aprende: "WIN @ 50100"
```

**Después (v1.9.1)**:
```
Vela: high=50200
TP level: 50100
Sistema: "TP detectado @ 50100" (teórico)
Marca como PENDING
Espera fill del exchange...
Fill confirmado: precio=50150, fee=2.5, pnl=+147.5
Confirma cierre con datos REALES
PnL: +147.5 USD (confirmado)
Gemini aprende: "WIN @ 50150" (REAL)
```

### **Métricas de Sincronización**

El sistema mantiene métricas de sincronización:
- Balance diff: < 1% (target)
- Equity diff: < 1% (target)
- Fills confirmados: 100%
- Precios reales: 100%

### **Herramientas de Diagnóstico**

`utils/diagnose_sync.py` - Script para medir desincronización:
```bash
python utils/diagnose_sync.py
```

Compara estado interno vs exchange y genera reporte con recomendaciones.

---

**Este documento es la BIBLIA del proyecto.**
**Sin entender esto, no se puede trabajar en Casino V2.**

**Última actualización**: 2025-11-03 (v1.9.1)
**Autor**: Pedro + Cascade
**Para**: Cascade y cualquier IA que trabaje en el proyecto
