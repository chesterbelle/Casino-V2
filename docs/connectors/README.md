# 🔌 Conectores de Exchange

Los conectores son módulos que permiten a Casino V2 comunicarse con diferentes exchanges de criptomonedas de manera estandarizada.

---

## 📚 **Arquitectura**

```
BaseConnector (Interface Abstracta)
    ↓
KrakenConnector, BinanceConnector, HyperliquidConnector, etc.
    ↓
TableCCXTPro (Mesa) usa cualquier conector
```

### **Separación de Responsabilidades**

| Componente | Responsabilidad |
|------------|----------------|
| **Mesa (TableCCXTPro)** | Lógica de negocio: balance, positions, TP/SL, validación |
| **Conector** | Comunicación con exchange: REST, WebSocket, normalización |

---

## 🎯 **BaseConnector Interface**

Todos los conectores deben implementar esta interface:

```python
class BaseConnector(ABC):
    # Conexión
    async def connect() -> None
    async def close() -> None

    # Datos de mercado
    async def fetch_ohlcv(symbol, timeframe, limit) -> List[Dict]

    # Datos de cuenta
    async def fetch_balance() -> Dict
    async def fetch_positions() -> List[Dict]

    # Ejecución de órdenes
    async def create_order(symbol, side, amount, price, order_type) -> Dict

    # Utilidades
    def normalize_symbol(symbol) -> str
    def denormalize_symbol(exchange_symbol) -> str

    # Propiedades
    @property
    def exchange_name() -> str
    @property
    def is_connected() -> bool
```

---

## 📋 **Conectores Disponibles**

### **✅ KrakenConnector** (v1.8)
- **Estado**: Implementado y validado
- **Exchange**: Kraken Futures
- **Testnet**: ✅ Disponible
- **Documentación**: [kraken.md](./kraken.md)

### **🔜 BinanceConnector** (v1.9)
- **Estado**: Planificado
- **Exchange**: Binance Futures
- **Testnet**: ✅ Disponible

### **🔜 HyperliquidConnector** (v2.0)
- **Estado**: Planificado
- **Exchange**: Hyperliquid
- **Testnet**: ❌ No disponible

---

## 🛠️ **Cómo Usar un Conector**

### **Uso Básico**

```python
from tables.connectors import KrakenConnector
from tables.table_ccxt_pro import TableCCXTPro

# 1. Crear conector
connector = KrakenConnector(testnet=True)

# 2. Crear mesa con conector
table = TableCCXTPro(
    connector=connector,
    symbol="BTC/USD",
    timeframe="1m"
)

# 3. Conectar
await table.connect()

# 4. Usar
candle = await table.next_candle()
balance = table.get_balance()

# 5. Cerrar
await table.close()
```

### **Con BrokerInterface**

```python
from croupier.broker_interface import BrokerInterface
from core import config

# Configurar exchange en config.py
config.MODE = "live"
config.EXCHANGE = "KRAKEN_DEMO"

# BrokerInterface crea el conector automáticamente
broker = BrokerInterface(symbol="BTC/USD", interval="1m")
table = broker.engine.table

# Conectar y usar
await table.connect()
```

---

## 📝 **Cómo Crear un Nuevo Conector**

### **Paso 1: Crear Estructura**

```
tables/connectors/
└── nombre_exchange/
    ├── __init__.py
    ├── nombre_exchange_connector.py
    ├── nombre_exchange_constants.py
    └── (opcional) nombre_exchange_auth.py
```

### **Paso 2: Implementar BaseConnector**

```python
# tables/connectors/nombre_exchange/nombre_exchange_connector.py

from ..connector_base import BaseConnector

class NombreExchangeConnector(BaseConnector):
    def __init__(self, api_key, secret, testnet=True):
        self.api_key = api_key
        self.secret = secret
        self.testnet = testnet
        self._connected = False

    async def connect(self):
        # Implementar conexión
        pass

    async def fetch_ohlcv(self, symbol, timeframe, limit):
        # Implementar fetch OHLCV
        pass

    # ... implementar todos los métodos abstractos
```

### **Paso 3: Crear Constantes**

```python
# tables/connectors/nombre_exchange/nombre_exchange_constants.py

# URLs
TESTNET_URL = "https://testnet.exchange.com"
MAINNET_URL = "https://api.exchange.com"

# Symbol mapping
SYMBOL_MAPPING = {
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
}

# Configuración
DEFAULT_CONFIG = {
    "enableRateLimit": True,
    "timeout": 30000,
}
```

### **Paso 4: Exportar**

```python
# tables/connectors/nombre_exchange/__init__.py

from .nombre_exchange_connector import NombreExchangeConnector

__all__ = ["NombreExchangeConnector"]
```

```python
# tables/connectors/__init__.py

from .nombre_exchange import NombreExchangeConnector

__all__ = [..., "NombreExchangeConnector"]
```

### **Paso 5: Integrar con BrokerInterface**

```python
# croupier/broker_interface.py

def _create_live_engine(self, symbol, interval, exchange):
    if "NOMBRE_EXCHANGE" in exchange:
        connector = NombreExchangeConnector(testnet=True)
        default_symbol = "BTC/USD"
    # ...
```

### **Paso 6: Tests**

```python
# tests/test_nombre_exchange_connector.py

import pytest
from tables.connectors import NombreExchangeConnector

@pytest.mark.asyncio
async def test_connector_connect():
    connector = NombreExchangeConnector(testnet=True)
    await connector.connect()
    assert connector.is_connected is True
    await connector.close()
```

---

## ✅ **Checklist para Nuevo Conector**

- [ ] Implementar todos los métodos de `BaseConnector`
- [ ] Crear archivo de constantes (URLs, símbolos, config)
- [ ] Normalización de símbolos (exchange ↔ estándar)
- [ ] Normalización de respuestas (OHLCV, balance, orders)
- [ ] Manejo de errores específicos del exchange
- [ ] Logging detallado
- [ ] Tests unitarios
- [ ] Tests de integración con testnet
- [ ] Documentación en `docs/connectors/nombre_exchange.md`
- [ ] Integración con `BrokerInterface`
- [ ] Validación con `utils/validate_v18.py`

---

## 🔍 **Referencia**

- **Ejemplo completo**: Ver `tables/connectors/kraken/kraken_connector.py`
- **Interface**: Ver `tables/connectors/connector_base.py`
- **Tests**: Ver `tests/test_kraken_connector.py`
- **Validación**: Ver `utils/validate_v18.py`

---

## 📚 **Recursos Externos**

- [Hummingbot Connectors](https://hummingbot.org/developers/connectors/) - Inspiración arquitectónica
- [CCXT Documentation](https://docs.ccxt.com/) - Librería base para exchanges
- [Kraken Futures API](https://docs.futures.kraken.com/) - Ejemplo de API
