# Arquitectura OCO Manual v2.0 - Agnóstica del Conector

## ✅ Respeto de la Arquitectura Modular

La refactorización OCO Manual respeta completamente la arquitectura agnóstica:

```
┌─────────────────────────────────────────────────────────────────┐
│ TradingSession (Capa Alta - Orquestación)                       │
│ ├── Llama: croupier.monitor_oco_manual()                        │
│ └── Llama: croupier.sync_and_process_fills()                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Croupier (Capa Media-Alta - Lógica de Negocio)                  │
│ ├── Registra TP/SL: position_tracker.register_tpsl_pair()       │
│ └── Monitorea: position_tracker.monitor_oco_manual()            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PositionTracker (Capa Media - Agnóstica)                        │
│ ├── Usa: adapter.fetch_ticker(symbol)                           │
│ ├── Usa: adapter.fetch_order(order_id, symbol)                  │
│ ├── Usa: adapter.fetch_positions([symbol])                      │
│ ├── Usa: adapter.cancel_order(order_id, symbol)                 │
│ └── Usa: adapter.create_order(symbol, type, side, amount, ...)  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ CCXTAdapter (Capa Media - Agnóstica)                            │
│ ├── Traduce: fetch_ticker() → connector.fetch_ticker()          │
│ ├── Traduce: fetch_order() → connector.fetch_order()            │
│ ├── Traduce: fetch_positions() → connector.fetch_positions()    │
│ ├── Traduce: cancel_order() → connector.cancel_order()          │
│ └── Traduce: create_order() → connector.create_order()          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ BinanceConnector (Capa Baja - Específica del Exchange)          │
│ ├── Implementa: fetch_ticker() - Binance REST API               │
│ ├── Implementa: fetch_order() - Binance REST API                │
│ ├── Implementa: fetch_positions() - Binance REST API            │
│ ├── Implementa: cancel_order() - Binance REST API               │
│ ├── Implementa: create_order() - Binance REST API               │
│ └── Implementa: create_order_with_tpsl() - Lógica Binance       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ CCXT Library (Capa Baja - Biblioteca)                           │
│ └── Comunica con Binance API                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Responsabilidades por Capa

### ✅ TradingSession (Capa Alta)
**Responsabilidad:** Orquestación del flujo de trading
- Llama a `croupier.monitor_oco_manual()` en cada iteración
- Llama a `croupier.sync_and_process_fills()` en cada iteración
- **NO conoce** detalles de OCO, TP/SL, o exchanges

### ✅ Croupier (Capa Media-Alta)
**Responsabilidad:** Lógica de negocio y estado del portfolio
- Registra pares TP/SL en PositionTracker después de abrir posición
- Llama a `position_tracker.monitor_oco_manual()` para monitoreo
- **NO implementa** lógica de OCO, solo orquesta
- **NO conoce** detalles específicos de Binance

### ✅ PositionTracker (Capa Media)
**Responsabilidad:** Monitoreo agnóstico de OCO Manual
- Chequea precios actuales vía `adapter.fetch_ticker()`
- Obtiene detalles de órdenes vía `adapter.fetch_order()`
- Obtiene posiciones vía `adapter.fetch_positions()`
- Cancela órdenes vía `adapter.cancel_order()`
- Crea órdenes de cierre vía `adapter.create_order()`
- **NO conoce** detalles específicos de Binance
- **NO tiene** lógica específica de ningún exchange

### ✅ CCXTAdapter (Capa Media)
**Responsabilidad:** Traducción agnóstica a conectores
- Traduce llamadas genéricas a llamadas del conector
- Proporciona interfaz uniforme para todos los exchanges
- **NO implementa** lógica de negocio
- **NO implementa** lógica específica de exchanges

### ✅ BinanceConnector (Capa Baja)
**Responsabilidad:** Implementación específica de Binance
- Implementa métodos genéricos: `fetch_ticker()`, `fetch_order()`, etc.
- Implementa `create_order_with_tpsl()` con lógica Binance-específica
- Maneja particularidades de Binance (GTE_GTC, TAKE_PROFIT_MARKET, etc.)
- **NO implementa** lógica de OCO manual (eso es responsabilidad de PositionTracker)
- **Falla rápido** si hay problemas (principio "Let it crash")

## 🔄 Flujo de Ejecución de OCO Manual

### 1. Apertura de Posición
```
Croupier.execute_order()
  ├── Llama: adapter.execute_order()
  │   └── Llama: connector.create_order_with_tpsl()
  │       ├── Crea orden principal
  │       ├── Crea orden TP (TAKE_PROFIT_MARKET)
  │       ├── Crea orden SL (STOP_MARKET)
  │       └── Retorna: {tp_order_id, sl_order_id}
  │
  └── Llama: position_tracker.register_tpsl_pair(symbol, tp_id, sl_id)
      └── Registra en _active_orders para monitoreo
