# 🚨 DEVELOPER.md — Guía Técnica Obligatoria

> **⚠️ OBLIGATORIO LEER ANTES DE CUALQUIER DESARROLLO**
>
> Este documento es tu "prompt" técnico. Si pierdes el contexto, lee esto primero.

---

## 🎯 Proyecto: Casino V2

**Visión**: Motor de trading probabilístico multi-asset multi-timeframe.

**Versión Actual**: v1.7 (Code Cleanup & Organization Completado)

**Estado**: Code Cleanup completado → Próximo: Multi-Asset Expansion (v1.8)

---

## 📋 Checklist Obligatorio (Antes de Cualquier Cambio)

### ✅ **1. Leer TODOS los 4 Documentos Pilares**
```bash
# ⚠️ ORDEN DE LECTURA 100% OBLIGATORIO - NO SALTAR NINGUNO:
1. DEVELOPER.md                    ← Este archivo (acabado de leer)
2. docs/workflow.md               ← CÓMO desarrollamos (OBLIGATORIO)
3. docs/development/PENDIENTES.md ← QUÉ implementar (OBLIGATORIO)
4. README.md                       ← Vista general (OBLIGATORIO)
```

**🚨 CONSECUENCIAS DE NO LEER LOS 4 PILARES:**
- ❌ **Código rechazado** en code review por falta de contexto
- ❌ **Features implementadas** que ya existen o van contra la arquitectura
- ❌ **Bugs introducidos** por no entender el flujo correcto
- ❌ **Tiempo perdido** refactorizando código mal diseñado
- ❌ **Consistencia rota** entre documentación y código

**💯 REGLA DE ORO:** Si no has leído los 4 documentos pilares completos, **NO CODEES**. Vuelve atrás y léelos TODOS.

### ✅ **1.5 Verificación de Lectura Completada**
Después de leer los 4 documentos, confirma que entiendes:
- [ ] Arquitectura modular (Sensores → Gemini → Player → Croupier → Tables)
- [ ] Estado actual v1.7 y bloqueantes para v1.8
- [ ] Workflow Git con ramas 1.7 → 1.8
- [ ] Testing strategy y reglas obligatorias
- [ ] Regla de sincronización de los 4 pilares

### ✅ **2. Regla de Sincronización de Documentación**
**⚠️ IMPORTANTE:** Si modificas cualquiera de los 4 archivos pilares, debes actualizar TODOS los archivos para mantener consistencia:

- **README.md** - Vista del usuario (¿qué es?)
- **DEVELOPER.md** - Guía técnica (¿cómo funciona?)
- **docs/workflow.md** - Proceso de desarrollo (¿cómo trabajamos?)
- **docs/development/PENDIENTES.md** - Roadmap (¿hacia dónde vamos?)

**Campos que deben mantenerse sincronizados:**
- ✅ Número de versión actual
- ✅ Estado del proyecto y features completadas
- ✅ Ramas Git activas (ej: 1.6 producción, 1.7 desarrollo)
- ✅ Próximas prioridades de desarrollo
- ✅ Arquitectura y componentes principales
- ✅ Referencias cruzadas entre documentos

### ✅ **2. Verificar Estado del Sistema**
```bash
# Sistema debe estar funcional
python main.py                    # Backtest básico funciona
python test_phase1.py            # Tests pasan (14/14)
python test_websocket_live.py    # WebSocket funciona (si tienes credenciales)
```

### ✅ **3. Conocer Arquitectura**
```
📂 Estructura Crítica:
├── main.py                    # 🚀 Entry point
├── config.py                  # ⚙️ Configuración global
├── gemini/                    # 🎯 Motor de decisión probabilística
├── players/                   # 🎮 Estrategias de sizing
├── sensors/                   # 👁️ Detectores técnicos (17 sensores)
├── tables/                    # 🪙 Interfaces de exchanges
├── croupier/                  # 🧤 Ejecución de órdenes
└── docs/                      # 📚 Documentación
```

---

## 🧠 Arquitectura Técnica

### **Flujo Principal**
```
Sensores → Gemini → Player → Croupier → BrokerInterface → Table → BalanceManager
```

### **Componentes Críticos**

#### **🎯 Gemini** (`gemini/gemini_core.py`)
- **Función**: Valida probabilísticamente si operar
- **Entrada**: Señales de sensores
- **Salida**: `verdict.side` (LONG/SHORT/NONE)
- **Regla**: NUNCA decide tamaño de posición

