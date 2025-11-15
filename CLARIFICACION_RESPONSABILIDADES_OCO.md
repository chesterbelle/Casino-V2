# 🎯 Clarificación de Responsabilidades OCO

## PROBLEMA CRÍTICO IDENTIFICADO

### La Verdad sobre Binance Futures + OCO

**Binance Futures NO soporta OCO nativo.**

- ❌ No existe un parámetro `oco=true` en la API
- ❌ El parámetro `timeInForce: "GTE_GTC"` NO proporciona OCO
- ❌ GTE_GTC solo cancela órdenes al cerrar la posición manualmente
- ✅ Lo que SÍ funciona: Crear 3 órdenes separadas (main, TP, SL)

### Expectativa Falsa Actual

El código sugiere que `create_order_with_tpsl()` proporciona OCO, pero:

```python
# ❌ FALSO: Esto NO es OCO
"timeInForce": TIME_IN_FORCE_GTE_GTC,  # Comentario: "Habilita OCO"
```

GTE_GTC solo significa: "Si cierro la posición manualmente, cancela esta orden"

**No significa**: "Si TP se ejecuta, cancela SL automáticamente"

---

## ARQUITECTURA CORRECTA (Sin Refactorización)

### 1️⃣ BinanceConnector - Responsabilidades Claras

**QUÉ HACE:**
- ✅ Crea orden principal (market/limit)
- ✅ Crea orden TP (TAKE_PROFIT_MARKET)
- ✅ Crea orden SL (STOP_MARKET)
- ✅ Retorna IDs de todas las órdenes
- ✅ Falla rápido con errores claros

**QUÉ NO HACE:**
- ❌ NO maneja relaciones entre órdenes
- ❌ NO asume OCO automático
- ❌ NO monitorea ejecuciones
- ❌ NO cancela órdenes hermanas

**Código Actual (CORRECTO):**
```python
async def create_order_with_tpsl(...) -> Dict:
    """
    Create an order with Take Profit and Stop Loss on Binance.

    **IMPORTANTE**: Binance NO soporta TP/SL en la misma orden como Bybit.
    Necesita crear 3 órdenes separadas:
    1. Orden principal (market/limit)
    2. Take Profit order (TAKE_PROFIT_MARKET)
    3. Stop Loss order (STOP_MARKET)
    """
    # Crear 3 órdenes separadas
    main_order = await self.create_order(...)
    tp_order = await self.create_order(...)  # TAKE_PROFIT_MARKET
    sl_order = await self.create_order(...)  # STOP_MARKET

    # Retornar IDs para que capas superiores manejen OCO
    main_order["tp_order_id"] = tp_order_id
    main_order["sl_order_id"] = sl_order_id
    return main_order
```

**Responsabilidad**: "Crea 3 órdenes, retorna IDs, falla rápido"

---

### 2️⃣ CCXTAdapter - Interfaz Unificada

**QUÉ HACE:**
- ✅ Proporciona `execute_order()` que detecta TP/SL
- ✅ Calcula precios absolutos desde multiplicadores
- ✅ Delega a `connector.create_order_with_tpsl()`
- ✅ Retorna resultado del conector sin modificar

**QUÉ NO HACE:**
- ❌ NO asume OCO automático
- ❌ NO monitorea órdenes
- ❌ NO cancela órdenes

**Documentación Requerida:**
```python
async def execute_order(self, order: Dict) -> Dict:
    """
    Ejecuta una orden en el exchange.

    ⚠️ IMPORTANTE - OCO Manual Requerido:
    Si la orden incluye TP/SL, el adapter crea 3 órdenes separadas.
    Binance NO proporciona OCO automático.

    La responsabilidad de monitorear y cancelar órdenes hermanas
    recae en capas superiores (Croupier/PositionTracker).

    Retorna:
        {
            "id": "main_order_id",
            "tp_order_id": "tp_order_id",
            "sl_order_id": "sl_order_id",
            ...
        }
    """
```

**Responsabilidad**: "Traduce y delega, documenta OCO manual requerido"

---

### 3️⃣ Croupier - Orquestación

**QUÉ HACE:**
- ✅ Llama a `adapter.execute_order()`
- ✅ Obtiene IDs de TP/SL del resultado
- ✅ Pasa IDs a `position_tracker.register_tpsl_pair()`
- ✅ Llama a `position_tracker.monitor_oco_execution()` en el loop

**QUÉ NO HACE:**
- ❌ NO crea órdenes directamente
- ❌ NO monitorea órdenes (eso es PositionTracker)

**Código Actual (CORRECTO):**
```python
async def execute_order(self, order: dict) -> dict:
    # ... validación ...

    # Ejecutar orden con TP/SL
    result = await self._execute_on_exchange(order)
    trade_id = result.get("trade_id")

    # Registrar TP/SL para OCO manual
    tp_order_id = result.get("tp_order_id")
    sl_order_id = result.get("sl_order_id")
    if tp_order_id and sl_order_id:
        symbol = order.get("symbol", "")
        self.position_tracker.register_tpsl_pair(symbol, tp_order_id, sl_order_id)

    return result
```

**Responsabilidad**: "Orquesta ejecución y registra OCO manual"

---

### 4️⃣ PositionTracker - OCO Manual

**QUÉ HACE:**
- ✅ Monitorea órdenes TP/SL registradas
- ✅ Detecta ejecuciones (TP o SL)
- ✅ Cancela orden hermana cuando una se ejecuta
- ✅ Cierra posición con `confirm_close()`
- ✅ Sigue principio "Let it Crash"

