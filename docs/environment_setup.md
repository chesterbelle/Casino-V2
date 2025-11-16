# Environment Setup - Casino V2 Trading Bot

## Estructura del Environment

### 1. Virtual Environment (.venv)
- **Ubicación**: `/home/chesterbelle/Casino-V2/.venv/`
- **Python**: Python 3.13
- **Activación**: `source .venv/bin/activate`

### 2. Comandos Disponibles en el Environment
El `.venv/bin/` contiene:
- **python/python3/python3.13**: Intérprete Python
- **pytest**: Framework para ejecutar tests
- **pip/pip3**: Gestor de paquetes
- **black**: Formateador de código
- **flake8**: Linter de código
- **mypy**: Verificador de tipos estáticos
- **pre-commit**: Hooks de pre-commit

### 3. Cómo Ejecutar Código

#### Tests
```bash
# Método 1: Activar environment primero
source .venv/bin/activate
python tests/test_oco_execution_debug.py

# Método 2: Usar pytest del environment
.venv/bin/pytest tests/test_oco_execution_debug.py -s

# Método 3: Directamente con python del environment
.venv/bin/python tests/test_oco_execution_debug.py
```

#### Scripts del Bot
```bash
# Ejecutar main.py
.venv/bin/python main.py

# Ejecutar scripts de debugging
.venv/bin/python debug_positions_raw.py
```

### 4. Variables de Entorno
- **Archivo**: `.env` en la raíz del proyecto
- **Contenido típico**:
  - API keys de exchanges
  - Configuración de Gemini
  - Opciones de logging

### 5. PYTHONPATH
- **Importante**: El PYTHONPATH debe incluir la raíz del proyecto
- **Comando típico**: `PYTHONPATH=/home/chesterbelle/Casino-V2 python script.py`

### 6. Scripts de Ejecución Convenientes
- `run_oco_debug_test.sh`: Script para ejecutar el test de OCO
- `monitor_testing.sh`: Script para monitorear tests
- `run_ronda1_monitored.sh`: Script para rondas monitoreadas

### 7. Estructura de Proyectos Importantes
- **tests/**: Tests unitarios y de integración
- **core/**: Lógica principal del bot
- **config/**: Archivos de configuración
- **logs/**: Archivos de log generados

### 8. Problemas Comunes y Soluciones

#### Error "ModuleNotFoundError"
```bash
# Solución: Asegurar PYTHONPATH correcto
export PYTHONPATH=/home/chesterbelle/Casino-V2:$PYTHONPATH
python script.py
```

#### Error de permisos o environment no activado
```bash
# Verificar que el environment está activado
which python
# Debería mostrar: /home/chesterbelle/Casino-V2/.venv/bin/python
```

#### Tests no encuentran módulos
```bash
# Usar pytest con el environment correcto
.venv/bin/pytest tests/test_file.py -s
```

### 9. Flujo de Trabajo Típico
1. Activar environment: `source .venv/bin/activate`
2. Verificar PYTHONPATH si es necesario
3. Ejecutar comandos/scripts
4. Desactivar environment al terminar: `deactivate`

### 10. Notas Importantes
- El environment ya está configurado con todas las dependencias necesarias
- No se necesita instalar paquetes adicionales a menos que se agregue nueva funcionalidad
- Los scripts del proyecto asumen que el environment está activado
- Los logs se guardan en `logs/` independientemente del environment
