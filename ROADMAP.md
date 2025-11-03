# 🗺️ ROADMAP v1.8 - Mesa + Conectores

> **Objetivo**: Refactorizar arquitectura de mesas para usar conectores modulares por exchange

---

## 🎯 **Visión General**

### **Problema Actual**
- `TableCCXTPro` es monolítica y multi-exchange
- Difícil de mantener y debuggear
- Documentación de CCXT confusa
- Cada exchange tiene peculiaridades difíciles de manejar en una sola clase

### **Solución Propuesta**
Arquitectura **Mesa + Conectores** inspirada en Hummingbot:
- **Mesa Base** (`TableCCXTPro`): Lógica de negocio común (balance, positions, TP/SL)
- **Conectores**: Implementaciones específicas por exchange (Kraken, Binance, etc.)

### **Beneficios**
- ✅ Código más limpio y mantenible
- ✅ Más fácil de debuggear (errores aislados por exchange)
- ✅ Más fácil de testear (tests específicos por conector)
- ✅ Escalable (agregar exchange = nuevo conector)
- ✅ Reutilización de código (lógica común en la Mesa)

---

## 📁 **Arquitectura Propuesta**

```
tables/
├── table_base.py                    # Base abstracta (sin cambios)
├── table_backtest.py                # Backtest (sin cambios)
├── table_ccxt_pro.py                # Mesa principal refactorizada
├── table_ccxt_pro_legacy.py         # Código original (referencia)
├── balance_manager.py               # Gestión de balance (sin cambios)
├── position_tracker.py              # Tracking de posiciones (sin cambios)
│
└── connectors/
    ├── __init__.py                  # Exports
    ├── connector_base.py            # Interface abstracta del conector
    │
    ├── kraken/
    │   ├── __init__.py
    │   ├── kraken_connector.py      # Conector principal Kraken
    │   ├── kraken_auth.py           # Autenticación específica (opcional)
    │   └── kraken_constants.py      # URLs, endpoints, configuración
    │
    ├── binance/                     # Futuro (v1.9+)
    │   └── ...
    │
    └── hyperliquid/                 # Futuro (v2.0+)
        └── ...
```

---

## 🔧 **Componentes Clave**

### **1. BaseConnector (Interface)**
```python
# tables/connectors/connector_base.py

class BaseConnector(ABC):
    """Interface abstracta para conectores de exchange."""

    @abstractmethod
    async def connect(self) -> None:
        """Conectar al exchange (WebSocket + REST)."""
        pass

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict]:
        """Obtener velas OHLCV."""
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: str,  # 'buy' | 'sell'
        amount: float,
        price: Optional[float] = None,
        order_type: str = 'market'
    ) -> Dict:
        """Crear orden en el exchange."""
        pass

    @abstractmethod
    async def fetch_balance(self) -> Dict:
        """Obtener balance de la cuenta."""
        pass

    @abstractmethod
    async def fetch_positions(self) -> List[Dict]:
        """Obtener posiciones abiertas (para perpetuals)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cerrar conexiones (WebSocket + REST)."""
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Normalizar símbolo al formato del exchange."""
        pass
```

