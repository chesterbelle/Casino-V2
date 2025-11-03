# 🛠️ Guía de Instalación Completa

> Instalación paso a paso de Casino V2 desde cero

## 📋 Requisitos Previos

### Sistema Operativo
- ✅ **Linux** (Ubuntu 20.04+, Debian 10+, CentOS 7+)
- ✅ **macOS** (10.15+)
- ✅ **Windows** (10+, con WSL recomendado)

### Python
- ✅ **Python 3.10 o superior**
- ❌ Python 3.9 o inferior no soportado

### Hardware Recomendado
- **RAM**: 4GB mínimo, 8GB recomendado
- **Disco**: 2GB libre para datos históricos
- **CPU**: 2 cores mínimo

---

## 🚀 Instalación Rápida

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/chesterbelle/Casino-V2.git
cd Casino-V2
```

### Paso 2: Instalar Python (si no tienes Python 3.10+)

#### Ubuntu/Debian
```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# Verificar versión
python3.10 --version
```

#### macOS (con Homebrew)
```bash
# Instalar Homebrew si no lo tienes
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar Python
brew install python@3.10

# Verificar versión
python3.10 --version
```

#### Windows (WSL recomendado)
```bash
# Instalar WSL2
wsl --install

# En WSL, instalar Python
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip -y
```

### Paso 3: Crear entorno virtual

```bash
# Crear entorno virtual
python3.10 -m venv casino_env

# Activar entorno virtual
source casino_env/bin/activate  # Linux/macOS
# casino_env\Scripts\activate   # Windows

# Verificar que estamos en el entorno correcto
which python  # Debe mostrar la ruta del entorno virtual
```

### Paso 4: Instalar dependencias

```bash
# Instalar todas las dependencias
pip install -r requirements.txt

# Verificar instalación
python -c "import ccxt, ccxtpro, pandas, numpy; print('✅ Todas las dependencias instaladas')"
```

---

## ⚙️ Configuración Inicial

### Paso 1: Archivo de configuración básico

```bash
# Copiar configuración de ejemplo
cp config.py config_backup.py

# Editar config.py según tus necesidades
nano config.py  # o tu editor favorito
```

**Configuración mínima recomendada:**

```python
# config.py
MODE = "backtest"  # Empezar con backtest
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"
EXCHANGE = "HYPERLIQUID"  # Para live trading después
```

### Paso 2: Descargar datos de ejemplo

```bash
# Crear directorios necesarios
mkdir -p tables/data/raw

# Descargar dataset de ejemplo
python -c "
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Generar datos de ejemplo LTCUSDT
dates = pd.date_range('2024-01-01', periods=1440, freq='1min')
np.random.seed(42)

# Generar precios realistas
base_price = 92.0
prices = []
current_price = base_price

for i in range(1440):
    # Movimiento aleatorio pero realista
    change = np.random.normal(0, 0.001)  # ~0.1% volatilidad por minuto
    current_price *= (1 + change)
    prices.append(current_price)

# Crear DataFrame
df = pd.DataFrame({
    'timestamp': dates,
    'open': prices,
    'high': [p * (1 + abs(np.random.normal(0, 0.0005))) for p in prices],
    'low': [p * (1 - abs(np.random.normal(0, 0.0005))) for p in prices],
    'close': prices,
    'volume': np.random.uniform(100, 1000, 1440)
})

# Calcular high/low correctamente
for i in range(len(df)):
    o, c = df.loc[i, 'open'], df.loc[i, 'close']
    df.loc[i, 'high'] = max(o, c) * (1 + abs(np.random.normal(0, 0.0005)))
    df.loc[i, 'low'] = min(o, c) * (1 - abs(np.random.normal(0, 0.0005)))

# Guardar
df.to_csv('tables/data/raw/LTCUSDT_1m__1d.csv', index=False)
print('✅ Dataset de ejemplo creado: tables/data/raw/LTCUSDT_1m__1d.csv')
"
```

---

## 🧪 Verificación de Instalación

### Paso 1: Ejecutar tests básicos

```bash
# Tests de arquitectura
python test_phase1.py

# Tests de mejoras
python test_mejoras_futurechanges.py

# Tests WebSocket
python test_websocket_integration.py
```

### Paso 2: Primer backtest

```bash
# Ejecutar backtest básico
python main.py

