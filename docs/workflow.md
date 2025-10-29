# 🚀 WORKFLOW - Casino V2 Development Guidelines

> **Versión**: v1.4
> **Última actualización**: Octubre 2025
> **Propósito**: Guidelines para desarrollo colaborativo consistente

---

## 📋 ÍNDICE

1. [Estado del Proyecto](#estado-del-proyecto)
2. [Antes de Empezar](#antes-de-empezar)
3. [Flujo de Desarrollo](#flujo-de-desarrollo)
4. [Estructura de Código](#estructura-de-código)
5. [Testing Guidelines](#testing-guidelines)
6. [Documentación](#documentación)
7. [Git Workflow](#git-workflow)
8. [Deployment](#deployment)

---

## 🎯 ESTADO DEL PROYECTO

### **Visión Final: Multi-Asset Multi-Timeframe Trading Engine**

**Casino V2 aspira a ser un motor de trading probabilístico avanzado capaz de:**

- **🎰 Multi-Asset Trading**: Operar múltiples criptomonedas simultáneamente en un mismo exchange
- **⏱️ Multi-Timeframe Analysis**: Analizar diferentes marcos temporales concurrentemente
- **🔄 Real-Time Processing**: Procesar flujos de velas en tiempo real para todas las parejas
- **🎯 Sensor-Driven Decisions**: Tomar decisiones de trading basadas en señales técnicas por activo
- **💰 Unified Risk Management**: Gestionar capital y riesgo de manera holística across assets

**Estado Actual: v1.4** (Single-Asset Foundation)
- ✅ **Arquitectura**: Modular Gemini/Player
- ✅ **Live Trading**: Operativo (Kraken Demo validado)
- ✅ **Backtest**: 89.71% winrate con gestión realista
- ✅ **Tests**: 14/14 pasando
- ✅ **Documentación**: Completamente actualizada

### **Próxima Versión: v1.5** (Hacia Multi-Asset)
- 🎯 **Adaptive Player** (Alta prioridad)
- 🎯 **Dashboard Web** (Alta prioridad)
- 🎯 **Kill-Switch** (Media prioridad)
- 🎯 **Multi-Asset Foundation** (Objetivo final)

### **Archivos Críticos para Leer Primero:**
```
📚 docs/development/PENDIENTES.md     # Estado actual y roadmap
📚 docs/architecture/overview.md      # Arquitectura completa
📚 docs/workflow.md                   # Este archivo
🧪 test_*.py                          # Tests como referencia
```

---

## 🔍 ANTES DE EMPEZAR

### **Checklist Obligatorio:**

#### **1. Leer Documentación Actual**
```bash
# Estado del proyecto
cat docs/development/PENDIENTES.md

# Arquitectura completa
cat docs/architecture/overview.md

# Guidelines de desarrollo
cat docs/workflow.md
```

#### **2. Verificar Sistema Funciona**
```bash
# Backtest funciona
python main.py --player=kelly

# Tests pasan
python -m pytest

# Live trading posible
python main.py  # Cambiar config a live si se quiere probar
```

#### **3. Revisar Código Reciente**
```bash
# Ver commits recientes
git log --oneline -10

# Ver cambios en rama principal
git show-branch 1.4
```

---

## 🔄 FLUJO DE DESARROLLO

### **Paso 1: Planificación**
1. ✅ **Leer PENDIENTES.md** - Ver features disponibles
2. ✅ **Elegir feature** - Priorizar según impacto
3. ✅ **Decidir ubicación** - Consultar tabla de organización arriba
4. ✅ **Crear issue** - Documentar alcance y criterios
5. ✅ **Diseñar solución** - Sketch arquitectura respetando estructura

### **Paso 2: Desarrollo**
1. ✅ **Crear rama feature/** - `git checkout -b feature/nombre`
2. ✅ **Implementar código** - Seguir estándares
3. ✅ **Testing continuo** - Tests pasan en cada cambio
4. ✅ **Documentar cambios** - Actualizar docs si necesario

### **Paso 3: Validación**
1. ✅ **Tests exhaustivos** - Cobertura completa
2. ✅ **Backtest validado** - Performance no degrada
3. ✅ **Live testing** - Paper trading si aplica
4. ✅ **Code review** - Checklist completo

### **Paso 4: Merge**
1. ✅ **Squash commits** - Historia limpia
2. ✅ **Merge a 1.5** - Pull request con descripción
3. ✅ **Actualizar docs** - PENDIENTES.md y changelog
4. ✅ **Tag release** - Si es milestone importante

---

## 🏗️ ESTRUCTURA DE CÓDIGO

### **Organización de Archivos**
```
Casino-V2/
├── main.py                    # 🚀 Entry point principal
├── config.py                  # ⚙️ Configuración global del sistema
├── gemini/                    # 🎯 Motor de decisión probabilística
│   ├── gemini_core.py         # Lógica principal de validación
│   ├── memory.py              # Sistema de aprendizaje (winrates)
│   ├── bucket_manager.py      # Clasificación de contextos
│   └── decision_logger.py     # Logging de decisiones
├── players/                   # 🎮 Estrategias de position sizing
│   ├── kelly_player.py        # Kelly Criterion conservador
│   ├── fixed_player.py        # Tamaño fijo por trade
│   └── paroli_player.py       # Progresión 1-4-8
├── sensors/                   # 👁️ Detectores técnicos
│   ├── sensor_manager.py      # Coordinador de sensores
│   ├── mean_reversion/        # Sensores de reversión media
│   ├── momentum_trend_following/  # Sensores momentum/tendencia
│   └── volumen_flujo_capital/     # Sensores volumen/capital
├── tables/                    # 🪙 Interfaces de exchanges
│   ├── table_backtest.py      # Backtest sobre CSV
│   ├── table_binance_paper.py # Binance Futures (paper/live)
│   ├── table_kraken_paper.py  # Kraken Futures (demo)
│   ├── table_aster_paper.py   # ASTER (paper)
│   ├── balance_manager.py     # Gestión de capital
│   └── position_tracker.py    # Gestión de posiciones abiertas
├── croupier/                  # 🧤 Ejecución de órdenes
│   ├── croupier.py            # Router de órdenes
│   └── broker_interface.py    # Interface con exchanges
├── utils/                     # 🛠️ Herramientas y CLI
│   ├── cli.py                 # CLI unificado
│   ├── analyze_memory.py      # Análisis de memoria
│   ├── download_kline_dataset.py  # Descarga de datos
│   └── [otras utilidades]
├── docs/                      # 📚 Documentación
│   ├── README.md              # Índice principal
│   ├── workflow.md            # Guidelines de desarrollo
│   ├── architecture/          # Arquitectura del sistema
│   ├── guides/                # Guías de uso
│   └── development/           # Desarrollo y roadmap
└── tests/                     # 🧪 Testing
    └── test_*.py              # Tests unitarios/integration
```

### **Reglas de Organización por Carpeta**

#### **📋 Decisiones de Arquitectura por Carpeta**

##### **¿Dónde poner nueva funcionalidad?**

| Tipo de Código | Carpeta | Ejemplo | Razón |
|---------------|---------|---------|-------|
| **Validación probabilística** | `/gemini/` | `gemini/volatility_analyzer.py` | Es decisión de entrada |
| **Cálculo de position size** | `/players/` | `players/adaptive_player.py` | Es sizing strategy |
| **Nuevo indicador técnico** | `/sensors/` | `sensors/volatility/bbands_squeeze.py` | Es detección de contexto |
| **Nueva conexión exchange** | `/tables/` | `tables/table_bybit_paper.py` | Es interface de mercado |
| **Script de análisis** | `/utils/` | `utils/analyze_volatility.py` | Es herramienta CLI |
| **Nueva guía** | `/docs/guides/` | `docs/guides/volatility-trading.md` | Es documentación |
| **Test de nueva feature** | `/tests/` | `tests/test_adaptive_player.py` | Es validación |

##### **❌ NO PONER en estas carpetas:**

- **NO sizing en `/gemini/`** → Va en `/players/`
- **NO indicadores en `/players/`** → Van en `/sensors/`
- **NO lógica core en `/utils/`** → Solo herramientas
- **NO código en `/docs/`** → Solo documentación
- **NO archivos sueltos en root** → Todo organizado

##### **📁 Estructura de Subcarpetas**

```
sensors/
├── mean_reversion/           # ✅ Agrupado por tipo
├── momentum_trend_following/ # ✅ Agrupado por tipo
└── volumen_flujo_capital/    # ✅ Agrupado por tipo

NO HACER:
sensors/
├── rsi.py                    # ❌ Archivos sueltos
├── macd.py                   # ❌ Archivos sueltos
└── bollinger.py              # ❌ Archivos sueltos
```

##### **🧩 Plugins y Extensiones**

**Para código extensible:**
- **Sensores**: `sensors/{categoria}/{sensor}.py`
- **Players**: `players/{strategy}_player.py`
- **Utils**: `utils/{funcion}.py`
- **Tests**: `tests/test_{feature}.py`

**Ejemplos correctos:**
```
✅ sensors/mean_reversion/keltner_reversion.py
✅ players/volatility_adaptive_player.py
✅ utils/download_funding_rates.py
✅ tests/test_volatility_adaptive_player.py
```

**Ejemplos incorrectos:**
```
❌ sensors/keltner.py (sin subcategoría)
❌ players/adaptive.py (sin _player)
❌ utils/funding.py (sin función específica)
❌ tests/volatility_test.py (sin test_)
```

#### **🎯 `/gemini/` - Motor de Decisión**
- **Propósito**: Validación probabilística y aprendizaje
- **Contenido**: Solo lógica de decisión, memoria y buckets
- **Regla**: NO sizing aquí (delegado a players)

#### **🎮 `/players/` - Estrategias de Sizing**
- **Propósito**: Decidir cuánto apostar
- **Contenido**: Implementaciones de position sizing
- **Regla**: Solo lógica de cálculo de tamaño, NO decisiones de entrada

#### **👁️ `/sensors/` - Detectores Técnicos**
- **Propósito**: Identificar contextos favorables
- **Contenido**: Indicadores técnicos y señales
- **Regla**: Solo detección, NO decisiones de trade

#### **🪙 `/tables/` - Interfaces de Exchange**
- **Propósito**: Conectar con mercados y simular trades
- **Contenido**: Conexiones API, simulación, balance/position management
- **Regla**: Solo I/O con mercados, NO lógica de decisión

#### **🧤 `/croupier/` - Ejecución**
- **Propósito**: Routing de órdenes sin cuestionar
- **Contenido**: Interfaces de broker, ejecución pura
- **Regla**: Solo ejecutar, NO decidir

#### **🛠️ `/utils/` - Herramientas**
- **Propósito**: Utilidades CLI y helpers
- **Contenido**: Scripts de análisis, descarga, configuración
- **Regla**: Solo herramientas, NO lógica core del sistema

#### **📚 `/docs/` - Documentación**
- **Propósito**: Conocimiento organizado
- **Contenido**: Guías, arquitectura, desarrollo
- **Regla**: Toda documentación aquí, NO en código

#### **🧪 `/tests/` - Testing**
- **Propósito**: Validación de funcionalidad
- **Contenido**: Tests unitarios, integration, performance
- **Regla**: Tests para TODO código nuevo

### **Estándares de Código**

#### **Imports**
```python
# ✅ Correcto
from __future__ import annotations
import logging
from typing import Dict, Optional
from gemini.gemini_core import Gemini

# ❌ Incorrecto
import *
from .. import *
```

#### **Clases y Funciones**
```python
# ✅ Correcto
class MyPlayer:
    """Una línea describiendo qué hace."""
    
    def __init__(self, param: float) -> None:
        self.param = param
    
    def calculate_position_size(
        self, 
        verdict: Verdict, 
        equity: float, 
        meta: Optional[Dict] = None
    ) -> Optional[float]:
        """Calcula tamaño de posición.
        
        Args:
            verdict: Decisión de Gemini
            equity: Capital disponible
            meta: Metadata adicional
            
        Returns:
            Fracción de equity a usar (0.0-1.0) o None
        """
        # Implementación aquí
        pass
```

#### **Logging**
```python
# ✅ Correcto
logger = logging.getLogger(__name__)

def my_function():
    logger.info("Iniciando proceso")
    try:
        # código
        logger.debug(f"Resultado: {result}")
    except Exception as e:
        logger.error(f"Error en proceso: {e}")
        raise
```

#### **Error Handling**
```python
# ✅ Correcto
try:
    result = risky_operation()
except SpecificError as e:
    logger.warning(f"Error específico: {e}")
    return fallback_value
except Exception as e:
    logger.error(f"Error inesperado: {e}")
    raise
```

---

## 🧪 TESTING GUIDELINES

### **Tipos de Tests Requeridos**

#### **1. Unit Tests** (Obligatorios)
```python
# tests/test_my_player.py
import pytest
from players.my_player import MyPlayer

class TestMyPlayer:
    def test_calculate_position_size_valid(self):
        player = MyPlayer(param=0.5)
        verdict = create_mock_verdict()  # Helper function
        result = player.calculate_position_size(verdict, 10000.0)
        assert result is not None
        assert 0.0 <= result <= 1.0
    
    def test_calculate_position_size_none(self):
        player = MyPlayer(param=0.5)
        verdict = create_mock_verdict(side=None)  # No side
        result = player.calculate_position_size(verdict, 10000.0)
        assert result is None
```

#### **2. Integration Tests** (Recomendados)
```python
# tests/test_integration_backtest.py
def test_full_backtest_pipeline():
    # Config test
    config.MODE = "backtest"
    config.STARTING_BALANCE = 10000
    
    # Run backtest
    from main import run_session_with_player
    stats = run_session_with_player(
        dataset_path="test_data.csv",
        initial_balance=10000,
        gemini=Gemini(),
        player_module=kelly_player,
        player_name="kelly"
    )
    
    # Assertions
    assert stats["final_balance"] > 9000  # No huge losses
    assert stats["wins"] + stats["losses"] > 0  # Some trades
```

#### **3. Performance Tests** (Para features críticas)
```python
# tests/test_performance.py
import time

def test_backtest_performance():
    start_time = time.time()
    
    # Run backtest with 1000 candles
    stats = run_backtest(dataset_1000_candles)
    
    duration = time.time() - start_time
    assert duration < 30.0  # Should complete in < 30 seconds
```

### **Ejecutar Tests**
```bash
# Todos los tests
python -m pytest

# Tests específicos
python -m pytest tests/test_my_player.py

# Con cobertura
python -m pytest --cov=players --cov-report=html

# Tests lentos
python -m pytest -m "not slow"
```

---

## 📚 DOCUMENTACIÓN

### **Regla de Oro:**
> **"Si cambias código, actualiza documentación"**

### **Qué Documentar:**

#### **1. Nuevas Features**
- ✅ Crear archivo en `docs/`
- ✅ Actualizar `PENDIENTES.md`
- ✅ Agregar ejemplos de uso

#### **2. Cambios en API**
- ✅ Actualizar docstrings
- ✅ Modificar ejemplos
- ✅ Versionar cambios

#### **3. Breaking Changes**
- ✅ Documentar migración
- ✅ Actualizar CHANGELOG.md
- ✅ Notificar impacto

### **Dónde Documentar:**

| Tipo de Cambio | Archivo | Ejemplo |
|---------------|---------|---------|
| Nueva feature | `docs/guides/` | `docs/guides/adaptive-player.md` |
| Arquitectura | `docs/architecture/` | `docs/architecture/position-management.md` |
| API cambio | `docs/reference/` | `docs/reference/api-players.md` |
| Roadmap | `docs/development/PENDIENTES.md` | Marcar completado |
| Release | `docs/CHANGELOG.md` | Nueva versión |

---

## 🌳 GIT WORKFLOW

### **Ramas Principales**
```
1.4     ← Rama principal (producción)
1.5     ← Rama de desarrollo
main    ← Backup (no usar)
```

### **Flujo de Trabajo**
```bash
# 1. Actualizar rama principal
git checkout 1.4
git pull origin 1.4

# 2. Crear rama feature
git checkout -b feature/adaptive-player

# 3. Desarrollo con commits descriptivos
git commit -m "feat: Implementar Adaptive Player base"
git commit -m "test: Agregar tests para volatilidad"
git commit -m "docs: Documentar Adaptive Player"

# 4. Push rama
git push -u origin feature/adaptive-player

# 5. Crear Pull Request a 1.5
# GitHub: Compare & pull request

# 6. Merge cuando aprobado
git checkout 1.5
git merge feature/adaptive-player
```

### **Commits Estándar**
```
feat: Nueva funcionalidad
fix: Corrección de bug
docs: Cambios en documentación
test: Agregar o modificar tests
refactor: Cambios de código sin funcionalidad nueva
chore: Mantenimiento (linting, etc.)
```

### **Pull Requests**
**Template requerido:**
- ✅ **Descripción clara** del cambio
- ✅ **Motivación** del cambio
- ✅ **Impacto** en otras partes
- ✅ **Tests** incluidos
- ✅ **Docs** actualizadas
- ✅ **Screenshots** si aplica UI

---

## 🚀 DEPLOYMENT

### **Para Nuevas Versiones**

#### **1. Preparar Release**
```bash
# Actualizar versión en config.py si aplica
# Actualizar CHANGELOG.md
# Asegurar todos tests pasan
git tag v1.5.0
git push origin v1.5
git push origin --tags
```

#### **2. GitHub Release**
- Crear release en GitHub
- Copiar CHANGELOG.md relevante
- Subir assets si aplica

#### **3. Post-Release**
```bash
# Merge a 1.4 si es stable
git checkout 1.4
git merge 1.5

# Crear nueva rama de desarrollo
git checkout -b 1.6
```

---

## ⚠️ REGLAS IMPORTANTES

### **NO HACER:**
- ❌ **Commits directos a 1.4** (usar PR)
- ❌ **Cambios sin tests**
- ❌ **Código sin documentación**
- ❌ **Merge sin code review**

### **SIEMPRE HACER:**
- ✅ **Leer docs antes de cambiar código**
- ✅ **Tests pasan antes de commit**
- ✅ **Documentar cambios**
- ✅ **Code review para merges**

---

## 🆘 TROUBLESHOOTING

### **Problemas Comunes**

#### **"No sé por dónde empezar"**
```bash
# Leer documentación
cat docs/development/PENDIENTES.md
cat docs/workflow.md

# Ver código existente
find . -name "*.py" -exec grep -l "class.*Player" {} \;
```

#### **"Mi código rompe tests"**
```bash
# Ver qué tests fallan
python -m pytest -v

# Ver logs detallados
python -m pytest --tb=long

# Comparar con código existente
git diff HEAD~1
```

#### **"No sé cómo documentar"**
```bash
# Ver ejemplos existentes
cat docs/guides/creating-players.md
cat docs/architecture/overview.md

# Seguir estructura
# 1. ¿Qué hace?
# 2. ¿Cómo usarlo?
# 3. ¿Ejemplos?
# 4. ¿Consideraciones?
```

---

## 📞 CONTACTO & SOPORTE

**Para dudas sobre desarrollo:**
1. Leer este documento (`docs/workflow.md`)
2. Revisar `docs/development/PENDIENTES.md`
3. Ver código existente como referencia
4. Preguntar en desarrollo con contexto completo

**Recuerda:** La documentación es tan importante como el código. ¡Mantengámosla actualizada! 📚✨