### **2. KrakenConnector (Implementación)**
```python
# tables/connectors/kraken/kraken_connector.py

class KrakenConnector(BaseConnector):
    """Conector específico para Kraken Futures."""

    def __init__(
        self,
        api_key: str,
        secret: str,
        testnet: bool = True,
        enable_websocket: bool = True
    ):
        self.api_key = api_key
        self.secret = secret
        self.testnet = testnet
        self.enable_websocket = enable_websocket

        # CCXT exchange instance
        self.exchange = None

        # WebSocket connection (si está habilitado)
        self.ws = None

        # Cache de datos
        self._markets = {}
        self._last_ohlcv = {}

    async def connect(self) -> None:
        """Conectar a Kraken."""
        # 1. Setup CCXT
        self.exchange = ccxt_async.krakenfutures({
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,
        })

        # 2. Configurar URLs según testnet/mainnet
        if self.testnet:
            self.exchange.urls['api'] = KRAKEN_DEMO_URLS

        # 3. Cargar mercados
        await self.exchange.load_markets()
        self._markets = self.exchange.markets

        # 4. Setup WebSocket (si está habilitado)
        if self.enable_websocket:
            await self._setup_websocket()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100):
        """Obtener velas OHLCV de Kraken."""
        # Normalizar símbolo
        normalized_symbol = self.normalize_symbol(symbol)

        # Fetch desde CCXT
        ohlcv = await self.exchange.fetch_ohlcv(
            normalized_symbol,
            timeframe,
            limit=limit
        )

        # Normalizar formato
        return self._normalize_ohlcv(ohlcv)

    # ... más métodos
```

### **3. TableCCXTPro Refactorizada**
```python
# tables/table_ccxt_pro.py

class TableCCXTPro(BaseTable):
    """Mesa que usa conectores intercambiables."""

    def __init__(
        self,
        connector: BaseConnector,
        symbol: str,
        timeframe: str = "1m"
    ):
        super().__init__()

        # Inyección de dependencia del conector
        self.connector = connector

        self.symbol = symbol
        self.timeframe = timeframe

        # Componentes de la Mesa (lógica común)
        self.balance_manager = BalanceManager()
        self.position_tracker = PositionTracker()

        # Estado
        self._connected = False

    async def connect(self):
        """Conectar usando el conector."""
        await self.connector.connect()

        # Inicializar balance
        balance_data = await self.connector.fetch_balance()
        self._update_balance(balance_data)

        self._connected = True

    async def next_candle(self) -> Optional[Dict]:
        """Obtener siguiente vela."""
        if not self._connected:
            raise RuntimeError("Mesa no conectada. Llama a connect() primero.")

        ohlcv = await self.connector.fetch_ohlcv(
            self.symbol,
            self.timeframe,
            limit=1
        )

        return ohlcv[0] if ohlcv else None

    async def execute_order(self, order: Dict) -> Dict:
        """Ejecutar orden usando el conector."""
        # 1. Validaciones de la Mesa (balance, limits, etc.)
        if not self._validate_order(order):
            return {
                'status': 'rejected',
                'reason': 'validation_failed'
            }

        # 2. Ejecutar a través del conector
        result = await self.connector.create_order(
            symbol=order['symbol'],
            side=order['side'],
            amount=order['amount'],
            price=order.get('price'),
            order_type=order.get('type', 'market')
        )

        # 3. Actualizar estado interno (balance, positions)
        self._update_after_order(result)

        return result

    # ... métodos de validación y actualización de estado
```

---

## 📋 **Plan de Implementación**

### **Fase 1: Preparación** ✅
- [x] Crear `ROADMAP.md`
- [x] Renombrar `table_ccxt_pro.py` → `table_ccxt_pro_legacy.py`
- [ ] Crear estructura de carpetas `connectors/`

### **Fase 2: Base Architecture** (Día 1)
- [ ] Crear `connectors/__init__.py`
- [ ] Crear `connectors/connector_base.py` (interface abstracta)
- [ ] Documentar interface con docstrings completos
- [ ] Tests básicos de la interface

### **Fase 3: Kraken Connector** (Días 2-3)
- [ ] Crear `connectors/kraken/__init__.py`
- [ ] Crear `connectors/kraken/kraken_constants.py`
  - URLs de testnet/mainnet
  - Endpoints específicos
  - Configuración de timeframes
  - Límites de rate
- [ ] Crear `connectors/kraken/kraken_connector.py`
  - Extraer lógica de `table_ccxt_pro_legacy.py`
  - Implementar todos los métodos abstractos
  - Manejo de errores específicos de Kraken
  - Normalización de respuestas