# Deberías ver salida como:
# 🎰 Casino V2 — Backtest Mode
# 🔄 MODO: Single-Asset Backtest
# 🎮 Player seleccionado: PAROLI
# ...
# Balance final: 10002.08 (+0.02%)
```

### Paso 3: Verificar WebSocket (opcional)

```bash
# Test básico de WebSocket (sin credenciales)
python -c "
from tables.table_ccxt_pro import TableCCXTPro
print('✅ TableCCXTPro importado correctamente')
print('Métodos disponibles:', [m for m in dir(TableCCXTPro) if not m.startswith('_')])
"
```

---

## 🔐 Configuración de Exchanges (Live Trading)

### Hyperliquid (Recomendado)

```bash
# Crear archivo .env
touch .env

# Editar .env con tus credenciales
echo "HYPERLIQUID_API_KEY=tu_api_key_aqui" >> .env
echo "HYPERLIQUID_API_SECRET=tu_api_secret_aqui" >> .env

# Configurar en config.py
echo "MODE = 'live'" >> config.py
echo "EXCHANGE = 'HYPERLIQUID'" >> config.py
```

### Binance Testnet

```bash
# Agregar a .env
echo "BINANCE_API_KEY=tu_binance_key" >> .env
echo "BINANCE_API_SECRET=tu_binance_secret" >> .env

# Configurar en config.py
echo "EXCHANGE = 'BINANCE_FUTURES_TESTNET'" >> config.py
```

### Kraken Demo

```bash
# Agregar a .env
echo "KRAKEN_FUTURES_API_KEY=tu_kraken_key" >> .env
echo "KRAKEN_FUTURES_API_SECRET=tu_kraken_secret" >> .env

# Configurar en config.py
echo "EXCHANGE = 'KRAKEN_DEMO'" >> config.py
```

---

## 🚀 Uso Básico

### Backtest
```bash
# Modo backtest (default)
python main.py
```

### Live Trading
```bash
# Cambiar a modo live en config.py
# MODE = "live"
python main.py
```

### Cambiar Player
```bash
# Usar Fixed Player
python main.py --player=fixed

# Usar Kelly Player
python main.py --player=kelly
```

---

## 🔧 Solución de Problemas

### Error: "Python 3.10 not found"
```bash
# Instalar Python 3.10+
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.10 python3.10-venv -y
```

### Error: "ModuleNotFoundError"
```bash
# Reinstalar dependencias
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Error: "Permission denied"
```bash
# Dar permisos de ejecución
chmod +x *.py
chmod +x utils/*.py
```

### Error: "No module named 'dotenv'"
```bash
# Instalar python-dotenv
pip install python-dotenv
```

---

## 📊 Verificación Final

Ejecuta este script para verificar que todo funciona:

```bash
python -c "
print('🔍 Verificación completa de Casino V2')
print('=' * 50)

# Verificar Python
import sys
print(f'✅ Python: {sys.version}')

# Verificar dependencias críticas
try:
    import ccxt
    print('✅ CCXT instalado')
except ImportError:
    print('❌ CCXT no encontrado')

try:
    import ccxtpro
    print('✅ CCXT Pro instalado')
except ImportError:
    print('❌ CCXT Pro no encontrado')

try:
    import pandas as pd
    print('✅ Pandas instalado')
except ImportError:
    print('❌ Pandas no encontrado')

# Verificar módulos propios
try:
    from gemini.gemini_core import Gemini
    print('✅ Gemini importado')
except ImportError as e:
    print(f'❌ Error importando Gemini: {e}')

try:
    from tables.table_ccxt_pro import TableCCXTPro
    print('✅ TableCCXTPro importado')
except ImportError as e:
    print(f'❌ Error importando TableCCXTPro: {e}')

print('=' * 50)
print('🎰 ¡Casino V2 listo para usar!')
"
```

---

## 🎯 Próximos Pasos

1. ✅ **Instalación completa** - Sistema operativo
2. ⏭️ **Primer backtest** - Verificar funcionamiento
3. ⏭️ **Configurar exchange** - Para live trading
4. ⏭️ **Crear custom player** - Personalizar estrategia

---

**📖 [← Volver al README](../README.md)** | **📋 [Tutorial básico →](getting-started.md)**