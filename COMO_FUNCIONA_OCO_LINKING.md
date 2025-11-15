# ¿Cómo se Linkean las 3 Órdenes OCO?

## 📋 El Problema

Binance crea 3 órdenes separadas:
1. **Orden Principal** (MARKET o LIMIT) - Abre la posición
2. **Orden TP** (TAKE_PROFIT_MARKET) - Cierra si gana
3. **Orden SL** (STOP_MARKET) - Cierra si pierde

Pero Binance NO las vincula automáticamente. Necesitamos nosotros hacerlo.

## ✅ La Solución: `_active_orders` Dictionary

PositionTracker mantiene un diccionario en memoria que linkea las órdenes:

```python
self._active_orders = {
    "LTC/USD:USD": {
        "850292374": {
            "type": "TP",
            "opposite": "850292444"  # ID de la orden SL
        },
        "850292444": {
            "type": "SL",
            "opposite": "850292374"  # ID de la orden TP
        }
    }
}
```

## 🔄 Flujo Paso a Paso

### Paso 1: Crear las 3 Órdenes (BinanceConnector)

```python
# BinanceConnector.create_order_with_tpsl()

# 1. Crear orden principal
main_order = await connector.create_order(...)
# Retorna: {"id": "850292300", ...}

# 2. Crear orden TP
tp_order = await connector.create_order(..., type="TAKE_PROFIT_MARKET", ...)
# Retorna: {"id": "850292374", ...}

# 3. Crear orden SL
sl_order = await connector.create_order(..., type="STOP_MARKET", ...)
# Retorna: {"id": "850292444", ...}

# Retornar los IDs al Croupier
return {
    "id": "850292300",
    "tp_order_id": "850292374",
    "sl_order_id": "850292444",
    ...
}
```

### Paso 2: Registrar el Linkeo (Croupier)

```python
# Croupier.execute_order()

result = await self._execute_on_exchange(order)

# Registrar TP/SL pair para OCO manual monitoring
tp_order_id = result.get("tp_order_id")      # "850292374"
sl_order_id = result.get("sl_order_id")      # "850292444"
if tp_order_id and sl_order_id:
    symbol = order.get("symbol", "")         # "LTC/USD:USD"
    self.position_tracker.register_tpsl_pair(symbol, tp_order_id, sl_order_id)
```

### Paso 3: Guardar en Memoria (PositionTracker)

```python
# PositionTracker.register_tpsl_pair()

def register_tpsl_pair(self, symbol: str, tp_order_id: str, sl_order_id: str) -> None:
    """Register TP/SL order pair for OCO monitoring."""

    # Crear entrada para el símbolo si no existe
    if symbol not in self._active_orders:
        self._active_orders[symbol] = {}

    # Linkear TP → SL
    self._active_orders[symbol][tp_order_id] = {
        "type": "TP",
        "opposite": sl_order_id  # ← Aquí está el linkeo
    }

    # Linkear SL → TP
    self._active_orders[symbol][sl_order_id] = {
        "type": "SL",
        "opposite": tp_order_id  # ← Aquí está el linkeo
    }

    logger.info(f"📝 Registered TP/SL pair for {symbol}: TP={tp_order_id}, SL={sl_order_id}")
```

**Estado en memoria después de registrar:**

```python
_active_orders = {
    "LTC/USD:USD": {
        "850292374": {"type": "TP", "opposite": "850292444"},
        "850292444": {"type": "SL", "opposite": "850292374"}
    }
}
```

### Paso 4: Monitorear y Ejecutar OCO (PositionTracker)

```python
# PositionTracker._check_manual_tpsl_execution()

for symbol, orders in list(self._active_orders.items()):
    # Para cada símbolo con órdenes activas

    for order_id, order_info in orders.items():
        # Para cada orden (TP o SL)

        # Obtener detalles de la orden
        order = await self.adapter.fetch_order(order_id, symbol)

        # Chequear si debe ejecutarse
        if should_execute:
            # Ejecutar la orden
            await self._execute_tpsl_manually(
                symbol, order_id, order_info, order, current_price, stop_price
            )
```

### Paso 5: Ejecutar OCO Manual

```python
# PositionTracker._execute_tpsl_manually()

async def _execute_tpsl_manually(self, symbol, order_id, order_info, ...):
    """Execute a TP/SL order manually by converting it to a market order."""

    # 1. Cancelar la orden original (TP o SL)
    await self.adapter.cancel_order(order_id, symbol)

    # 2. Crear orden de cierre (market order)
    market_order = await self.adapter.create_order(
        symbol, "market", close_side, amount, None, {"reduceOnly": True}
    )

    # 3. Cancelar la orden OPUESTA (OCO behavior)
    opposite_id = order_info.get("opposite")  # ← Aquí usamos el linkeo
    if opposite_id:
        await self.adapter.cancel_order(opposite_id, symbol)
        logger.info(f"✅ OCO: Cancelled opposite order {opposite_id}")

    # 4. Limpiar del tracking
    if symbol in self._active_orders:
        del self._active_orders[symbol]
```

