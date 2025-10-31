# 🛠️ Development Setup

Guía completa para configurar el entorno de desarrollo de Casino V2.

---

## 📦 Instalación y Configuración

### 1. Clonar y Instalar

```bash
git clone https://github.com/tu-usuario/Casino-V2.git
cd Casino-V2
pip install -r requirements.txt
```

### 2. Instalar Pre-commit Hooks

**Pre-commit** es un sistema de calidad de código que ejecuta verificaciones automáticas antes de cada commit.

```bash
# Instalar pre-commit (ya incluido en requirements-dev.txt)
pip install pre-commit

# Instalar hooks en el repositorio
pre-commit install

# Verificar instalación
pre-commit --version
```

---

## 🔧 Pre-commit Hooks - Calidad de Código Automática

### Qué Hace Pre-commit

Cada vez que ejecutas `git commit`, **pre-commit automáticamente**:

1. **✅ Black** - Formatea el código Python automáticamente
2. **✅ Flake8** - Revisa estilo de código y posibles errores
3. **✅ MyPy** - Verifica tipos (type checking)
4. **✅ isort** - Ordena y agrupa imports automáticamente
5. **✅ pytest** - Ejecuta tests si hay cambios relevantes

### Ejemplo de Funcionamiento

```bash
# Cuando haces commit normalmente:
git add core/session_runner.py
git commit -m "feat: mejorar session runner"

# Pre-commit se ejecuta automáticamente:
# 🔄 Reformateando código con Black...
# 🔄 Ordenando imports con isort...
# 🔄 Verificando tipos con MyPy...
# 🔄 Revisando estilo con Flake8...
# ✅ Todos los checks pasaron - commit exitoso

# Si hay errores:
# ❌ Error en Flake8: línea demasiado larga
# ❌ Commit bloqueado - corrige los errores primero
```

### Beneficios

- **🔒 Calidad Garantizada**: Todo código sigue estándares consistentes
- **⚡ Automático**: No requiere acción manual del desarrollador
- **🚫 Bloquea Errores**: Evita que código problemático llegue al repositorio
- **📝 Formato Consistente**: Black e isort mantienen estilo uniforme
- **🛡️ Type Safety**: MyPy atrapa errores de tipos antes de runtime

### Configuración

Los hooks están configurados en `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pytest-dev/pytest
    rev: 7.4.0
    hooks:
      - id: pytest
        args: [--tb=short]
```

### Comandos Útiles

```bash
# Ejecutar todos los hooks manualmente
pre-commit run --all-files

# Ejecutar solo un hook específico
pre-commit run black --all-files
pre-commit run flake8 --all-files

# Ver estado de hooks
pre-commit install --install-hooks

# Saltar hooks para commit urgente (no recomendado)
git commit --no-verify -m "mensaje"
```

---

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests específicos
pytest test_core_architecture.py
pytest test_websocket_integration.py -v

# Con cobertura
pytest --cov=core --cov-report=html

# Tests lentos marcados
pytest -m "slow"
```

### Estructura de Tests

```
tests/
├── test_core_architecture.py    # Tests de arquitectura core
├── test_core_integration.py     # Tests de integración
├── test_websocket_integration.py # Tests WebSocket
└── test_new_sensors.py          # Tests de sensores
```

---

## 📝 Code Style Guidelines

### Black (Formateo Automático)

- **Líneas**: Máximo 79 caracteres
- **Comillas**: Dobles por defecto
- **Imports**: Uno por línea cuando > 79 chars

### Flake8 (Linting)

- **E501**: Líneas demasiado largas (Black las corrige)
- **F401**: Imports no usados
- **E203**: Espacios alrededor de comas (Black compatible)

### MyPy (Type Checking)

- **Tipos obligatorios** en funciones públicas
- **Type hints completos** en módulos core
- **Generic types** para colecciones

### isort (Import Sorting)

```python
# Correcto
import os
import sys
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from .core.exceptions import ValidationError
from .core.logger import logger
```

---

## 🔍 Debugging y Desarrollo

### Logs Estructurados

```python
from core.logger import logger

# Logging con niveles
logger.debug("Detalle técnico")
logger.info("Información general")
logger.warning("Advertencia")
logger.error("Error recuperable")
logger.critical("Error fatal")

# Performance monitoring
@performance_monitor("operation_name")
def my_function():
    pass
```

### Manejo de Errores

```python
from core.exceptions import ValidationError, TradingError
from core.validators import validate_positive_number

try:
    amount = validate_positive_number(input_amount, "amount")
except ValidationError as e:
    logger.error(f"Validación fallida: {e}")
    raise
```

### Caching para Performance

```python
from core.cache import cached_sensor, data_cache

@cached_sensor
def calculate_rsi(prices: List[float], period: int = 14) -> float:
    # Cálculo pesado, cacheado automáticamente
    pass

# Cache manual
result = data_cache.get_indicator("rsi", "BTC/USDT", "1h", 14)
if result is None:
    result = calculate_rsi(prices, 14)
    data_cache.set_indicator("rsi", "BTC/USDT", "1h", 14, result)
```

---

## 🚀 Desarrollo Avanzado

### Rama de Desarrollo

```bash
# Crear rama para feature
git checkout -b feature/nueva-funcionalidad

# Commits frecuentes (pre-commit se ejecuta automáticamente)
git add .
git commit -m "feat: descripción clara"

# Push y PR
git push origin feature/nueva-funcionalidad
```

### Code Review Checklist

- [ ] Pre-commit pasa todos los checks
- [ ] Tests nuevos incluidos y pasan
- [ ] Documentación actualizada
- [ ] Type hints completos
- [ ] Manejo de errores apropiado
- [ ] Logging adecuado

---

## 📚 Recursos Adicionales

- [Black Documentation](https://black.readthedocs.io/)
- [Flake8 Documentation](https://flake8.pycqa.org/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Casino V2 Architecture](../architecture/overview.md)

---

**← [Volver a Quick Start](quickstart.md)**
