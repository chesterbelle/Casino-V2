# 🆘 Guía de Troubleshooting

> Solución de problemas comunes en Casino V2

## 📋 Tabla de Contenidos

- [Problemas de Instalación](#-problemas-de-instalación)
- [Errores de Configuración](#-errores-de-configuración)
- [Problemas de Backtest](#-problemas-de-backtest)
- [Errores de Live Trading](#-errores-de-live-trading)
- [Problemas de WebSocket](#-problemas-de-websocket)
- [Errores de Memoria](#-errores-de-memoria)
- [Performance Issues](#-performance-issues)
- [Debugging Avanzado](#-debugging-avanzado)

---

## 🛠️ Problemas de Instalación

### "Python 3.10 not found"

**Síntomas:**
```
python3.10: command not found
```

**Soluciones:**

Ubuntu/Debian:
```bash
# Agregar repositorio deadsnakes
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Instalar Python 3.10
sudo apt install python3.10 python3.10-venv python3.10-pip
```

macOS:
```bash
# Usar Homebrew
brew install python@3.10

# O instalar desde python.org
# Descargar e instalar Python 3.10 desde https://python.org
```

Windows:
```bash
# Usar WSL
wsl --install
sudo apt install python3.10 python3.10-venv
```

### "ModuleNotFoundError" después de instalación

**Síntomas:**
```
ModuleNotFoundError: No module named 'ccxt'
```

**Soluciones:**

1. **Verificar entorno virtual:**
```bash
# Asegurarse de estar en el entorno correcto
which python  # Debe mostrar ruta del venv
source casino_env/bin/activate  # Si no está activado
```

2. **Reinstalar dependencias:**
```bash
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

3. **Verificar requirements.txt:**
```bash
cat requirements.txt
# Debe contener: ccxt, ccxtpro, pandas, numpy, etc.
```

### "Permission denied" en instalación

**Síntomas:**
```
PermissionError: [Errno 13] Permission denied
```

**Soluciones:**

```bash
# Dar permisos de ejecución
chmod +x *.py
chmod +x utils/*.py
chmod +x scripts/*.sh

# O usar sudo si es necesario (no recomendado)
# sudo pip install -r requirements.txt
```

---

## ⚙️ Errores de Configuración

### "Config file not found"

**Síntomas:**
```
FileNotFoundError: config.py not found
```

**Soluciones:**

```bash
# Verificar archivo existe
ls -la config.py

# Si no existe, crear uno básico
cat > config.py << 'EOF'
MODE = "backtest"
DATASET_PATH = "tables/data/raw/LTCUSDT_1m__1d.csv"
EXCHANGE = "HYPERLIQUID"
KELLY_FRACTION = 0.2
MAX_POSITION_SIZE = 0.02
TAKE_PROFIT = 0.01
STOP_LOSS = 0.01
EOF
```

### Variables de entorno no cargadas

**Síntomas:**
```
KeyError: 'HYPERLIQUID_API_KEY'
```

**Soluciones:**

```bash
# Verificar .env existe
ls -la .env

# Verificar contenido
cat .env

# Verificar formato correcto
# Debe ser: VARIABLE_NAME=value
# Sin espacios alrededor del =

# Recargar entorno
source .env
# o reiniciar terminal
```

### Configuración de exchange inválida

**Síntomas:**
```
ValueError: Invalid exchange configuration
```

**Soluciones:**

```python
# Verificar config.py
EXCHANGE = "HYPERLIQUID"  # Una de: HYPERLIQUID, BINANCE_FUTURES_TESTNET, KRAKEN_DEMO

# Para live trading, verificar credenciales
from utils.hyperliquid_env_loader import validate_hyperliquid_config
config = load_hyperliquid_config()
print("Valid:", validate_hyperliquid_config(config))
```

---

## 📊 Problemas de Backtest

### "Dataset not found"

**Síntomas:**
```
FileNotFoundError: tables/data/raw/LTCUSDT_1m__1d.csv not found
```

**Soluciones:**

```bash
# Crear directorios
mkdir -p tables/data/raw

# Verificar dataset existe
ls -la tables/data/raw/

# Si no existe, crear dataset de ejemplo
python -c "
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Crear datos de ejemplo
dates = pd.date_range('2024-01-01', periods=1440, freq='1min')
prices = 90 + np.random.randn(1440).cumsum() * 0.1

df = pd.DataFrame({
    'timestamp': dates,
    'open': prices,
    'high': prices * 1.001,
    'low': prices * 0.999,
    'close': prices,
    'volume': np.random.uniform(100, 1000, 1440)
})

df.to_csv('tables/data/raw/LTCUSDT_1m__1d.csv', index=False)
print('Dataset creado')
"
```

### Backtest no genera trades

**Síntomas:**
```
Trades BET: 0
```

**Causas posibles:**

1. **Sensores demasiado restrictivos:**
```python
# Hacer sensores menos restrictivos en config.py
MIN_SUPPORT = 10  # En lugar de 500
BAYES_CREDIBILITY_THRESHOLD = 0.5  # En lugar de 0.7
```

2. **Player demasiado conservador:**
```python
# Hacer player más agresivo
KELLY_FRACTION = 0.5  # En lugar de 0.2
MAX_POSITION_SIZE = 0.1  # En lugar de 0.02
```

3. **Mercado sin oportunidades:**
```bash
# Probar con datos más volátiles
DATASET_PATH = "tables/data/raw/BTCUSDT_1m__1d.csv"
```

### Resultados inconsistentes

**Síntomas:**
```
Winrate varía mucho entre runs
```

**Soluciones:**

```python
# Fijar semilla para reproducibilidad
import numpy as np
np.random.seed(42)

# O usar parámetros más estables
MEMORY_WINDOW = 1000  # Más datos históricos
MIN_SUPPORT = 1000   # Más trades requeridos
```

---

## 🔴 Errores de Live Trading

### "API credentials invalid"

**Síntomas:**
```
AuthenticationError: Invalid API key
```

**Soluciones:**

```bash
# Verificar credenciales en .env
cat .env

# Para Hyperliquid
echo "HYPERLIQUID_API_KEY=tu_key_correcta" >> .env
echo "HYPERLIQUID_API_SECRET=tu_secret_correcto" >> .env

# Test de conexión
python -c "
from utils.hyperliquid_env_loader import load_hyperliquid_config, validate_hyperliquid_config
config = load_hyperliquid_config()
print('Config loaded:', bool(config))
print('Valid:', validate_hyperliquid_config(config))
"
```

### "Connection timeout"

**Síntomas:**
```
TimeoutError: Connection timed out
```

**Soluciones:**

```bash
# Verificar conectividad de red
ping api.hyperliquid.xyz
curl -I https://api.hyperliquid.xyz

# Verificar firewall
sudo ufw status

# Intentar con diferentes timeouts
# En config.py
REQUEST_TIMEOUT = 30000  # 30 segundos
```

### "Insufficient balance"

**Síntomas:**
```
ExchangeError: Insufficient balance
```

**Soluciones:**

```bash
# Verificar balance en exchange
# Para Hyperliquid: Depositar USDC en testnet
# Para Binance: Usar faucet de testnet
# Para Kraken: Depositar USD en demo account

# Verificar configuración de balance inicial
INITIAL_BALANCE = 1000  # En config.py
```

---

## 🔌 Problemas de WebSocket

### "WebSocket connection failed"

**Síntomas:**
```
ConnectionError: WebSocket connection failed
```

**Soluciones:**

```python
# Verificar configuración de exchange
EXCHANGE = "HYPERLIQUID"  # Una de las soportadas

# Test básico de WebSocket
python -c "
import asyncio
from tables.table_ccxt_pro import TableCCXTPro

async def test():
    table = TableCCXTPro('hyperliquid', ['BTC/USDT'])
    try:
        await table.connect()
        print('✅ WebSocket conectado')
        await table.disconnect()
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test())
"
```

### Datos no llegan en tiempo real

**Síntomas:**
```
No OHLCV updates received
```

**Soluciones:**

```python
# Verificar símbolo soportado
SYMBOLS = ['BTC/USDT']  # Para Hyperliquid
# SYMBOLS = ['BTCUSDT']  # Para Binance
# SYMBOLS = ['PF_XBTUSD']  # Para Kraken

# Verificar timeframe
TIMEFRAME = '1m'  # Soportado por todos

# Monitorear logs
python main.py --verbose 2>&1 | grep -i websocket
```

### WebSocket se desconecta

**Síntomas:**
```
WebSocket disconnected, attempting reconnect...
```

**Soluciones:**

```python
# Aumentar timeouts
WEBSOCKET_TIMEOUT = 60000  # 60 segundos

# Verificar estabilidad de red
ping -c 10 api.hyperliquid.xyz

# Usar VPN si hay problemas de red local
```

---

## 🧠 Errores de Memoria

### "Memory file corrupted"

**Síntomas:**
```
JSONDecodeError: Expecting ',' delimiter
```

**Soluciones:**

```bash
# Respaldar y recrear memoria
cp gemini/data/memory_state.json gemini/data/memory_state.json.backup

# Limpiar archivos de memoria
rm gemini/data/memory_log.csv
rm gemini/data/gemini_decisions.csv
rm gemini/data/gemini_trade_results.csv

# Reiniciar memoria
python -c "
from gemini.memory import Memory
memory = Memory()
memory.clear()
print('Memoria reiniciada')
"
```

### Memoria no aprende

**Síntomas:**
```
Memory not updating after trades
```

**Soluciones:**

```python
# Verificar configuración de memoria
AUTOSAVE_INTERVAL = 10  # Guardar cada 10 trades
MEMORY_WINDOW = 500    # Ventana de análisis

# Verificar permisos de escritura
ls -la gemini/data/
chmod 755 gemini/data/
```

### Credibilidad baja

**Síntomas:**
```
Bayesian credibility: 0.15 (too low)
```

**Soluciones:**

```python
# Reducir umbrales para más aprendizaje
BAYES_CREDIBILITY_THRESHOLD = 0.6  # En lugar de 0.7
MIN_SUPPORT = 50  # En lugar de 500

# O entrenar más tiempo
# Ejecutar más backtests para acumular datos
```

---

## ⚡ Performance Issues

### Backtest muy lento

**Síntomas:**
```
Backtest toma más de 5 minutos
```

**Soluciones:**

```python
# Optimizar configuración
AUTOSAVE_INTERVAL = 100  # Menos saves
MEMORY_WINDOW = 200     # Menos datos históricos

# Usar datos más pequeños
DATASET_PATH = "tables/data/raw/BTCUSDT_15m__1d.csv"  # 15m en lugar de 1m

# Verificar CPU/memoria
top  # o htop
free -h
```

### Alta uso de memoria

**Síntomas:**
```
Memory usage > 2GB
```

**Soluciones:**

```python
# Reducir ventana de memoria
MEMORY_WINDOW = 200

# Limpiar memoria periódicamente
# En gemini/memory.py
if len(self._memory) > 10000:
    self._cleanup_old_entries()
```

### Live trading lento

**Síntomas:**
```
Latency > 2 segundos
```

**Soluciones:**

```python
# Optimizar WebSocket
WEBSOCKET_BUFFER_SIZE = 1000
MAX_CONCURRENT_REQUESTS = 5

# Verificar red
speedtest-cli
ping api.hyperliquid.xyz
```

---

## 🔍 Debugging Avanzado

### Logs detallados

```bash
# Ejecutar con máximo verbosidad
python main.py --debug 2>&1 | tee debug.log

# Filtrar logs específicos
grep -i error debug.log
grep -i websocket debug.log
grep -i trade debug.log
```

### Profiling de performance

```bash
# Instalar py-spy
pip install py-spy

# Profile durante ejecución
py-spy top --pid $(pgrep -f "python main.py")

# O usar cProfile
python -m cProfile -s time main.py > profile.txt
```

### Test de componentes individuales

```python
# Test Gemini
from gemini.gemini_core import Gemini
gemini = Gemini()
print("Gemini OK")

# Test Sensors
from sensors.sensor_manager import SensorManager
sensors = SensorManager()
print("Sensors OK:", len(sensors.sensors))

# Test Players
from players.kelly_player import calculate_position_size
result = calculate_position_size(None, 1000)
print("Players OK")
```

### Database inspection

```bash
# Ver estado de memoria
python -c "
import pandas as pd
df = pd.read_csv('gemini/data/memory_log.csv')
print('Memory shape:', df.shape)
print('Top strategies:')
print(df.nlargest(5, 'winrate')[['strategy', 'winrate', 'total_trades']])
"

# Ver decisiones recientes
tail -20 gemini/data/gemini_decisions.csv
```

### Network debugging

```bash
# Capturar tráfico de red
sudo tcpdump -i any port 443 -w capture.pcap

# Ver conexiones activas
netstat -tlnp | grep python

# Test de conectividad
curl -v https://api.hyperliquid.xyz/info
```

---

## 🚑 Recuperación de Emergencia

### Sistema completamente roto

```bash
# Respaldar configuración importante
cp config.py config_backup.py
cp .env .env_backup

# Limpiar todo y reinstalar
rm -rf casino_env/
rm -rf gemini/data/
rm -rf __pycache__/

# Reiniciar desde cero
git checkout .  # Descartar cambios locales
# Seguir guía de instalación
```

### Datos corruptos

```bash
# Limpiar datos corruptos
rm -rf gemini/data/
rm -rf tables/data/raw/

# Recrear estructura
mkdir -p gemini/data/
mkdir -p tables/data/raw/

# Reiniciar memoria
touch gemini/data/memory_log.csv
echo '{"version": "1.6", "created": "'$(date)'"}' > gemini/data/memory_state.json
```

### Exchange bloqueado

```bash
# Cambiar exchange
EXCHANGE = "BINANCE_FUTURES_TESTNET"  # En config.py

# O cambiar a backtest
MODE = "backtest"
```

---

## 📞 Contacto y Soporte

Si estos pasos no resuelven tu problema:

1. **Reúne información de debug:**
```bash
# Crear reporte de debug
python -c "
import sys
import platform
print('Python:', sys.version)
print('OS:', platform.system(), platform.release())
print('Arquitectura:', platform.machine())

try:
    import ccxt
    print('CCXT version:', ccxt.__version__)
except:
    print('CCXT: NOT INSTALLED')

try:
    import ccxtpro
    print('CCXT Pro: OK')
except:
    print('CCXT Pro: NOT INSTALLED')
" > debug_info.txt
```

2. **Abre un issue en GitHub** con:
   - Descripción del problema
   - Pasos para reproducir
   - Logs relevantes
   - `debug_info.txt`

3. **Únete a la comunidad:**
   - [GitHub Discussions](https://github.com/chesterbelle/Casino-V2/discussions)
   - [Issues](https://github.com/chesterbelle/Casino-V2/issues)

---

**Recuerda:** La mayoría de problemas se resuelven verificando configuración, credenciales y conectividad de red. ¡No te rindas! 🎰

---

**📖 [← Getting Started](../guides/getting-started.md)** | **🛠️ [Instalación](../guides/installation.md)** | **🔐 [Exchange Setup](../guides/exchange-setup.md)**