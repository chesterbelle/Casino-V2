# ¿Dónde se Guardan los 3 IDs de OCO?

## 📋 El Problema Identificado

Binance retorna 3 IDs al crear las órdenes:
1. **main_order_id** - ID de la orden principal (MARKET/LIMIT)
2. **tp_order_id** - ID de la orden TP (TAKE_PROFIT_MARKET)
3. **sl_order_id** - ID de la orden SL (STOP_MARKET)

Pero solo se estaban guardando 2 (TP y SL). **Faltaba guardar el main_order_id**.

## ✅ Solución Implementada

### 1. Agregar Campo a OpenPosition

```python
@dataclass
class OpenPosition:
    """Representa una posición abierta con TP/SL pendientes."""

    # ... otros campos ...

    main_order_id: Optional[str] = None  # ID de la orden principal (MARKET/LIMIT)
    tp_order_id: Optional[str] = None    # ID de la orden TP (TAKE_PROFIT_MARKET)
    sl_order_id: Optional[str] = None    # ID de la orden SL (STOP_MARKET)
```

### 2. Pasar main_order_id desde Croupier

```python
# Croupier.execute_order()

result = await self._execute_on_exchange(order)

# Guardar los 3 IDs en la posición
self.position_tracker.open_position(
    order=order,
    entry_price=result.get("price", 0.0),
    entry_timestamp=result.get("timestamp", ""),
    available_equity=self.get_equity(),
    main_order_id=result.get("id"),      # ← ID de la orden principal
    tp_order_id=result.get("tp_order_id"),
    sl_order_id=result.get("sl_order_id"),
)
```

### 3. Guardar en OpenPosition

```python
# PositionTracker.open_position()

position = OpenPosition(
    trade_id=trade_id,
    symbol=symbol,
    side=side,
    entry_price=entry_price,
    entry_timestamp=entry_timestamp,
    margin_used=margin_used,
    notional=notional,
    leverage=leverage,
    tp_level=tp_level,
    sl_level=sl_level,
    liquidation_level=liquidation_level,
    order=order.copy(),
    main_order_id=main_order_id,      # ← Guardado aquí
    tp_order_id=tp_order_id,          # ← Guardado aquí
    sl_order_id=sl_order_id,          # ← Guardado aquí
)
```

## 📊 Flujo Completo: Dónde se Guardan los 3 IDs

### Paso 1: Binance Retorna los 3 IDs

```python
# BinanceConnector.create_order_with_tpsl()

result = {
    "id": "850292300",           # ← main_order_id
    "tp_order_id": "850292374",  # ← tp_order_id
    "sl_order_id": "850292444",  # ← sl_order_id
    "symbol": "LTC/USD:USD",
    "side": "buy",
    "amount": 1.004,
    "price": 96.31,
    "status": "open",
    ...
}
```

### Paso 2: Croupier Recibe los 3 IDs

```python
# Croupier.execute_order()

result = await self._execute_on_exchange(order)
# result contiene los 3 IDs

# Guardar en PositionTracker
self.position_tracker.open_position(
    order=order,
    entry_price=result.get("price"),
    entry_timestamp=result.get("timestamp"),
    available_equity=self.get_equity(),
    main_order_id=result.get("id"),           # ← 850292300
    tp_order_id=result.get("tp_order_id"),    # ← 850292374
    sl_order_id=result.get("sl_order_id"),    # ← 850292444
)
```

### Paso 3: PositionTracker Guarda los 3 IDs

```python
# PositionTracker.open_position()

position = OpenPosition(
    trade_id="pos_0",
    symbol="LTC/USD:USD",
    side="LONG",
    entry_price=96.31,
    entry_timestamp="2025-11-14T15:06:14",
    margin_used=9.71,
    notional=97.12,
    leverage=10.0,
    tp_level=96.45,
    sl_level=95.50,
    liquidation_level=...,
    order={...},
    main_order_id="850292300",    # ← Guardado en OpenPosition
    tp_order_id="850292374",      # ← Guardado en OpenPosition
    sl_order_id="850292444",      # ← Guardado en OpenPosition
)

# Registrar en open_positions
self.open_positions.append(position)
```

### Paso 4: Registrar en _active_orders para Monitoreo

```python
# Croupier.execute_order()

# Registrar TP/SL pair para OCO manual monitoring
tp_order_id = result.get("tp_order_id")      # "850292374"
sl_order_id = result.get("sl_order_id")      # "850292444"
if tp_order_id and sl_order_id:
    symbol = order.get("symbol", "")         # "LTC/USD:USD"
    self.position_tracker.register_tpsl_pair(symbol, tp_order_id, sl_order_id)
```

```python
# PositionTracker.register_tpsl_pair()

self._active_orders = {
    "LTC/USD:USD": {
        "850292374": {
            "type": "TP",
            "opposite": "850292444"
        },
        "850292444": {
            "type": "SL",
            "opposite": "850292374"
        }
    }
}
```

## 📍 Resumen: Dónde se Guardan los 3 IDs

