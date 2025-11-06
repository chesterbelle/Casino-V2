# 🔄 Guía de Migración: Croupier V2

## 📋 Resumen

El Croupier ha sido refactorizado para convertirse en un **tablero de control centralizado** que gestiona el portfolio completo. La migración es **100% backward compatible** - el código existente sigue funcionando sin cambios.

---

## 🎯 Dos Modos de Operación

### Modo V1 (Pass-through) - Backward Compatible

```python
# Sin initial_balance - funciona como antes
croupier = Croupier(exchange_adapter)

# El portfolio se gestiona en el exchange_adapter
# Croupier solo enruta órdenes
```

### Modo V2 (Portfolio Management) - Nuevo

```python
# Con initial_balance - activa gestión de portfolio
croupier = Croupier(exchange_adapter, initial_balance=10000.0)

# Croupier gestiona el portfolio internamente
# Consultas directas sin acceder al exchange
balance = croupier.get_balance()
equity = croupier.get_equity()
positions = croupier.get_open_positions()
```

---

## 🔄 Migración Gradual

### Paso 1: Sin Cambios (Actual)

Tu código existente funciona sin modificaciones:

```python
# Código existente - sigue funcionando
from croupier.croupier import Croupier

croupier = Croupier(table)  # Sin initial_balance
result = croupier.route_order(order)
```

### Paso 2: Opt-in a V2 (Cuando estés listo)

Agrega `initial_balance` para activar portfolio management:

```python
# Nuevo código - con portfolio management
from croupier.croupier import Croupier

croupier = Croupier(exchange_adapter, initial_balance=10000.0)

# Ahora puedes consultar directamente
print(f"Balance: ${croupier.get_balance():,.2f}")
print(f"Equity: ${croupier.get_equity():,.2f}")
print(f"Positions: {len(croupier.get_open_positions())}")

# Ejecutar órdenes como siempre
result = croupier.execute_order(order)
```

---

## 🆕 Nuevas Capacidades (V2)

### 1. Consultas de Portfolio

```python
# Balance disponible
balance = croupier.get_balance()

# Equity total (balance + posiciones)
equity = croupier.get_equity()

# Posiciones abiertas
positions = croupier.get_open_positions()

# Posición específica
position = croupier.get_position(trade_id)

# Estado completo
state = croupier.get_portfolio_state()
# {
#   "balance": 10000.0,
#   "equity": 10500.0,
#   "open_positions_count": 2,
#   "open_positions": [...]
# }
```

### 2. Validación Automática de Fondos

```python
# V2 valida fondos antes de ejecutar
result = croupier.execute_order(order)

if result["status"] == "rejected":
    print(f"Fondos insuficientes: {result['reason']}")
```

### 3. Actualización Automática de Portfolio

```python
# V2 actualiza el portfolio automáticamente
result = croupier.execute_order(order)

# El balance ya está actualizado
print(f"Nuevo balance: ${result['balance']:,.2f}")
```

---

## 📊 Comparación de APIs

### Consultar Balance

**Antes (V1):**
```python
# Acceso indirecto via table
balance = croupier.table.balance_manager.balance
```

**Ahora (V2):**
```python
# Acceso directo via croupier
balance = croupier.get_balance()
```

### Consultar Posiciones

**Antes (V1):**
```python
# Acceso indirecto via table
positions = croupier.table.position_tracker.get_open_positions()
```

**Ahora (V2):**
```python
# Acceso directo via croupier
positions = croupier.get_open_positions()
```

### Ejecutar Orden

**Antes y Ahora (Compatible):**
```python
# La API no cambia
result = croupier.route_order(order)
# o
result = croupier.execute_order(order)
```

---

## 🏗️ Arquitectura

### V1 (Pass-through)
```
Gemini → Croupier → Table/Exchange
                      ├── BalanceManager
                      └── PositionTracker
```

### V2 (Control Board)
```
Gemini → Croupier → Exchange
           ├── PortfolioManager
           │     ├── BalanceManager
           │     └── PositionTracker
           └── Exchange (delegate)
```

---

## ✅ Ventajas de Migrar a V2

1. **Centralización**
   - Un solo punto para consultar estado
   - No más navegación por objetos anidados

2. **Validación**
   - Fondos validados antes de ejecutar
   - Errores claros y manejables

3. **Automatización**
   - Portfolio actualizado automáticamente
   - PnL calculado automáticamente

4. **Testabilidad**
   - Mock del exchange trivial
   - Portfolio testeable aislado

5. **Escalabilidad**
   - Fácil agregar multi-asset
   - Fácil agregar risk management

---

## 🧪 Testing

### Test en Modo V1 (Backward Compatibility)

```python
def test_croupier_v1_mode():
    """Test que el modo V1 sigue funcionando."""
    exchange = MockExchange()
    croupier = Croupier(exchange)  # Sin initial_balance

    order = {"symbol": "BTC/USDT", "side": "LONG", ...}
    result = croupier.route_order(order)

    assert result["status"] in ["opened", "closed"]
```

### Test en Modo V2 (Portfolio Management)

```python
def test_croupier_v2_mode():
    """Test del nuevo modo con portfolio management."""
    exchange = MockExchange()
    croupier = Croupier(exchange, initial_balance=10000.0)

    # Consultas directas
    assert croupier.get_balance() == 10000.0
    assert croupier.get_equity() == 10000.0
    assert len(croupier.get_open_positions()) == 0

    # Ejecutar orden
    order = {"symbol": "BTC/USDT", "side": "LONG", "size": 100, ...}
    result = croupier.execute_order(order)

    # Portfolio actualizado
    assert result["balance"] < 10000.0  # Fondos reservados
```

---

## 🚀 Recomendaciones

### Para Código Nuevo
✅ Usa V2 con `initial_balance`
```python
croupier = Croupier(exchange, initial_balance=10000.0)
```

### Para Código Existente
✅ Déjalo como está (V1 mode)
```python
croupier = Croupier(exchange)  # Funciona sin cambios
```

### Para Migración Gradual
1. Identifica puntos donde consultas balance/posiciones
2. Migra a V2 en esos puntos
3. Disfruta de la API más limpia

---

## 📝 Checklist de Migración

- [ ] Código existente funciona sin cambios (V1 mode)
- [ ] Identificar código que consulta balance/posiciones
- [ ] Migrar gradualmente a V2 agregando `initial_balance`
- [ ] Actualizar consultas a usar `croupier.get_*()`
- [ ] Validar que tests pasan
- [ ] Disfrutar de código más limpio

---

## 🎯 Conclusión

La migración a Croupier V2 es **opcional y gradual**:
- ✅ Código existente funciona sin cambios
- ✅ Nuevas features disponibles cuando las necesites
- ✅ Migración a tu propio ritmo
- ✅ Sin breaking changes

**Sin prisa pero sin pausa** 🚀
