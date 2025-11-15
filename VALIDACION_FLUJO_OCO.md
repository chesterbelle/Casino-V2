# ✅ Validación del Flujo OCO Manual

## Checklist de Validación

### 1. BinanceConnector - Crea 3 órdenes separadas

```python
✅ create_order_with_tpsl():
   - Crea orden principal (market/limit)
   - Crea orden TP (TAKE_PROFIT_MARKET)
   - Crea orden SL (STOP_MARKET)
   - Retorna IDs: {"id": "...", "tp_order_id": "...", "sl_order_id": "..."}
   - Falla rápido si hay errores
   - NO asume OCO automático
```

**Validación:**
```bash
# Verificar que create_order_with_tpsl retorna tp_order_id y sl_order_id
grep -n "tp_order_id\|sl_order_id" exchanges/connectors/binance/binance_connector.py | grep "return\|main_order"
```

---

### 2. CCXTAdapter - Delega y documenta

```python
✅ execute_order():
   - Detecta TP/SL en la orden
   - Calcula precios absolutos
   - Delega a connector.create_order_with_tpsl()
   - Retorna resultado con IDs
   - Documenta: "OCO manual requerido"
```

**Validación:**
```bash
# Verificar que execute_order documenta OCO manual
grep -A 10 "def execute_order" exchanges/adapters/ccxt_adapter.py | grep -i "oco manual"
```

---

### 3. Croupier - Orquesta y registra

```python
✅ execute_order():
   - Llama adapter.execute_order()
   - Obtiene tp_order_id y sl_order_id
   - Llama position_tracker.register_tpsl_pair()
   - Llama position_tracker.monitor_oco_execution() en el loop
```

**Validación:**
```bash
# Verificar que Croupier registra TP/SL
grep -n "register_tpsl_pair\|monitor_oco_manual" croupier/croupier.py
```

---

### 4. PositionTracker - Monitorea y ejecuta OCO

```python
✅ register_tpsl_pair():
   - Registra TP/SL en _active_orders
   - Linkea órdenes hermanas

✅ monitor_oco_execution():
   - Monitorea órdenes TP/SL
   - Detecta ejecuciones
   - Cancela orden hermana
   - Cierra posición con confirm_close()
```

**Validación:**
```bash
# Verificar que PositionTracker monitorea OCO
grep -n "monitor_oco_execution\|_check_manual_tpsl_execution" core/portfolio/position_tracker.py
```

---

## Flujo Completo de Validación

### Escenario: Orden LONG con TP/SL

```
1. Usuario envía orden:
   {
       "side": "LONG",
       "size": 0.01,
       "take_profit": 1.05,
       "stop_loss": 0.95,
       "leverage": 10
   }

2. Croupier.execute_order():
   ✅ Valida orden
   ✅ Llama adapter.execute_order()

3. CCXTAdapter.execute_order():
   ✅ Detecta TP/SL
   ✅ Calcula precios absolutos
   ✅ Delega a connector.create_order_with_tpsl()

4. BinanceConnector.create_order_with_tpsl():
   ✅ Crea orden principal (LONG)
   ✅ Crea orden TP (SELL @ 1.05x)
   ✅ Crea orden SL (SELL @ 0.95x)
   ✅ Retorna:
      {
          "id": "main_order_id",
          "tp_order_id": "tp_order_id",
          "sl_order_id": "sl_order_id"
      }

5. Croupier.execute_order() (continúa):
   ✅ Obtiene tp_order_id y sl_order_id
   ✅ Llama position_tracker.register_tpsl_pair()
   ✅ Retorna resultado

6. PositionTracker.register_tpsl_pair():
   ✅ Registra en _active_orders:
      {
          "tp_order_id": {"type": "TP", "opposite": "sl_order_id"},
          "sl_order_id": {"type": "SL", "opposite": "tp_order_id"}
      }

7. TradingSession loop:
   ✅ Llama croupier.monitor_oco_manual()
   ✅ Que llama position_tracker.monitor_oco_execution()

8. PositionTracker.monitor_oco_execution():
   ✅ Monitorea órdenes TP/SL
   ✅ Si TP ejecutado:
      - Cancela SL
      - Cierra posición
      - Registra trade
   ✅ Si SL ejecutado:
      - Cancela TP
      - Cierra posición
      - Registra trade
```

