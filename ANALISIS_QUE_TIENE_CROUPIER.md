# 📊 Análisis: ¿Qué tiene Croupier cuando llama create_order_with_tpsl()?

## 🎯 FLUJO ACTUAL

```
Croupier.execute_order(order)
  ↓
  1. Validación: _validate_order(order)
  2. Verificación: _has_open_position()
  3. Validación fondos: can_open_position()
  4. Ejecución: _execute_on_exchange(order)
     ↓
     a. Cálculo: _calculate_amount_from_size(order) si es necesario
     b. Delegación: exchange_adapter.execute_order(order)
        ↓
        CCXTAdapter.execute_order(order)
          ├─ Detecta: has_tpsl = True
          ├─ Calcula: tp_price, sl_price
          └─ Llama: connector.create_order_with_tpsl(
               tp_price=tp_price,
               sl_price=sl_price,
               ...
             )
             ↓
             BinanceConnector.create_order_with_tpsl()
               ├─ Crea: main_order
               ├─ Crea: tp_order
               ├─ Crea: sl_order
               └─ Retorna: {id, tp_order_id, sl_order_id}
        ↓
        Retorna: result con tp_order_id y sl_order_id
     ↓
     Retorna: result
  5. Registro: position_tracker.open_position(
       main_order_id=result.get("id"),
       tp_order_id=result.get("tp_order_id"),
       sl_order_id=result.get("sl_order_id"),
     )
  6. Registro OCO: position_tracker.register_tpsl_pair(
       tp_order_id,
       sl_order_id
     )
```

---

## 📋 QUÉ TIENE CROUPIER EN CADA MOMENTO

### MOMENTO 1: Cuando entra execute_order()

```python
Tiene:
  - order: dict con {
      "trade_id": str,
      "symbol": str,
      "side": "LONG" | "SHORT",
      "size": float,
      "take_profit": float,      # ← MULTIPLICADOR (ej. 1.01)
      "stop_loss": float,        # ← MULTIPLICADOR (ej. 0.99)
      "timestamp": str,
      "ghost": bool
    }
  - self.exchange_adapter: CCXTAdapter
  - self.position_tracker: PositionTracker
  - self.balance_manager: BalanceManager
```

### MOMENTO 2: Después de _calculate_amount_from_size()

```python
Tiene:
  - order: dict ahora con {
      "trade_id": str,
      "symbol": str,
      "side": "LONG" | "SHORT",
      "size": float,
      "amount": float,           # ← CALCULADO (cantidad en base currency)
      "take_profit": float,      # ← MULTIPLICADOR
      "stop_loss": float,        # ← MULTIPLICADOR
      "timestamp": str,
      "ghost": bool
    }
  - self.exchange_adapter: CCXTAdapter
  - self.position_tracker: PositionTracker
  - self.balance_manager: BalanceManager
```

### MOMENTO 3: Después de exchange_adapter.execute_order()

```python
Tiene:
  - order: dict original
  - result: dict con {
      "id": "main_order_id",
      "tp_order_id": "tp_order_id",      # ← RETORNADO POR CONNECTOR
      "sl_order_id": "sl_order_id",      # ← RETORNADO POR CONNECTOR
      "symbol": str,
      "side": str,
      "amount": float,
      "price": float,
      "status": "open" | "closed",
      "timestamp": int,
      ...
    }
  - self.exchange_adapter: CCXTAdapter
  - self.position_tracker: PositionTracker
  - self.balance_manager: BalanceManager
```

---

## 🔄 PROPUESTA: OCO Monitor en Croupier

### IDEA PRINCIPAL

En lugar de que `CCXTAdapter` llame `create_order_with_tpsl()`,
**Croupier crea un "OCO Monitor" que maneja las 3 órdenes**.

### FLUJO PROPUESTO

```
Croupier.execute_order(order)
  ↓
  1. Validación: _validate_order(order)
  2. Verificación: _has_open_position()
  3. Validación fondos: can_open_position()
  4. Ejecución: _execute_on_exchange(order)
     ↓
     a. Cálculo: _calculate_amount_from_size(order)
     b. Delegación: exchange_adapter.execute_order(order)
        ↓
        CCXTAdapter.execute_order(order)
          └─ Llama: connector.create_order()
             ↓
             BinanceConnector.create_order()
               └─ Crea: main_order
               └─ Retorna: {id, price, ...}
        ↓
        Retorna: result con main_order_id
     ↓
     Retorna: result
  5. OCO Monitor: _setup_oco_orders(order, result)
     ↓
     a. Detecta: has_tpsl = True
     b. Calcula: tp_price, sl_price
     c. Crea TP: exchange_adapter.create_order(tp_order)
     d. Crea SL: exchange_adapter.create_order(sl_order)
     e. Retorna: {tp_order_id, sl_order_id}
  6. Registro: position_tracker.open_position(
       main_order_id=result.get("id"),
       tp_order_id=tp_order_id,
       sl_order_id=sl_order_id,
     )
  7. Registro OCO: position_tracker.register_tpsl_pair(
       tp_order_id,
       sl_order_id
     )
```

