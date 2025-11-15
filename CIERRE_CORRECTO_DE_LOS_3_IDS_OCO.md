# Cierre Correcto de los 3 IDs de OCO

## 🎯 El Problema

Cuando se ejecuta TP o SL, necesitamos **cancelar los 3 IDs** para cerrar completamente la posición:

1. **main_order_id** - ID de la orden principal (MARKET/LIMIT)
2. **tp_order_id** - ID de la orden TP (TAKE_PROFIT_MARKET)
3. **sl_order_id** - ID de la orden SL (STOP_MARKET)

Esto es **crítico para multi-asset trading** porque si no cancelamos todos los IDs, pueden quedar órdenes huérfanas en el exchange.

## ✅ Solución Implementada

### Flujo de Cierre Correcto

```python
# PositionTracker._execute_tpsl_manually()

# Step 0: Obtener la posición abierta
open_position = self.get_position_by_symbol(symbol)
trade_id = open_position.trade_id

# Step 1: Cancelar la orden TP/SL que se ejecutó
await adapter.cancel_order(order_id, symbol)  # order_id es TP o SL

# Step 2: Crear orden de cierre (market order)
market_order = await adapter.create_order(...)

# Step 3: Cancelar la orden OPUESTA (OCO behavior)
opposite_id = order_info.get("opposite")  # Si ejecutó TP, cancela SL; si ejecutó SL, cancela TP
await adapter.cancel_order(opposite_id, symbol)

# Step 4b: Cancelar la orden PRINCIPAL (NUEVO - Critical!)
main_order_id = open_position.main_order_id
await adapter.cancel_order(main_order_id, symbol)

# Step 5: Confirmar cierre en PositionTracker
confirm_close(trade_id, exit_price, exit_reason, pnl)
```

## 📊 Visualización: Qué Sucede

### Antes (Incorrecto - Solo cancelaba 2 IDs)
```
Posición Abierta:
├── main_order_id: "850292300"    ← NO SE CANCELABA ❌
├── tp_order_id: "850292374"      ← Se cancelaba ✓
└── sl_order_id: "850292444"      ← Se cancelaba ✓

Cuando se ejecuta TP:
├── Cancelar TP: "850292374" ✓
├── Cancelar SL: "850292444" ✓
└── main_order_id: "850292300" sigue abierto ❌

Resultado: Orden huérfana en el exchange
```

### Después (Correcto - Cancela los 3 IDs)
```
Posición Abierta:
├── main_order_id: "850292300"    ← SE CANCELA ✓
├── tp_order_id: "850292374"      ← SE CANCELA ✓
└── sl_order_id: "850292444"      ← SE CANCELA ✓

Cuando se ejecuta TP:
├── Cancelar TP: "850292374" ✓
├── Cancelar SL: "850292444" ✓
├── Cancelar main: "850292300" ✓
└── Crear cierre: market order ✓

Resultado: Posición completamente cerrada ✓
```

## 🔄 Código Implementado

```python
async def _execute_tpsl_manually(
    self, symbol: str, order_id: str, order_info: dict, order: dict,
    current_price: float, trigger_price: float
) -> None:
    """Execute a TP/SL order manually by converting it to a market order."""

    # Step 0: Find the open position for this symbol
    open_position = None
    for pos in self.open_positions:
        if pos.symbol == symbol:
            open_position = pos
            break

    if not open_position:
        logger.error(f"❌ OCO Manual: No open position found for {symbol}")
        return

    trade_id = open_position.trade_id

    # Step 1: Cancel the original TP/SL order
    await self.adapter.cancel_order(order_id, symbol)

    # Step 2: Get position side and amount
    position_side = await self._get_position_side(symbol)
    close_side = "sell" if position_side == "long" else "buy"

    # Step 3: Create market order to close position
    market_order = await self.adapter.create_order(
        symbol, "market", close_side, amount, None, {"reduceOnly": True}
    )

    # Step 4: Cancel opposite order (OCO behavior)
    opposite_id = order_info.get("opposite")
    if opposite_id:
        await self.adapter.cancel_order(opposite_id, symbol)

    # Step 4b: Cancel main order (NUEVO - Critical for multi-asset)
    main_order_id = open_position.main_order_id
    if main_order_id and main_order_id != order_id:
        await self.adapter.cancel_order(main_order_id, symbol)
        logger.info(f"✅ OCO Manual: Cancelled main order {main_order_id[:8]}...")

    # Step 5: Confirm close in PositionTracker
    self.confirm_close(
        trade_id=trade_id,
        exit_price=current_price,
        exit_reason=order_type,  # "TP" or "SL"
        pnl=pnl,
        fee=0.0
    )
```

## 🎯 Por Qué es Importante para Multi-Asset

### Escenario: Trading 3 Assets Simultáneamente

```
Asset 1: BTC/USD
├── main_order_id: "BTC_001"
├── tp_order_id: "BTC_TP_001"
└── sl_order_id: "BTC_SL_001"

Asset 2: ETH/USD
├── main_order_id: "ETH_001"
├── tp_order_id: "ETH_TP_001"
└── sl_order_id: "ETH_SL_001"

Asset 3: LTC/USD
├── main_order_id: "LTC_001"
├── tp_order_id: "LTC_TP_001"
└── sl_order_id: "LTC_SL_001"

Si NO cancelamos main_order_id:
├── BTC: main_order_id "BTC_001" sigue abierto ❌
├── ETH: main_order_id "ETH_001" sigue abierto ❌
└── LTC: main_order_id "LTC_001" sigue abierto ❌

Resultado: 3 órdenes huérfanas en el exchange
```

## 🔐 Validación: Los 3 IDs se Cancelan

```python
# Cuando se ejecuta TP en LTC/USD:

logger.info("🎯 Executing TP manually: LTC/USD @ $96.45")
logger.debug("✅ OCO Manual: Cancelled original TP order 850292374...")
logger.info("✅ OCO Manual: Cancelled opposite order 850292444...")
logger.info("✅ OCO Manual: Cancelled main order 850292300...")  # ← NUEVO
logger.info("✅ OCO Manual: Position pos_0 closed | PnL: $0.14")
```

## 📋 Resumen: Los 3 IDs

| ID | Tipo | Cuándo se Cancela | Por Qué |
|-------|------|---|---|
| **main_order_id** | Orden de entrada | Cuando se ejecuta TP/SL | Evita órdenes huérfanas |
| **tp_order_id** | Orden de ganancia | Cuando se ejecuta SL | OCO behavior |
| **sl_order_id** | Orden de pérdida | Cuando se ejecuta TP | OCO behavior |

## ✅ Conclusión

Ahora se cancelan correctamente los **3 IDs** cuando se ejecuta TP/SL:

1. ✅ **main_order_id** - Cancelado (NUEVO)
2. ✅ **tp_order_id** - Cancelado
3. ✅ **sl_order_id** - Cancelado

Esto asegura que:
- ✅ No hay órdenes huérfanas
- ✅ Multi-asset trading funciona correctamente
- ✅ Posiciones se cierran completamente
- ✅ OCO behavior es correcto