---

## Validaciones Específicas

### ✅ Validación 1: TP/SL IDs Retornados

**Archivo**: `exchanges/connectors/binance/binance_connector.py` línea ~1120

```python
# ✅ CORRECTO: Retorna IDs
main_order["tp_order_id"] = tp_order_id
main_order["sl_order_id"] = sl_order_id
return main_order
```

**Test**:
```bash
grep -A 5 "main_order\[\"tp_order_id\"\]" exchanges/connectors/binance/binance_connector.py
```

---

### ✅ Validación 2: Croupier Registra TP/SL

**Archivo**: `croupier/croupier.py` línea ~150

```python
# ✅ CORRECTO: Registra TP/SL
tp_order_id = result.get("tp_order_id")
sl_order_id = result.get("sl_order_id")
if tp_order_id and sl_order_id:
    self.position_tracker.register_tpsl_pair(symbol, tp_order_id, sl_order_id)
```

**Test**:
```bash
grep -B 2 -A 2 "register_tpsl_pair" croupier/croupier.py
```

---

### ✅ Validación 3: PositionTracker Monitorea

**Archivo**: `core/portfolio/position_tracker.py` línea ~663

```python
# ✅ CORRECTO: Monitorea OCO
async def monitor_oco_execution(self) -> None:
    """Monitorea órdenes TP/SL y ejecuta OCO manual"""
    await self._check_manual_tpsl_execution()
```

**Test**:
```bash
grep -A 10 "def monitor_oco_execution" core/portfolio/position_tracker.py
```

---

### ✅ Validación 4: TradingSession Llama Monitor

**Archivo**: `core/trading/session.py` línea ~200

```python
# ✅ CORRECTO: Llama monitor en el loop
await self.data_source.croupier.monitor_oco_manual()
```

**Test**:
```bash
grep "monitor_oco_manual" core/trading/session.py
```

---

## Problemas Conocidos y Soluciones

### Problema 1: GTE_GTC NO proporciona OCO automático

**Síntoma**: TP se ejecuta pero SL no se cancela automáticamente

**Causa**: Binance NO soporta OCO nativo, GTE_GTC solo cancela al cerrar posición manualmente

**Solución**: PositionTracker monitorea y cancela manualmente ✅

---

### Problema 2: Órdenes huérfanas

**Síntoma**: SL queda abierta después de que TP se ejecuta

**Causa**: Si PositionTracker no monitorea correctamente

**Solución**: Verificar que `monitor_oco_execution()` se llama en el loop ✅

---

### Problema 3: Trades no se registran

**Síntoma**: Posiciones cierran pero `total_trades` = 0

**Causa**: `confirm_close()` no se llama en PositionTracker

**Solución**: Verificar que `_execute_tpsl_manually()` llama `confirm_close()` ✅

---

## Resumen

### ✅ Arquitectura Correcta

| Capa | Responsabilidad | Estado |
|------|-----------------|--------|
| BinanceConnector | Crea 3 órdenes | ✅ Correcto |
| CCXTAdapter | Delega y documenta | ✅ Correcto |
| Croupier | Orquesta y registra | ✅ Correcto |
| PositionTracker | Monitorea y ejecuta OCO | ✅ Correcto |

### ✅ "Let it Crash" Aplicado

| Nivel | Falla Rápido | Recupera | Estado |
|------|--------------|----------|--------|
| BinanceConnector | ✅ Sí | ❌ No | ✅ Correcto |
| CCXTAdapter | ✅ Propaga | ❌ No | ✅ Correcto |
| Croupier | ❌ No | ✅ Sí | ✅ Correcto |
| PositionTracker | ✅ Sí | ✅ Sí | ✅ Correcto |

### ✅ Conclusión

**La arquitectura es correcta y sigue el principio "Let it Crash".**

Solo se requiere:
1. ✅ Documentación clara (COMPLETADA)
2. ✅ Validación del flujo (COMPLETADA)
3. ⏳ Tests de integración (Ronda 1 en progreso)
