# 🎰 Casino V2 - Arquitectura Unificada
## Guía Rápida con Analogías

---

## 🎯 ¿Qué pasó con la Mesa?

### **RESPUESTA CORTA**:
**La Mesa sigue existiendo**, pero ahora se llama **`DataSource`** y es intercambiable.

### **ANTES (v1.9.1)**:
```
Casino Real (Live)
├── Mesa Real (TableCCXTPro) ← Única mesa, acoplada al código
├── Croupier
├── Gemini
└── Player (Paroli)
```

### **AHORA (v2.0)**:
```
Casino Moderno (TradingSession)
├── Mesa Intercambiable (DataSource) ← ¡3 tipos de mesa!
│   ├── Mesa de Práctica (BacktestDataSource) ← Datos históricos
│   ├── Mesa Demo (TestingDataSource) ← Exchange demo
│   └── Mesa Real (LiveDataSource) ← Exchange real
├── Pipeline (flujo unificado)
│   ├── ProcessSignalsStage (sensores)
│   ├── EvaluateStage (Gemini)
│   ├── BuildOrderStage (Player)
│   └── ExecuteStage (ejecuta en la mesa)
└── Player (Paroli)
```

---

## 🏛️ Analogía del Casino

### **Concepto de "Mesa"**

Imagina un casino real:

#### **ANTES**: Un solo tipo de mesa
```
🎰 Casino V1.9.1
   └── 🎲 Mesa de Póker Real
       ├── Fichas reales ($$$)
       ├── Croupier real
       └── Solo puedes jugar con dinero real
```

#### **AHORA**: Múltiples tipos de mesa con la misma interfaz
```
🎰 Casino V2.0
   ├── 📚 Mesa de Práctica (Backtest)
   │   ├── Fichas de papel
   │   ├── Datos históricos
   │   └── Aprendes sin riesgo
   │
   ├── 🎮 Mesa Demo (Testing)
   │   ├── Fichas virtuales
   │   ├── Croupier de práctica
   │   └── Simula el casino real
   │
   └── 💰 Mesa Real (Live)
       ├── Fichas reales ($$$)
       ├── Croupier real
       └── Dinero de verdad
```

**TODAS LAS MESAS TIENEN LA MISMA INTERFAZ**:
- `next_candle()` → Dame la siguiente carta/vela
- `execute_order()` → Ejecuta mi apuesta
- `get_balance()` → ¿Cuánto dinero tengo?
- `get_equity()` → ¿Cuánto valgo en total?

---

## 📊 Diagrama de Flujo: ¿Cómo Funciona?

```
┌─────────────────────────────────────────────────────────────┐
│                    🎰 CASINO V2.0                           │
│                  (TradingSession)                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   Selecciona tipo de Mesa         │
        │   (DataSource)                    │
        └───────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 📚 Backtest  │    │ 🎮 Testing   │    │ 💰 Live      │
│              │    │              │    │              │
│ CSV/Parquet  │    │ Kraken Demo  │    │ Kraken Real  │
│ Simula TP/SL │    │ WebSocket    │    │ WebSocket    │
│ Sin riesgo   │    │ Fichas fake  │    │ Dinero real  │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   🎯 PIPELINE UNIFICADO           │
        │   (Mismo flujo para todas)        │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  1️⃣ ProcessSignalsStage          │
        │     📡 Sensores detectan señales  │
        │     (RSI, MACD, ADX, etc.)        │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  2️⃣ EvaluateStage                │
        │     🧠 Gemini evalúa señales      │
        │     → BET / GHOST / SKIP          │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  3️⃣ BuildOrderStage               │
        │     🎲 Player calcula tamaño      │
        │     (Paroli ignora Gemini)        │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  4️⃣ ExecuteStage                  │
        │     ⚡ Ejecuta en la Mesa          │
        │     (DataSource.execute_order)    │
        └───────────────────────────────────┘
                            │
                            ▼
                    ┌───────────┐
                    │  Resultado │
                    │  WIN/LOSS  │
                    └───────────┘
```

---

## 🔄 Flujo Detallado: Una Vela

```
INICIO: Nueva vela llega
│
├─► 📚 Mesa (DataSource) entrega vela
│   │
│   ├─ Backtest: Lee del CSV
│   ├─ Testing: Fetch de Kraken Demo
│   └─ Live: Fetch de Kraken Real
│
├─► 🎯 Pipeline procesa vela
│   │
│   ├─► 1️⃣ ProcessSignalsStage
│   │   └─ Sensores analizan vela
│   │      └─ Señales: [{side: LONG, origin: RSI}, ...]
│   │
│   ├─► 2️⃣ EvaluateStage (Gemini)
│   │   └─ Evalúa señales
│   │      ├─ Revisa memoria histórica
│   │      ├─ Calcula credibilidad
│   │      └─ Veredicto: BET/GHOST/SKIP
│   │
│   ├─► 3️⃣ BuildOrderStage (Player)
│   │   └─ Calcula tamaño de posición
│   │      ├─ Paroli: Ignora Gemini, apuesta siempre
│   │      ├─ Kelly: Respeta Gemini, solo BET
│   │      └─ Orden: {side, amount, tp, sl}
│   │
│   └─► 4️⃣ ExecuteStage
│       └─ Ejecuta en la Mesa (DataSource)
│          ├─ Backtest: Simula ejecución
│          ├─ Testing: Envía a Kraken Demo
│          └─ Live: Envía a Kraken Real
│
└─► 💰 Actualiza balance
    └─ Mesa devuelve resultado
       └─ WIN/LOSS → Actualiza estado
```

