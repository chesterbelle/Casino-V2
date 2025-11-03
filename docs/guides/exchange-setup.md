# 🔐 Configuración de Exchanges

> Guía completa para configurar live trading en testnet

## 📋 Exchanges Soportados

| Exchange | Estado | Testnet | Real Money |
|----------|--------|---------|------------|
| **Hyperliquid** | ✅ Completo | ✅ Sí | ❌ No |
| **Binance** | ✅ Completo | ✅ Sí | ❌ No |
| **Kraken** | ✅ Completo | ✅ Sí | ❌ No |

> **⚠️ Importante**: Solo usar testnet para desarrollo. Real money viene después de validar estrategias.

---

## 🚀 Hyperliquid (Recomendado)

### Paso 1: Crear cuenta en Hyperliquid
1. Ve a [https://app.hyperliquid.xyz](https://app.hyperliquid.xyz)
2. Regístrate con email
3. Completa verificación KYC básica
4. Deposita USDC de testnet (gratis)

### Paso 2: Generar API Keys
1. Ve a **Settings** → **API Keys**
2. Click **Create API Key**
3. Configura permisos:
   - ✅ **Read Info** (leer balances)
   - ✅ **Trade** (ejecutar órdenes)
   - ❌ **Manage Positions** (no necesario)
4. Copia **API Key** y **API Secret**

### Paso 3: Configurar en Casino V2

```bash
# Crear archivo .env
touch .env

# Agregar credenciales
echo "HYPERLIQUID_API_KEY=tu_api_key_aqui" >> .env
echo "HYPERLIQUID_API_SECRET=tu_secret_aqui" >> .env
```

### Paso 4: Configurar config.py

```python
# config.py
MODE = "live"
EXCHANGE = "HYPERLIQUID"
```

### Paso 5: Verificar configuración

```bash
# Test de credenciales
python -c "
from utils.hyperliquid_env_loader import load_hyperliquid_config, validate_hyperliquid_config
config = load_hyperliquid_config()
print('✅ Config loaded:', bool(config))
print('✅ Valid config:', validate_hyperliquid_config(config))
"
```

---

## 💰 Binance Futures Testnet

### Paso 1: Crear cuenta Binance
1. Ve a [https://www.binance.com](https://www.binance.com)
2. Regístrate y completa verificación
3. Activa **Futures Trading**

### Paso 2: Configurar Testnet
1. Ve a [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Logueate con tu cuenta real de Binance
3. Deposita USDT de testnet (gratis desde faucet)

### Paso 3: Generar API Keys
1. Ve a **API Management** → **Create API**
2. Configura restricciones:
   - ✅ **Enable Futures**
   - ✅ **Enable Spot & Margin Trading** (para transfers)
   - ❌ **Enable Reading** (suficiente)
3. Copia **API Key** y **Secret Key**

### Paso 4: Configurar en Casino V2

```bash
# Agregar a .env
echo "BINANCE_API_KEY=tu_binance_key" >> .env
echo "BINANCE_API_SECRET=tu_binance_secret" >> .env
```

### Paso 5: Configurar config.py

```python
# config.py
MODE = "live"
EXCHANGE = "BINANCE_FUTURES_TESTNET"
```

### Paso 6: Verificar configuración

```bash
# Test de credenciales
python -c "
from utils.binance_env_loader import load_binance_config, validate_binance_config
config = load_binance_config()
print('✅ Config loaded:', bool(config))
print('✅ Valid config:', validate_binance_config(config))
"
```

---

## 🐙 Kraken Futures Demo

### Paso 1: Crear cuenta Kraken
1. Ve a [https://www.kraken.com](https://www.kraken.com)
2. Regístrate y completa verificación básica
3. Ve a [https://demo-futures.kraken.com](https://demo-futures.kraken.com)

### Paso 2: Generar API Keys
1. Ve a **Settings** → **API**
2. Click **Add Key**
3. Configura permisos:
   - ✅ **Query Funds** (leer balances)
   - ✅ **Create Order** (ejecutar trades)
   - ✅ **Cancel Order** (cancelar órdenes)
4. Copia **API Key** y **Private Key**

### Paso 3: Configurar en Casino V2

```bash
# Agregar a .env
echo "KRAKEN_FUTURES_API_KEY=tu_kraken_key" >> .env
echo "KRAKEN_FUTURES_API_SECRET=tu_kraken_secret" >> .env
```

### Paso 4: Configurar config.py

```python
# config.py
MODE = "live"
EXCHANGE = "KRAKEN_DEMO"
```

### Paso 5: Verificar configuración

```bash
# Test de credenciales
python -c "
from utils.kraken_env_loader import load_kraken_config, validate_kraken_config
config = load_kraken_config()
print('✅ Config loaded:', bool(config))
print('✅ Valid config:', validate_kraken_config(config))
"
```

---

## 🧪 Probar Live Trading

### Paso 1: Verificar conexión

```bash
# Test básico de conexión
python -c "
from tables.table_ccxt_pro import TableCCXTPro
import asyncio

async def test_connection():
    table = TableCCXTPro(
        exchange_id='hyperliquid',  # Cambiar según tu exchange
        symbols=['BTCUSDT'],
        timeframe='1m',
        testnet=True
    )

    try:
        await table.connect()
        print('✅ Conexión exitosa')
        await table.disconnect()
    except Exception as e:
        print(f'❌ Error de conexión: {e}')

asyncio.run(test_connection())
"
```

### Paso 2: Ejecutar live trading

```bash
# Ejecutar con timeout de seguridad
timeout 300 python main.py  # 5 minutos máximo
```

### Paso 3: Monitorear logs

Los logs mostrarán:
- ✅ Conexión WebSocket exitosa
- 📊 Datos OHLCV llegando en tiempo real
- 🎯 Señales detectadas por sensores
- 🎲 Trades ejecutados (si hay oportunidades)

---

## 🔧 Configuración Avanzada

### Balance inicial por exchange

```python
# config.py
INITIAL_BALANCE = {
    "HYPERLIQUID": 10000,
    "BINANCE_FUTURES_TESTNET": 1000,
    "KRAKEN_DEMO": 100000
}
```

### Risk management por exchange

```python
# config.py
EXCHANGE_RISK_CONFIG = {
    "HYPERLIQUID": {
        "max_position_size": 0.05,  # 5% del balance
        "max_concurrent_positions": 3
    },
    "BINANCE_FUTURES_TESTNET": {
        "max_position_size": 0.02,  # 2% del balance
        "max_concurrent_positions": 1
    }
}
```

---

## 🚨 Solución de Problemas

### Error: "API key not found"
```bash
# Verificar .env
cat .env

# Verificar que las variables están cargadas
python -c "import os; print('KEY:', bool(os.getenv('HYPERLIQUID_API_KEY')))"
```

### Error: "Invalid API key"
```
❌ Credenciales inválidas. Verifica:
1. API key copiada correctamente
2. API secret copiada correctamente
3. Permisos correctos en el exchange
4. Testnet vs mainnet
```

### Error: "Connection timeout"
```bash
# Verificar conectividad
ping api.hyperliquid.xyz
ping testnet.binancefuture.com
ping demo-futures.kraken.com

# Verificar firewall
sudo ufw status
```

### Error: "Insufficient balance"
```
💰 Deposita fondos en testnet:
- Hyperliquid: Deposita USDC desde faucet
- Binance: Usa faucet de testnet
- Kraken: Deposita USD desde demo account
```

---

## 📊 Monitoreo de Live Trading

### Logs importantes
```
✅ Conexión WebSocket exitosa
📊 Datos OHLCV llegando
🎯 Señal detectada por sensor X
🎲 Trade ejecutado: BUY 0.01 BTC @ $50000
💰 Balance actualizado: 10050.00
```

### Métricas a monitorear
- **Conexión**: WebSocket activa
- **Datos**: OHLCV llegando cada minuto
- **Señales**: Frecuencia de detección
- **Trades**: Winrate y PnL
- **Balance**: Equity en tiempo real

---

## 🔄 Cambiar entre Exchanges

```bash
# Cambiar a Binance
echo "EXCHANGE = 'BINANCE_FUTURES_TESTNET'" > config.py

# Cambiar a Kraken
echo "EXCHANGE = 'KRAKEN_DEMO'" > config.py

# Volver a Hyperliquid
echo "EXCHANGE = 'HYPERLIQUID'" > config.py
```

---

## ⚠️ Advertencias de Seguridad

### 🔐 Nunca uses mainnet para testing
- Usa **siempre testnet** para desarrollo
- Mainnet = dinero real en riesgo
- Testnet = fondos virtuales gratis

### 🔑 Protege tus API keys
- Nunca commits .env al git
- Usa permisos mínimos necesarios
- Rota keys regularmente
- Monitorea uso de API keys

### 💰 Gestión de riesgo
- Empieza con posiciones pequeñas (0.01-0.05 lotes)
- Usa stop losses siempre
- Monitorea drawdown máximo
- Ten plan de salida

---

## 🎯 Próximos Pasos

1. ✅ **Configurar exchange** - Credenciales listas
2. ⏭️ **Primer live trade** - Ejecutar con timeout
3. ⏭️ **Monitorear performance** - Logs y métricas
4. ⏭️ **Optimizar parámetros** - Según resultados

---

**📖 [← Instalación](installation.md)** | **📋 [Tutorial básico →](getting-started.md)** | **🆘 [Troubleshooting →](../development/troubleshooting.md)**