```

### 2. Monitoreo de OCO Manual (cada iteración)
```
TradingSession.run()
  └── Llama: croupier.monitor_oco_manual()
      └── Llama: position_tracker.monitor_oco_execution()
          ├── Para cada símbolo en _active_orders:
          │   ├── Obtiene precio actual: adapter.fetch_ticker(symbol)
          │   ├── Obtiene detalles de orden: adapter.fetch_order(order_id, symbol)
          │   ├── Obtiene posición: adapter.fetch_positions([symbol])
          │   ├── Chequea si TP/SL debe ejecutarse
          │   └── Si sí:
          │       ├── Cancela orden original: adapter.cancel_order(order_id, symbol)
          │       ├── Crea orden de cierre: adapter.create_order(...)
          │       └── Cancela orden opuesta: adapter.cancel_order(opposite_id, symbol)
          │
          └── Limpia _active_orders después de ejecutar
```

### 3. Confirmación de Fills
```
TradingSession.run()
  └── Llama: croupier.sync_and_process_fills()
      └── Detecta fills de TP/SL y confirma cierres
```

## 🎯 Principios Arquitectónicos Respetados

### ✅ 1. "Let it Crash" (Erlang/Elixir)
- **Capas bajas (BinanceConnector):** Fallan rápido y claro
  - Si hay error en API de Binance, propagan excepción
  - No intentan recuperarse
  - Logging claro del error

- **Capas altas (Croupier, PositionTracker):** Deciden cómo recuperarse
  - Capturan excepciones del conector
  - Implementan reintentos si es necesario
  - Toman decisiones de negocio

### ✅ 2. Agnóstico del Conector
- PositionTracker **NO conoce** que está usando BinanceConnector
- PositionTracker **NO tiene** lógica específica de Binance
- PositionTracker funciona igual con KrakenConnector, BybitConnector, etc.
- Solo usa métodos genéricos del adapter

### ✅ 3. Responsabilidad Única
- **BinanceConnector:** Comunicación con Binance
- **CCXTAdapter:** Traducción agnóstica
- **PositionTracker:** Monitoreo de OCO Manual
- **Croupier:** Orquestación de lógica de negocio
- **TradingSession:** Orquestación del flujo

### ✅ 4. Separación de Capas
- Cada capa solo conoce la capa inmediatamente inferior
- No hay saltos de capas
- No hay acoplamiento entre capas no adyacentes

## 📊 Métodos del Adapter Usados por PositionTracker

| Método | Implementación | Responsabilidad |
|--------|----------------|-----------------|
| `fetch_ticker(symbol)` | CCXTAdapter → BinanceConnector | Obtener precio actual |
| `fetch_order(order_id, symbol)` | CCXTAdapter → BinanceConnector | Obtener detalles de orden |
| `fetch_positions([symbol])` | CCXTAdapter → BinanceConnector | Obtener posiciones abiertas |
| `cancel_order(order_id, symbol)` | CCXTAdapter → BinanceConnector | Cancelar orden |
| `create_order(symbol, type, side, amount, price, params)` | CCXTAdapter → BinanceConnector | Crear orden de cierre |

## ✅ Validación de Arquitectura

### Preguntas de Validación

1. **¿PositionTracker conoce que está usando BinanceConnector?**
   - ❌ NO - Solo usa métodos genéricos del adapter

2. **¿PositionTracker tiene lógica específica de Binance?**
   - ❌ NO - Todo es agnóstico

3. **¿BinanceConnector implementa OCO Manual?**
   - ❌ NO - Solo crea órdenes TP/SL, el monitoreo es responsabilidad de PositionTracker

4. **¿CCXTAdapter traduce correctamente?**
   - ✅ SÍ - Todos los métodos están implementados

5. **¿Se respeta "Let it crash"?**
   - ✅ SÍ - BinanceConnector falla rápido, capas altas recuperan

6. **¿Hay acoplamiento entre capas?**
   - ❌ NO - Cada capa solo conoce la inmediatamente inferior

## 🔧 Cómo Agregar un Nuevo Exchange

Para agregar soporte a un nuevo exchange (ej. Kraken):

1. **Crear KrakenConnector** con métodos genéricos:
   - `fetch_ticker(symbol)`
   - `fetch_order(order_id, symbol)`
   - `fetch_positions([symbol])`
   - `cancel_order(order_id, symbol)`
   - `create_order(symbol, type, side, amount, price, params)`
   - `create_order_with_tpsl(symbol, side, amount, tp_price, sl_price)`

2. **Implementar lógica Kraken-específica** en KrakenConnector
   - Manejo de órdenes Kraken
   - Parámetros específicos de Kraken
   - Normalización de datos de Kraken

3. **PositionTracker funciona automáticamente** sin cambios
   - Usa los métodos genéricos del adapter
   - No necesita cambios

4. **CCXTAdapter funciona automáticamente** sin cambios
   - Solo traduce a los nuevos métodos del conector

## 📝 Conclusión

La arquitectura OCO Manual v2.0 respeta completamente los principios de:
- ✅ Agnóstico del conector
- ✅ "Let it crash"
- ✅ Separación de responsabilidades
- ✅ Separación de capas
- ✅ Escalabilidad

Cada capa tiene una responsabilidad clara y no conoce detalles de capas inferiores.