**QUÉ NO HACE:**
- ❌ NO crea órdenes
- ❌ NO asume OCO automático

**Código Actual (CORRECTO):**
```python
async def monitor_oco_execution(self) -> None:
    """
    Monitor active TP/SL orders and execute manual OCO if needed.

    Flujo:
    1. Fetch estado de órdenes TP/SL
    2. Si TP ejecutado: Cancelar SL, cerrar posición
    3. Si SL ejecutado: Cancelar TP, cerrar posición
    """
    await self._check_manual_tpsl_execution()
```

**Responsabilidad**: "Monitorea y ejecuta OCO manual"

---

## FLUJO CORRECTO DE RESPONSABILIDADES

```
┌─────────────────────────────────────────────────────────┐
│ 🎯 CROUPIER (Orquestación)                              │
│ • Llama: adapter.execute_order()                        │
│ • Obtiene: tp_order_id, sl_order_id                     │
│ • Registra: position_tracker.register_tpsl_pair()       │
│ • Monitorea: position_tracker.monitor_oco_execution()   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 📊 CCXT ADAPTER (Traducción)                            │
│ • Detecta: TP/SL en orden                               │
│ • Calcula: Precios absolutos                            │
│ • Delega: connector.create_order_with_tpsl()            │
│ • Retorna: Resultado con IDs                            │
│ ⚠️ Documenta: "OCO manual requerido"                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 🏦 BINANCE CONNECTOR (Implementación)                   │
│ • Crea: 3 órdenes separadas (main, TP, SL)             │
│ • Retorna: IDs de todas las órdenes                     │
│ • Falla: Rápido y claro                                 │
│ ❌ NO asume OCO automático                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 🌐 BINANCE API (Ejecución)                              │
│ • Crea órdenes en el exchange                           │
│ • NO proporciona OCO automático                         │
└─────────────────────────────────────────────────────────┘
```

---

## CAMBIOS MÍNIMOS REQUERIDOS

### 1. Documentación en BinanceConnector

```python
async def create_order_with_tpsl(...) -> Dict:
    """
    Create an order with Take Profit and Stop Loss on Binance.

    **IMPORTANTE**: Binance NO soporta OCO nativo.

    Esta función crea 3 órdenes separadas:
    1. Orden principal (market/limit)
    2. Take Profit order (TAKE_PROFIT_MARKET)
    3. Stop Loss order (STOP_MARKET)

    ⚠️ OCO Manual Requerido:
    Las órdenes TP/SL se crean independientemente.
    El parámetro timeInForce: "GTE_GTC" NO proporciona OCO automático.

    Capas superiores (PositionTracker) son responsables de:
    - Monitorear ejecuciones de TP/SL
    - Cancelar orden hermana cuando una se ejecuta
    - Cerrar la posición

    Returns:
        {
            "id": "main_order_id",
            "tp_order_id": "tp_order_id",
            "sl_order_id": "sl_order_id",
            ...
        }
    """
```

### 2. Documentación en CCXTAdapter

```python
async def execute_order(self, order: Dict) -> Dict:
    """
    Ejecuta una orden en el exchange.

    ⚠️ IMPORTANTE - OCO Manual Requerido:
    Si la orden incluye TP/SL, se crean 3 órdenes separadas.

    Binance NO proporciona OCO automático.
    La responsabilidad de monitorear y cancelar órdenes hermanas
    recae en capas superiores (Croupier/PositionTracker).

    Flujo:
    1. Detecta TP/SL en la orden
    2. Calcula precios absolutos
    3. Delega a connector.create_order_with_tpsl()
    4. Retorna resultado con IDs

    Returns:
        {
            "id": "main_order_id",
            "tp_order_id": "tp_order_id",
            "sl_order_id": "sl_order_id",
            ...
        }
    """
```

### 3. Documentación en PositionTracker

```python
async def monitor_oco_execution(self) -> None:
    """
    Monitor active TP/SL orders and execute manual OCO if needed.

    Esta función es responsable de:
    1. Monitorear órdenes TP/SL registradas
    2. Detectar ejecuciones (TP o SL)
    3. Cancelar orden hermana cuando una se ejecuta
    4. Cerrar la posición

    Sigue el principio "Let it Crash":
    - Falla rápido si hay errores
    - Capas superiores (Croupier) manejan recuperación
    """
```

---

## VALIDACIÓN

### ✅ Responsabilidades Claras

| Capa | Crea Órdenes | Monitorea | Cancela | OCO Manual |
|------|--------------|-----------|---------|-----------|
| BinanceConnector | ✅ 3 órdenes | ❌ | ❌ | ❌ |
| CCXTAdapter | ❌ | ❌ | ❌ | ⚠️ Documenta |
| Croupier | ❌ | ❌ | ❌ | ✅ Orquesta |
| PositionTracker | ❌ | ✅ | ✅ | ✅ Ejecuta |

### ✅ "Let it Crash" Aplicado

- **BinanceConnector**: Falla rápido si no puede crear órdenes
- **CCXTAdapter**: Propaga excepciones del conector
- **Croupier**: Maneja recuperación (reintentos, logging)
- **PositionTracker**: Monitorea y ejecuta OCO manual

---

## CONCLUSIÓN

**No se requiere refactorización.**

Solo se requiere:
1. ✅ Documentación clara en cada capa
2. ✅ Remover expectativas falsas de OCO nativo
3. ✅ Validar que PositionTracker monitorea correctamente
4. ✅ Tests que validen el flujo completo

**La arquitectura actual es correcta, solo necesita clarificación.**