#### **🎮 Players** (`players/`)
- **Función**: Calcula tamaño de posición
- **Entrada**: `verdict` de Gemini + equity
- **Salida**: Fracción de equity (0.0-1.0)
- **Regla**: NUNCA decide cuándo operar

#### **🧤 Croupier** (`croupier/croupier.py`)
- **Función**: Ejecutor imparcial
- **Interface**: `route_order(order_dict) → result_dict`
- **Validación**: Campos requeridos del order

#### **🤝 BrokerInterface** (`croupier/broker_interface.py`)
- **Función**: Crea mesas según modo (backtest/live)
- **Lógica**: `config.MODE` → `TableBacktest` o `TableCCXTPro`

#### **🪙 Tables** (`tables/`)
- **TableBacktest**: Backtest vela-por-vela con TP/SL
- **TableCCXTPro**: Live trading con WebSocket
- **BalanceManager**: Gestiona capital
- **PositionTracker**: Simula posiciones abiertas

---

## 🎮 Modos de Operación

### **Backtest** (`MODE = "backtest"`)
```python
# config.py
MODE = "backtest"
DATASET_PATH = "tables/data/raw/BTCUSDT_15m.csv"
```

**Flujo**: CSV → TableBacktest → Croupier → Gemini → Resultados

### **Live** (`MODE = "live"`)
```python
# config.py
MODE = "live"
EXCHANGE = "KRAKEN"  # o "BINANCE" o "HYPERLIQUID"
```

**Flujo**: WebSocket → TableCCXTPro → Croupier → Gemini → Órdenes reales

---

## 🧪 Testing Strategy

### **Tests Obligatorios**
```bash
# Arquitectura (siempre)
python test_phase1.py           # ✅ 14/14 tests

# Mejoras específicas
python test_mejoras_futurechanges.py  # ✅ 3/3 tests

# WebSocket (si aplica)
python test_websocket_integration.py  # Tests unitarios
python test_websocket_live.py         # Tests con datos reales
```

### **Reglas de Testing**
- ✅ **Todo código nuevo** debe tener tests
- ✅ **Tests pasan** antes de commit
- ✅ **Cobertura completa** para lógica crítica
- ✅ **Integration tests** para flujos completos

---

## 🌳 Git Workflow

### **Ramas Principales**
```
1.7     ← Producción actual (Code Cleanup completado)
1.8     ← Desarrollo (Multi-Asset Expansion)
main    ← Backup (no tocar)
```

### **Flujo de Desarrollo**
```bash
# 1. Actualizar rama principal
git checkout 1.7 && git pull

# 2. Crear feature branch
git checkout -b feature/nombre-descriptivo

# 3. Desarrollo + commits
git commit -m "feat: descripción"
git commit -m "test: tests agregados"

# 4. Push y PR
git push -u origin feature/nombre-descriptivo
# → GitHub PR a 1.8

# 5. Merge cuando aprobado
git checkout 1.8 && git merge feature/nombre-descriptivo
```

### **Commits Estándar**
```
feat: Nueva funcionalidad
fix: Corrección de bug
docs: Cambios en documentación
test: Agregar/modificar tests
refactor: Cambios sin nueva funcionalidad
```

---

## 🎯 Próximos Pasos

**📖 Ver roadmap completo en `docs/development/PENDIENTES.md`**

---

## 🛠️ Comandos Útiles

### **Desarrollo Diario**
```bash
# Ver estado
python main.py                    # Backtest rápido
python main.py --player=fixed     # Probar player alternativo

# Tests
python -m pytest                  # Todos los tests
python test_phase1.py            # Tests arquitectura

# Documentación
cat docs/workflow.md             # Cómo desarrollar
cat docs/development/PENDIENTES.md  # Qué hacer
```

### **Live Trading**
```bash
# Configurar en config.py
MODE = "live"
EXCHANGE = "KRAKEN"  # o BINANCE o HYPERLIQUID

# Ejecutar
python main.py
```

### **Debugging**
```bash
# Logs detallados
python main.py --verbose

# Ver memoria entrenada
python -m utils.analyze_memory

# Tests específicos
python -m pytest tests/test_gemini.py -v
```

---

## ⚠️ Reglas Importantes

### **NO HACER:**
- ❌ **Commits directos** a ramas principales (1.6, 1.7)
- ❌ **Cambios sin tests**
- ❌ **Código sin documentación**
- ❌ **Merge sin code review**