---

## 🎲 Ejemplo Concreto: Paroli en Backtest

```
Usuario ejecuta:
$ python main.py --mode=backtest --player=paroli --data=BTCUSDT_5m.csv

┌─────────────────────────────────────────────┐
│ 1. TradingSession se inicializa            │
│    ├─ DataSource = BacktestDataSource      │
│    ├─ Player = Paroli                      │
│    └─ Pipeline = [Process→Eval→Build→Exec] │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ 2. Mesa (Backtest) carga CSV               │
│    ├─ 8,640 velas de BTC/USDT 5m          │
│    ├─ Normaliza: BTC/USDC:USDC @1m        │
│    └─ Balance inicial: $10,000            │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ 3. Loop: Por cada vela                     │
│    ├─ Mesa entrega vela #1                │
│    ├─ Pipeline procesa                     │
│    │  ├─ Sensores: RSI detecta LONG       │
│    │  ├─ Gemini: GHOST (sin_aprobadas)    │
│    │  ├─ Paroli: ¡Apuesta igual! (0.25%)  │
│    │  └─ Mesa: Ejecuta LONG $25           │
│    ├─ Mesa simula: SL tocado              │
│    └─ Balance: $10,000 → $10,000.24       │
└─────────────────────────────────────────────┘
                    │
                    ▼ (repite 500 veces)
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ 4. Resultados finales                      │
│    ├─ Balance: $10,076                    │
│    ├─ Trades: 458                         │
│    ├─ Wins: 458 (100%)                    │
│    └─ PnL: +$108                          │
└─────────────────────────────────────────────┘
```

---

## 🏗️ Componentes: ¿Qué es cada cosa?

### **DataSource (La Mesa)**
**¿Qué es?** La fuente de datos y ejecución de órdenes.

```python
# ANTES: TableCCXTPro (solo una mesa)
table = TableCCXTPro(connector, symbol, timeframe)
candle = await table.next_candle()
result = table.execute_order(order)

# AHORA: DataSource (3 tipos de mesa)
# Backtest
source = BacktestDataSource.from_csv("data.csv")

# Testing
source = TestingDataSource(connector, symbol, timeframe)

# Live
source = LiveDataSource(connector, symbol, timeframe)

# ¡TODAS TIENEN LA MISMA INTERFAZ!
candle = await source.next_candle()
result = await source.execute_order(order)
```

### **TradingSession (El Casino)**
**¿Qué es?** El orquestador principal.

```python
# Crea sesión con cualquier mesa
session = TradingSession(
    data_source=source,  # ← La mesa (cualquier tipo)
    player=paroli,       # ← El jugador
    max_candles=500      # ← Límite de velas
)

# Ejecuta
await session.run()
```

### **Pipeline (El Flujo)**
**¿Qué es?** La secuencia de pasos que se ejecuta para cada vela.

```python
pipeline = Pipeline([
    ProcessSignalsStage(sensor_manager),  # 1. Detecta señales
    EvaluateStage(gemini),                # 2. Evalúa con Gemini
    BuildOrderStage(player),              # 3. Construye orden
    ExecuteStage(data_source),            # 4. Ejecuta en mesa
])

# Procesa vela
context = await pipeline.process(context)
```

### **TradingContext (El Estado)**
**¿Qué es?** El contenedor inmutable del estado en cada paso.

```python
@dataclass(frozen=True)
class TradingContext:
    candle: Candle           # Vela actual
    equity: float            # Capital total
    balance: float           # Balance disponible
    signals: Tuple[Dict]     # Señales detectadas
    verdict: Dict            # Veredicto de Gemini
    order: Dict              # Orden construida
    result: Dict             # Resultado de ejecución
```

---

## 🔑 Conceptos Clave

### **1. La Mesa NO desapareció**
- **Antes**: `TableCCXTPro` era la única mesa
- **Ahora**: `DataSource` es la interfaz, con 3 implementaciones:
  - `BacktestDataSource` (mesa de práctica)
  - `TestingDataSource` (mesa demo)
  - `LiveDataSource` (mesa real)