## 📊 Ejemplo Completo: Ejecución de TP

```
ESTADO INICIAL:
_active_orders = {
    "LTC/USD:USD": {
        "850292374": {"type": "TP", "opposite": "850292444"},
        "850292444": {"type": "SL", "opposite": "850292374"}
    }
}

MONITOREO:
1. Precio actual: $96.50
2. TP trigger: $96.45 ← Precio cruzó el TP
3. Detectar: order_id="850292374" debe ejecutarse

EJECUCIÓN:
1. Cancelar TP: await adapter.cancel_order("850292374", "LTC/USD:USD")
2. Crear market order para cerrar posición
3. Obtener opposite_id: "850292444" (del diccionario)
4. Cancelar SL: await adapter.cancel_order("850292444", "LTC/USD:USD")
   ✅ OCO: Cancelled opposite order 850292444

ESTADO FINAL:
_active_orders = {}  # Limpiado
```

## 🔍 ¿Dónde se Guarda?

### En Memoria (Temporal)
```python
# PositionTracker._active_orders
# Vive en RAM mientras la sesión está activa
# Se pierde cuando se cierra la aplicación
```

### En la OpenPosition (Persistente)
```python
# PositionTracker.open_positions
# Cada OpenPosition tiene:
position.tp_order_id = "850292374"
position.sl_order_id = "850292444"

# Esto se usa para:
# 1. Confirmar cierres en sync_and_process_fills()
# 2. Cancelar órdenes hermanas en close_position()
```

### En Croupier (Referencia)
```python
# Croupier.position_tracker
# Tiene acceso a:
# - position_tracker._active_orders (monitoreo activo)
# - position_tracker.open_positions (estado de posiciones)
```

## 🎯 Diferencia: OCO Manual vs OCO Automático

### OCO Automático (Kraken, Bybit)
```
Kraken API:
POST /orders
{
    "symbol": "LTCUSD",
    "side": "buy",
    "amount": 1.0,
    "tp": 96.45,
    "sl": 95.50
}
→ Kraken linkea automáticamente
```

### OCO Manual (Binance Testnet)
```
Binance API:
1. POST /order (main)
2. POST /order (TP)
3. POST /order (SL)
→ Nosotros linkeamos en _active_orders
→ Nosotros monitoreamos
→ Nosotros ejecutamos OCO
```

## 📝 Resumen: 3 Formas de Linkear

| Ubicación | Tipo | Duración | Uso |
|-----------|------|----------|-----|
| `_active_orders` | En Memoria | Sesión activa | Monitoreo activo |
| `OpenPosition.tp_order_id` | En Memoria | Sesión activa | Confirmación de fills |
| `OpenPosition.sl_order_id` | En Memoria | Sesión activa | Cancelación de hermanas |

## 🔐 Seguridad del Linkeo

### ¿Qué pasa si se pierde el linkeo?

```python
# Escenario: Se reinicia la aplicación
# _active_orders se pierde (está en RAM)

# Pero no hay problema porque:
# 1. OpenPosition tiene los IDs guardados
# 2. En la siguiente sesión, se puede recuperar
# 3. Las órdenes en Binance siguen existiendo
```

### ¿Qué pasa si una orden se ejecuta antes de registrar?

```python
# Escenario: TP se ejecuta en Binance antes de registrar en _active_orders

# Solución:
# 1. sync_and_process_fills() detecta el fill
# 2. Busca la orden en position_tracker.open_positions
# 3. Encuentra el opposite_id en OpenPosition.sl_order_id
# 4. Cancela la orden SL
# 5. Confirma el cierre
```

## ✅ Conclusión

Las 3 órdenes OCO se linkean de 2 formas:

1. **`_active_orders` (Monitoreo Activo)**
   - Diccionario en memoria
   - Usado para monitoreo continuo
   - Se limpia después de ejecutar

2. **`OpenPosition` (Referencia Persistente)**
   - Guardado en la posición abierta
   - Usado para confirmación de fills
   - Usado para cancelación de hermanas

Esto asegura que:
- ✅ Se monitorean activamente
- ✅ Se ejecutan cuando es necesario
- ✅ Se cancela la orden opuesta (OCO behavior)
- ✅ Se recupera si hay errores