| ID | Ubicación 1 | Ubicación 2 | Ubicación 3 | Uso |
|-------|-------------|-------------|-------------|-----|
| **main_order_id** | `OpenPosition.main_order_id` | - | - | Referencia de la orden principal |
| **tp_order_id** | `OpenPosition.tp_order_id` | `_active_orders[symbol][tp_id]` | - | Monitoreo OCO + Confirmación |
| **sl_order_id** | `OpenPosition.sl_order_id` | `_active_orders[symbol][sl_id]` | - | Monitoreo OCO + Confirmación |

## 🔍 Visualización: Estructura de Datos

```
OpenPosition (En PositionTracker.open_positions)
├── trade_id: "pos_0"
├── symbol: "LTC/USD:USD"
├── side: "LONG"
├── entry_price: 96.31
├── entry_timestamp: "2025-11-14T15:06:14"
├── margin_used: 9.71
├── notional: 97.12
├── leverage: 10.0
├── tp_level: 96.45
├── sl_level: 95.50
├── liquidation_level: 95.20
├── order: {...}
├── main_order_id: "850292300"     ← ID de la orden principal
├── tp_order_id: "850292374"       ← ID de la orden TP
├── sl_order_id: "850292444"       ← ID de la orden SL
├── bars_held: 0
└── funding_accrued: 0.0

_active_orders (En PositionTracker)
└── "LTC/USD:USD": {
    ├── "850292374": {
    │   ├── type: "TP"
    │   └── opposite: "850292444"
    └── "850292444": {
        ├── type: "SL"
        └── opposite: "850292374"
    }
}
```

## 🎯 Casos de Uso: Cuándo se Usan los 3 IDs

### 1. main_order_id
**Uso:** Referencia de la orden que abrió la posición
```python
# Ejemplo: Para auditoría o debugging
position.main_order_id  # "850292300"
# "Esta posición fue abierta por la orden 850292300"
```

### 2. tp_order_id
**Uso:** Monitoreo y ejecución de TP
```python
# En _active_orders para monitoreo continuo
_active_orders["LTC/USD:USD"]["850292374"] = {
    "type": "TP",
    "opposite": "850292444"
}

# Cuando se ejecuta TP:
await adapter.cancel_order("850292374", "LTC/USD:USD")  # Cancelar TP
await adapter.create_order(...)  # Crear market order
await adapter.cancel_order("850292444", "LTC/USD:USD")  # Cancelar SL (opposite)
```

### 3. sl_order_id
**Uso:** Monitoreo y ejecución de SL
```python
# En _active_orders para monitoreo continuo
_active_orders["LTC/USD:USD"]["850292444"] = {
    "type": "SL",
    "opposite": "850292374"
}

# Cuando se ejecuta SL:
await adapter.cancel_order("850292444", "LTC/USD:USD")  # Cancelar SL
await adapter.create_order(...)  # Crear market order
await adapter.cancel_order("850292374", "LTC/USD:USD")  # Cancelar TP (opposite)
```

## ✅ Validación: Los 3 IDs Guardados

```python
# Después de abrir una posición:

position = position_tracker.open_positions[0]

print(f"Main Order ID: {position.main_order_id}")    # "850292300"
print(f"TP Order ID:   {position.tp_order_id}")      # "850292374"
print(f"SL Order ID:   {position.sl_order_id}")      # "850292444"

# En _active_orders:
print(f"Active Orders: {position_tracker._active_orders}")
# {
#   "LTC/USD:USD": {
#     "850292374": {"type": "TP", "opposite": "850292444"},
#     "850292444": {"type": "SL", "opposite": "850292374"}
#   }
# }
```

## 🔐 Recuperación: Si se Pierde la Información

### Escenario 1: Se Reinicia la Aplicación
```python
# _active_orders se pierde (está en RAM)
# Pero OpenPosition tiene los IDs guardados

position = position_tracker.open_positions[0]
tp_id = position.tp_order_id      # "850292374"
sl_id = position.sl_order_id      # "850292444"

# Reconstruir _active_orders
position_tracker.register_tpsl_pair(
    position.symbol,
    tp_id,
    sl_id
)
```

### Escenario 2: Se Ejecuta una Orden Antes de Registrar
```python
# TP se ejecutó en Binance antes de registrar en _active_orders

# sync_and_process_fills() detecta el fill
# Busca la orden en position_tracker.open_positions
position = position_tracker.get_position(trade_id)

# Encuentra el opposite_id
sl_id = position.sl_order_id  # "850292444"

# Cancela la orden SL
await adapter.cancel_order(sl_id, position.symbol)
```

## 📝 Conclusión

Ahora se guardan correctamente los **3 IDs de OCO**:

1. ✅ **main_order_id** - En `OpenPosition.main_order_id`
2. ✅ **tp_order_id** - En `OpenPosition.tp_order_id` + `_active_orders`
3. ✅ **sl_order_id** - En `OpenPosition.sl_order_id` + `_active_orders`

Esto asegura que:
- ✅ Se puede recuperar la información si se reinicia
- ✅ Se puede auditar qué orden abrió la posición
- ✅ Se puede monitorear y ejecutar OCO correctamente
- ✅ Se puede cancelar órdenes hermanas cuando sea necesario