### **SIEMPRE HACER:**
- ✅ **Leer DEVELOPER.md** antes de cualquier cambio
- ✅ **Tests pasan** antes de commit
- ✅ **Documentar cambios** en PENDIENTES.md
- ✅ **Code review** para todos los merges

---

## 🎭 Glosario de Analogías del Casino

**Referencia rápida para comunicación consistente entre humano y AI:**

### **1. 🎯 Jugador (Player)**
- **Analogía**: El apostador que decide cuánto arriesgar
- **Función Técnica**: `players/` - Algoritmos de money management
- **Código**: `players/kelly_player.py`, `players/fixed_player.py`
- **Responsabilidad**: Calcular `size_fraction` basado en equity

### **2. 👁️ Gemini (Spotter/Observador)**
- **Analogía**: Spotter que vigila mesas y avisa cuándo están calientes
- **Función Técnica**: `gemini/` - Sistema de aprendizaje probabilístico
- **Código**: `gemini/gemini_core.py`, `gemini/memory.py`
- **Responsabilidad**: Generar `Verdict` con side y confidence

### **3. 🎲 Croupier (Router)**
- **Analogía**: El dealer que recibe órdenes del spotter y las enruta
- **Función Técnica**: `croupier/` - Enrutador de órdenes
- **Código**: `croupier/croupier.py` - `route_order()`
- **Responsabilidad**: Validar y enrutar órdenes al destino correcto

### **4. 🪙 Mesa/Table (Ejecutor)**
- **Analogía**: La mesa específica donde se ejecuta la acción
- **Función Técnica**: `tables/` - Interfaces con exchanges/brokers
- **Código**: `tables/table_*.py` - `execute_order()`
- **Responsabilidad**: Ejecutar órdenes y manejar posiciones

### **5. 🃏 Señales (Signals)**
- **Analogía**: Cartas que llegan a la mesa
- **Función Técnica**: `sensors/` - Indicadores técnicos procesados
- **Código**: `sensors/mean_reversion/`, `sensors/momentum_trend_following/`
- **Ejemplo**: RSI, MACD, Supertrend generan señales

### **6. 💰 Fichas (Size Fraction)**
- **Analogía**: Cantidad de fichas apostadas
- **Función Técnica**: Porcentaje del equity a arriesgar (0.0-1.0)
- **Código**: `size_fraction` en órdenes
- **Ejemplo**: 0.02 = 2% del bankroll

### **7. 📊 Verdict (Decisión del Spotter)**
- **Analogía**: Aviso del spotter sobre mesa caliente
- **Función Técnica**: `Verdict(side='BUY', confidence=0.8)`
- **Código**: `gemini_core.Verdict`
- **Ejemplo**: BUY con 80% confidence

### **8. 👻 Ghost Trades**
- **Analogía**: Carta que se registra pero no se juega
- **Función Técnica**: Trade simulado para aprendizaje
- **Código**: `order["ghost"] = True`
- **Ejemplo**: Entrena sin tocar balance

### **9. 🏢 Pisos del Casino (Trading Modes)**
- **Analogía**: Diferentes pisos con reglas y riesgos distintos
- **Piso 1**: Ruleta Americana (Backtest) - `MODE = "backtest"` - simulación histórica sin riesgo
- **Piso 2**: Ruleta Francesa (Paper Trading) - `MODE = "live"` con testnet - datos reales, balance simulado
- **Piso 3**: Ruleta Europea (Live Trading) - `MODE = "live"` con mainnet - dinero real, máximo riesgo

### **10. 🎰 Casino (Sistema Completo)**
- **Analogía**: El establecimiento completo de juegos
- **Función Técnica**: Todo el sistema de trading algorítmico
- **Código**: `main.py` + todos los módulos

### **11. 🎯 Sensores**
- **Analogía**: Los dados o ruletas que generan números aleatorios
- **Función Técnica**: Indicadores técnicos que generan señales
- **Código**: 17 sensores en `sensors/`
- **Ejemplo**: RSI = dado que tira valores 0-100

## 📞 Contacto & Referencias

**Documentos Relacionados:**
- `docs/workflow.md` - Proceso de desarrollo detallado
- `docs/development/PENDIENTES.md` - Roadmap y prioridades
- `README.md` - Vista general del proyecto

**Si pierdes el contexto:**
1. Lee este archivo (DEVELOPER.md)
2. Revisa `docs/workflow.md`
3. Verifica `docs/development/PENDIENTES.md`
4. Corre tests para verificar funcionalidad

---

**🎰 Casino V2 - Arquitectura Modular para Trading Probabilístico**

*Última actualización: Octubre 2025*
