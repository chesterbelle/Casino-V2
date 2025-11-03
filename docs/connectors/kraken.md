# 🔷 KrakenConnector

Conector para Kraken Futures (testnet y mainnet).

---

## 📊 **Información General**

| Propiedad | Valor |
|-----------|-------|
| **Exchange** | Kraken Futures |
| **Tipo** | Perpetual Futures |
| **Testnet** | ✅ Disponible (demo-futures.kraken.com) |
| **WebSocket** | ✅ Soportado |
| **Implementado en** | v1.8 |
| **Estado** | ✅ Validado con exchange real |

---

## 🚀 **Inicio Rápido**

### **1. Configurar Credenciales**

Agregar a `.env`:

```bash
# Kraken Futures (Demo o Live)
KRAKEN_FUTURES_API_KEY=tu_api_key_aqui
KRAKEN_FUTURES_API_SECRET=tu_api_secret_aqui
```

### **2. Uso Básico**

```python
from tables.connectors import KrakenConnector
from tables.table_ccxt_pro import TableCCXTPro

# Crear conector (testnet por defecto)
connector = KrakenConnector(testnet=True)

# Crear mesa
table = TableCCXTPro(
    connector=connector,
    symbol="BTC/USD",
    timeframe="1m"
)

# Conectar
await table.connect()
print(f"Balance: ${table.get_balance():,.2f}")

# Obtener vela
candle = await table.next_candle()
print(f"BTC: ${candle['close']:,.2f}")

# Cerrar
await table.close()
```

### **3. Con BrokerInterface**

```python
from croupier.broker_interface import BrokerInterface
from core import config

# Configurar
config.MODE = "live"
config.EXCHANGE = "KRAKEN_DEMO"  # o "KRAKEN_FUTURES" para mainnet

# Usar
broker = BrokerInterface(symbol="BTC/USD", interval="1m")
table = broker.engine.table
await table.connect()
```

---

## 🔧 **Configuración**

### **Parámetros del Constructor**

```python
KrakenConnector(
    api_key: Optional[str] = None,      # API key (auto-carga desde .env)
    secret: Optional[str] = None,       # API secret (auto-carga desde .env)
    testnet: bool = True,               # True = demo, False = mainnet
    enable_websocket: bool = False      # WebSocket (experimental)
)
```

### **URLs**

| Entorno | URL |
|---------|-----|
| **Testnet** | `https://demo-futures.kraken.com/derivatives/api/` |
| **Mainnet** | `https://futures.kraken.com/derivatives/api/` |

---

## 💱 **Símbolos**

### **Formato de Símbolos**

Kraken usa el prefijo `PF_` para perpetual futures:

| Estándar | Kraken | Descripción |
|----------|--------|-------------|
| `BTC/USD` | `PF_XBTUSD` | Bitcoin Perpetual |
| `ETH/USD` | `PF_ETHUSD` | Ethereum Perpetual |
| `SOL/USD` | `PF_SOLUSD` | Solana Perpetual |
| `XRP/USD` | `PF_XRPUSD` | Ripple Perpetual |

### **Normalización Automática**

El conector normaliza automáticamente:

```python
# Entrada estándar
connector.normalize_symbol("BTC/USD")
# Salida: "PF_XBTUSD"

# Entrada Kraken
connector.denormalize_symbol("PF_XBTUSD")
# Salida: "BTC/USD"
```

---

## 📊 **Métodos Disponibles**

### **Conexión**

```python
# Conectar
await connector.connect()

# Verificar conexión
if connector.is_connected:
    print("Conectado!")

# Cerrar
await connector.close()
```

### **Datos de Mercado**

```python
# Obtener velas OHLCV
candles = await connector.fetch_ohlcv(
    symbol="BTC/USD",
    timeframe="1m",  # 1m, 5m, 15m, 1h, 4h, 1d
    limit=100
)

# Formato de respuesta
{
    'timestamp': 1699000000000,
    'timestamp_ms': 1699000000000,
    'open': 35000.0,
    'high': 35100.0,
    'low': 34900.0,
    'close': 35050.0,
    'volume': 123.45,
    'symbol': 'BTC/USD',
    'timeframe': '1m'
}
```

### **Datos de Cuenta**

```python
# Obtener balance
balance = await connector.fetch_balance()

# Formato de respuesta
{
    'total': {'USD': 10000.0},
    'free': {'USD': 8000.0},
    'used': {'USD': 2000.0},
    'timestamp': 1699000000000,
    'currency': 'USD'
}

# Obtener posiciones abiertas
positions = await connector.fetch_positions()

# Formato de respuesta
[{
    'symbol': 'BTC/USD',
    'side': 'LONG',
    'size': 0.5,
    'entry_price': 35000.0,
    'mark_price': 35100.0,
    'liquidation_price': 30000.0,
    'unrealized_pnl': 50.0,
    'margin': 1000.0,
    'leverage': 10,
    'timestamp': 1699000000000
}]
```