### **2. Mismo código, diferentes mesas**
```python
# El MISMO código funciona con CUALQUIER mesa
async def trading_logic(data_source):
    candle = await data_source.next_candle()
    # ... procesa señales ...
    result = await data_source.execute_order(order)

# Funciona con:
await trading_logic(BacktestDataSource(...))  # ✅
await trading_logic(TestingDataSource(...))   # ✅
await trading_logic(LiveDataSource(...))      # ✅
```

### **3. Pipeline unificado**
- **Antes**: Lógica dispersa en `testing_session.py`, `live_session.py`
- **Ahora**: Un solo `Pipeline` que funciona para todos los modos

### **4. Inmutabilidad**
- `TradingContext` es inmutable (frozen dataclass)
- Cada stage recibe un context y devuelve uno nuevo
- Fácil de debuggear, testear y razonar

---

## 📁 Estructura de Archivos

```
Casino-V2/
├── core/
│   ├── data_sources/          ← 🎲 LAS MESAS
│   │   ├── base.py           ← Interfaz DataSource
│   │   ├── backtest.py       ← Mesa de práctica
│   │   ├── testing.py        ← Mesa demo
│   │   └── live.py           ← Mesa real
│   │
│   └── trading/               ← 🎯 EL PIPELINE
│       ├── context.py         ← Estado inmutable
│       ├── pipeline.py        ← Orquestador
│       ├── session.py         ← TradingSession
│       └── stages/            ← Etapas del pipeline
│           ├── process_signals.py  ← 1️⃣ Detecta señales
│           ├── evaluate.py         ← 2️⃣ Gemini evalúa
│           ├── build_order.py      ← 3️⃣ Player construye
│           └── execute.py          ← 4️⃣ Ejecuta en mesa
│
├── players/                   ← 🎲 JUGADORES
│   ├── paroli_player.py      ← Apuesta siempre
│   └── kelly_player.py       ← Respeta Gemini
│
├── gemini/                    ← 🧠 EVALUADOR
│   └── gemini_core.py        ← Lógica de decisión
│
├── sensors/                   ← 📡 DETECTORES
│   └── sensor_manager.py     ← RSI, MACD, etc.
│
└── main.py                    ← 🚀 ENTRADA
```

---

## 🎯 Ventajas de la Nueva Arquitectura

### **1. Modularidad**
- Cada componente tiene una responsabilidad única
- Fácil de entender y mantener

### **2. Testabilidad**
- Backtest sin exchange real
- Testing en demo antes de live
- Mismo código en todos los modos

### **3. Extensibilidad**
- Agregar nuevo DataSource (ej: Binance)
- Agregar nuevo Stage al pipeline
- Agregar nuevo Player

### **4. Inmutabilidad**
- Sin efectos secundarios
- Fácil de debuggear
- Predecible

### **5. Documentación**
- Docstrings en todos los componentes
- Analogías claras (Casino, Mesa, etc.)
- Diagramas de flujo

---

## 🚀 Uso Rápido

### **Backtest (Mesa de Práctica)**
```bash
python main.py \
  --mode=backtest \
  --player=paroli \
  --data=tables/data/raw/BTCUSDT_5m__30d.csv \
  --max-candles=500
```

### **Testing (Mesa Demo)**
```bash
python main.py \
  --mode=testing \
  --player=paroli \
  --symbol=BTC/USD \
  --interval=5m
```

### **Live (Mesa Real)** ⚠️
```bash
python main.py \
  --mode=live \
  --player=paroli \
  --symbol=BTC/USD \
  --interval=5m
```

---

## 📝 Resumen

### **¿Qué pasó con la Mesa?**
✅ **La Mesa sigue existiendo**, ahora se llama `DataSource`

### **¿Hay una sola mesa?**
❌ **No**, ahora hay 3 tipos de mesa intercambiables:
- `BacktestDataSource` (práctica)
- `TestingDataSource` (demo)
- `LiveDataSource` (real)

### **¿Cambió la lógica de trading?**
❌ **No**, la lógica es la misma, solo está mejor organizada en un `Pipeline`

### **¿Puedo usar el código antiguo?**
✅ **Sí**, está en `main_legacy.py` como backup

### **¿Es más complicado?**
❌ **No**, es más simple y claro. Antes había código duplicado en `testing_session.py` y `live_session.py`. Ahora hay un solo `TradingSession` que funciona con cualquier mesa.

---

## 🎓 Conclusión

La nueva arquitectura **NO eliminó la mesa**, la **generalizó**:

```
ANTES: Una mesa específica (TableCCXTPro)
AHORA: Una interfaz (DataSource) con 3 implementaciones

┌─────────────────────────────────────────┐
│  DataSource (La Mesa Abstracta)         │
│  ├─ next_candle()                       │
│  ├─ execute_order()                     │
│  ├─ get_balance()                       │
│  └─ get_equity()                        │
└─────────────────────────────────────────┘
            │
    ┌───────┼───────┐
    │       │       │
    ▼       ▼       ▼
Backtest Testing  Live
(Papel) (Demo)  (Real)
```

**Mismo concepto, mejor implementación.** 🎯