- [ ] (Opcional) Crear `connectors/kraken/kraken_auth.py`
  - Si la autenticación es compleja
- [ ] Tests del conector Kraken
  - Tests unitarios (mocks)
  - Tests de integración (testnet)

### **Fase 4: Refactorizar TableCCXTPro** (Día 4)
- [ ] Crear nuevo `table_ccxt_pro.py` vacío
- [ ] Extraer lógica común de `table_ccxt_pro_legacy.py`:
  - Balance management
  - Position tracking
  - Order validation
  - TP/SL logic
  - Logging
- [ ] Implementar inyección de dependencia del conector
- [ ] Tests de integración Mesa + Conector

### **Fase 5: Integration & Testing** (Día 5)
- [ ] Actualizar `core/live_session.py` para usar nueva arquitectura
- [ ] Actualizar `main.py` para instanciar correctamente
- [ ] Tests end-to-end con Kraken testnet
- [ ] Validar que todo funciona igual que antes

### **Fase 6: Cleanup & Documentation** (Día 6)
- [ ] Eliminar código duplicado
- [ ] Mejorar logging y error handling
- [ ] Actualizar documentación:
  - `docs/VISION.md`
  - `docs/architecture/overview.md`
  - Crear `docs/connectors/kraken.md`
- [ ] Actualizar `core/version.py` con highlights de v1.8

---

## 🎯 **Criterios de Éxito**

### **Funcional**
- ✅ Sistema funciona igual que antes (sin regresiones)
- ✅ Kraken testnet conecta y ejecuta órdenes
- ✅ Balance se actualiza correctamente
- ✅ Positions se trackean correctamente
- ✅ TP/SL funcionan como antes

### **Arquitectura**
- ✅ Código más limpio y modular
- ✅ Separación clara Mesa vs Conector
- ✅ Fácil agregar nuevos exchanges
- ✅ Tests pasan al 100%
- ✅ Pre-commit hooks pasan

### **Documentación**
- ✅ VISION.md actualizado
- ✅ Arquitectura documentada
- ✅ Guía de cómo agregar nuevos conectores

---

## 🚀 **Futuro (Post v1.8)**

### **v1.9 - Binance Connector**
- Implementar `connectors/binance/binance_connector.py`
- Soporte para Binance Futures Testnet
- Validación multi-exchange

### **v2.0 - Hyperliquid Connector**
- Implementar `connectors/hyperliquid/hyperliquid_connector.py`
- Soporte para Hyperliquid (sin testnet)
- Multi-asset foundation

### **v2.1 - Multi-Timeframe**
- Soporte para múltiples timeframes simultáneos
- Decisiones más robustas

---

## 📝 **Notas Importantes**

### **Preservar Código Funcional**
- `table_ccxt_pro_legacy.py` contiene:
  - URLs correctas de Kraken testnet/mainnet
  - Lógica de WebSocket funcional
  - Manejo de errores probado
  - **NO ELIMINAR** hasta que nueva implementación esté 100% validada

### **Extraer, No Reescribir**
- Copiar código funcional de legacy
- No reinventar la rueda
- Mantener lo que funciona

### **Testing Continuo**
- Test después de cada fase
- Validar con Kraken testnet
- No avanzar si algo está roto

---

## ✅ **Checklist de Validación**

Antes de considerar v1.8 completa:

- [ ] Pre-commit hooks pasan
- [ ] Tests unitarios pasan
- [ ] Tests de integración pasan
- [ ] Kraken testnet funciona
- [ ] Balance real se obtiene correctamente
- [ ] Órdenes se ejecutan correctamente
- [ ] TP/SL funcionan
- [ ] Logging es claro
- [ ] Documentación actualizada
- [ ] `table_ccxt_pro_legacy.py` puede ser eliminado (o archivado)

---

**Última actualización**: 2025-11-03
**Autor**: Pedro + Cascade
**Estado**: 🚧 En Progreso