### **Ejecución de Órdenes**

```python
# Orden de mercado
order = await connector.create_order(
    symbol="BTC/USD",
    side="buy",
    amount=0.1,
    order_type="market"
)

# Orden límite
order = await connector.create_order(
    symbol="BTC/USD",
    side="buy",
    amount=0.1,
    price=35000.0,
    order_type="limit"
)

# Formato de respuesta
{
    'id': 'order_123456',
    'symbol': 'BTC/USD',
    'side': 'buy',
    'type': 'market',
    'status': 'closed',
    'price': 35000.0,
    'amount': 0.1,
    'filled': 0.1,
    'remaining': 0.0,
    'cost': 3500.0,
    'fee': {'cost': 3.5, 'currency': 'USD'},
    'timestamp': 1699000000000
}
```

---

## 🔍 **Validación**

### **Script de Validación**

```bash
# Ejecutar validación completa
python utils/validate_v18.py
```

### **Resultado Esperado**

```
============================================================
TEST 1: KrakenConnector
============================================================
✅ Connector created: kraken
✅ Connected to Kraken testnet
✅ Balance fetched: 4997.92 USD
✅ Fetched 5 candles
   Latest close: $107,530.00
✅ Connector closed

============================================================
TEST 2: TableCCXTPro + KrakenConnector
============================================================
✅ Table created with connector
✅ Table connected
✅ Balance: $4,997.92
✅ Candle fetched: $107,530.00
✅ Balance refreshed: $4,997.92
✅ Table closed

============================================================
RESUMEN DE VALIDACIÓN
============================================================
KrakenConnector      ✅ PASSED
TableCCXTPro         ✅ PASSED
BrokerInterface      ✅ PASSED
============================================================
🎉 TODAS LAS VALIDACIONES PASARON!
```

---

## ⚠️ **Limitaciones y Consideraciones**

### **Rate Limits**

Kraken tiene límites de tasa:
- **Público**: 10 req/s
- **Privado**: 5 req/s

El conector usa `enableRateLimit: True` en CCXT para respetar estos límites.

### **Testnet vs Mainnet**

| Aspecto | Testnet | Mainnet |
|---------|---------|---------|
| **Dinero** | Simulado | Real |
| **Credenciales** | Diferentes | Diferentes |
| **URL** | demo-futures.kraken.com | futures.kraken.com |
| **Datos** | Reales | Reales |

### **Símbolos Soportados**

No todos los símbolos están disponibles en Kraken Futures. Consultar:
```python
await connector.connect()
markets = connector._markets
print(list(markets.keys()))
```

---

## 🐛 **Troubleshooting**

### **Error: AuthenticationError**

```
❌ Error de autenticación: Invalid API key
```

**Solución:**
1. Verificar que las credenciales en `.env` son correctas
2. Verificar que usas credenciales de testnet si `testnet=True`
3. Verificar que las credenciales tienen permisos de trading

### **Error: Symbol not found**

```
❌ Symbol BTC/USDT not supported on Kraken
```

**Solución:**
Kraken Futures usa `BTC/USD`, no `BTC/USDT`. Ver tabla de símbolos arriba.

### **Error: Insufficient balance**

```
❌ Fondos insuficientes
```

**Solución:**
En testnet, el balance es limitado. Verificar balance disponible:
```python
balance = await connector.fetch_balance()
print(balance['free']['USD'])
```

---

## 📚 **Referencias**

- [Kraken Futures API Docs](https://docs.futures.kraken.com/)
- [CCXT Kraken Futures](https://docs.ccxt.com/#/exchanges/krakenfutures)
- [Código fuente](../../tables/connectors/kraken/kraken_connector.py)
- [Tests](../../tests/test_kraken_connector.py)

---

## ✅ **Checklist de Implementación**

- [x] Conexión a testnet
- [x] Conexión a mainnet
- [x] Fetch OHLCV
- [x] Fetch balance
- [x] Fetch positions
- [x] Create order (market)
- [x] Create order (limit)
- [x] Symbol normalization
- [x] Error handling
- [x] Logging
- [x] Tests unitarios
- [x] Tests de integración
- [x] Validación con exchange real
- [x] Documentación

---

**Última actualización**: 2025-11-03
**Versión**: 1.8
**Estado**: ✅ Producción