---

## 🎯 VENTAJAS DE OCO Monitor EN CROUPIER

### 1. **Responsabilidad Clara**
```
BinanceConnector: Solo crea órdenes individuales
CCXTAdapter: Solo traduce y delega
Croupier: Orquesta la creación de 3 órdenes (OCO Monitor)
PositionTracker: Monitorea y ejecuta OCO manual
```

### 2. **Croupier Tiene Todo Lo Necesario**

En el momento de crear TP/SL, Croupier tiene:

```python
# Información de la orden original
order = {
    "symbol": str,
    "side": "LONG" | "SHORT",
    "amount": float,
    "take_profit": float,      # ← MULTIPLICADOR
    "stop_loss": float,        # ← MULTIPLICADOR
}

# Información de la orden ejecutada
result = {
    "id": "main_order_id",
    "price": float,            # ← PRECIO DE ENTRADA
    "timestamp": int,
}

# Acceso a recursos
self.exchange_adapter: CCXTAdapter  # ← PARA CREAR TP/SL
self.position_tracker: PositionTracker  # ← PARA REGISTRAR
```

### 3. **Lógica Centralizada**

Toda la lógica de OCO está en un lugar:
- Cálculo de precios TP/SL
- Creación de órdenes TP/SL
- Registro en PositionTracker

### 4. **Fácil de Debuggear**

```python
# En Croupier, todo está junto:
async def execute_order(self, order):
    result = await self._execute_on_exchange(order)

    # OCO Monitor aquí
    tp_id, sl_id = await self._setup_oco_orders(order, result)

    # Registro aquí
    self.position_tracker.open_position(
        main_order_id=result["id"],
        tp_order_id=tp_id,
        sl_order_id=sl_id,
    )
```

---

## 📝 ESTRUCTURA DEL OCO MONITOR

### Método en Croupier

```python
async def _setup_oco_orders(self, order: dict, main_result: dict) -> tuple[str, str]:
    """
    Crea órdenes TP/SL después de la orden principal.

    Responsable de:
    1. Detectar si hay TP/SL en la orden
    2. Calcular precios absolutos
    3. Crear órdenes TP y SL
    4. Retornar IDs de las órdenes

    Args:
        order: Orden original con multiplicadores
        main_result: Resultado de la orden principal

    Returns:
        (tp_order_id, sl_order_id)
    """
    # Detectar TP/SL
    has_tpsl = "take_profit" in order or "stop_loss" in order
    if not has_tpsl:
        return None, None

    # Calcular precios
    entry_price = main_result.get("price", 0.0)
    tp_multiplier = order.get("take_profit", 1.0)
    sl_multiplier = order.get("stop_loss", 1.0)

    tp_price = entry_price * tp_multiplier
    sl_price = entry_price * sl_multiplier

    # Crear TP
    tp_order = {
        "symbol": order["symbol"],
        "side": "sell" if order["side"] == "LONG" else "buy",
        "amount": order["amount"],
        "price": tp_price,
        "type": "TAKE_PROFIT_MARKET",
        "params": {"stopPrice": tp_price, ...}
    }
    tp_result = await self.exchange_adapter.create_order(tp_order)
    tp_order_id = tp_result.get("id")

    # Crear SL
    sl_order = {
        "symbol": order["symbol"],
        "side": "sell" if order["side"] == "LONG" else "buy",
        "amount": order["amount"],
        "price": sl_price,
        "type": "STOP_MARKET",
        "params": {"stopPrice": sl_price, ...}
    }
    sl_result = await self.exchange_adapter.create_order(sl_order)
    sl_order_id = sl_result.get("id")

    return tp_order_id, sl_order_id
```

---

## ✅ CONCLUSIÓN

### Croupier SÍ tiene todo lo necesario

En el momento de crear TP/SL, Croupier tiene:
- ✅ Orden original con multiplicadores
- ✅ Resultado de orden principal con precio de entrada
- ✅ Acceso a exchange_adapter para crear órdenes
- ✅ Acceso a position_tracker para registrar

### OCO Monitor es el nombre perfecto

- ✅ Describe exactamente qué hace: monitorea OCO
- ✅ No hay conflicto con PositionTracker.monitor_oco_execution()
- ✅ Clarifica que es responsabilidad de Croupier

### Arquitectura Resultante

```
BinanceConnector: create_order() - Crea UNA orden
CCXTAdapter: execute_order() - Delega a connector
Croupier: _setup_oco_orders() - Crea 3 órdenes (OCO Monitor)
PositionTracker: monitor_oco_execution() - Monitorea y ejecuta OCO manual
```

**Cada capa hace exactamente lo que debe hacer.**
