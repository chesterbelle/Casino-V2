# 🔍 GUÍA DE DEBUG: EJECUCIÓN DE ÓRDENES OCO

## 📋 RESUMEN

Este test debuguea **exactamente** cómo el Croupier ejecuta una orden con TP/SL (Take Profit / Stop Loss) y valida que el OCO (One Cancels the Other) funcione correctamente.

---

## 🎯 OBJETIVO DEL TEST

Validar que:
1. ✅ La orden principal (MARKET) se ejecuta correctamente
2. ✅ Las órdenes TP/SL (LIMIT) se crean correctamente
3. ✅ Los IDs de TP/SL se registran en PositionTracker
4. ✅ El OCO manual monitorea las órdenes
5. ✅ Cuando TP o SL se ejecuta, la otra se cancela
6. ✅ La posición se cierra correctamente

---

## 🚀 CÓMO EJECUTAR

### Opción 1: Script bash (recomendado)
```bash
bash run_oco_debug_test.sh
```

### Opción 2: Python directo
```bash
python tests/test_oco_execution_debug.py
```

### Opción 3: Con logging detallado
```bash
PYTHONUNBUFFERED=1 python tests/test_oco_execution_debug.py 2>&1 | tee logs/oco_debug.log
```

---

## 📊 PASOS DEL TEST

### PASO 1: Conectar al exchange
```
📌 Conecta a Binance Testnet
✅ Valida que la conexión funciona
```

**Qué buscar si falla:**
- Error de autenticación → Revisar API keys en `.env`
- Error de conexión → Revisar URL del testnet
- Timeout → Revisar conexión a internet

---

### PASO 2: Obtener balance real
```
📌 Obtiene balance USDT del exchange
✅ Valida que hay fondos disponibles
```

**Qué buscar si falla:**
- Balance = 0 → Agregar fondos al testnet
- Error de fetch_balance → Revisar permisos de API key

---

### PASO 3: Crear Adapter y Croupier
```
📌 Crea CCXTAdapter (traductor agnóstico)
📌 Crea Croupier (dueño del estado)
✅ Valida que ambos se inicializan correctamente
```

**Qué buscar si falla:**
- Error de inicialización → Revisar imports
- Error de configuración → Revisar config/exchange.py

---

### PASO 4: Obtener precio actual
```
📌 Obtiene precio del mercado
✅ Valida que el ticker funciona
```

**Qué buscar si falla:**
- Precio = 0 → Revisar símbolo (LTC/USD:USD)
- Error de fetch_ticker → Revisar conexión WebSocket

---

### PASO 5: Ejecutar orden con Croupier
```
📌 Construye orden: LONG 0.01 (1% del equity)
📌 TP: +0.5% (1.005x)
📌 SL: -0.5% (0.995x)
📌 Ejecuta con Croupier.execute_order()

FLUJO INTERNO:
1. Croupier._validate_order() → Valida campos
2. Croupier._has_open_position() → Verifica posiciones
3. Croupier._execute_on_exchange() → Ejecuta orden principal
4. Croupier._setup_oco_orders() → Crea TP/SL
5. PositionTracker.open_position() → Registra posición

✅ Valida que la orden se ejecuta correctamente
```

**Qué buscar si falla:**
- Status != "open/opened/closed" → Revisar error de Binance
- Error en _execute_on_exchange → Revisar BinanceConnector
- Error en _setup_oco_orders → Revisar creación de TP/SL

---

### PASO 6: Verificar posición abierta
```
📌 Busca posición en PositionTracker
✅ Valida que se registró correctamente

INFORMACIÓN ESPERADA:
- trade_id: ID único de la posición
- symbol: LTC/USD:USD
- side: LONG
- entry_price: Precio de entrada
- tp_level: Precio de TP
- sl_level: Precio de SL
- main_order_id: ID de orden principal
- tp_order_id: ID de orden TP
- sl_order_id: ID de orden SL
```

**Qué buscar si falla:**
- No hay posiciones → Revisar PASO 5
- tp_order_id = None → TP no se creó, revisar _setup_oco_orders
- sl_order_id = None → SL no se creó, revisar _setup_oco_orders

---

### PASO 7: Verificar órdenes TP/SL en el exchange
```
📌 Obtiene estado de TP order desde Binance
📌 Obtiene estado de SL order desde Binance
✅ Valida que ambas órdenes existen

INFORMACIÓN ESPERADA:
- Status: "open" (pendiente de ejecución)
- Price: Precio TP/SL
- Amount: Cantidad de contratos
```

**Qué buscar si falla:**
- TP order no encontrada → Revisar tp_order_id
- SL order no encontrada → Revisar sl_order_id
- Status != "open" → Revisar si ya se ejecutó

---

### PASO 8: Monitorear OCO manual (60 segundos)
```
📌 Cada 5 segundos:
   1. Llama PositionTracker.monitor_oco_execution()
   2. Obtiene precio actual del mercado
   3. Verifica si TP o SL se ejecutó
   4. Si ejecutado: cancela la otra y cierra posición

ESPERADO:
- Si precio sube > TP → TP se ejecuta → SL se cancela → Posición cierra (WIN)
- Si precio baja < SL → SL se ejecuta → TP se cancela → Posición cierra (LOSS)
- Si precio no toca TP/SL → Timeout después de 60s (TIMEOUT)
```

**Qué buscar si falla:**
- Timeout (60s sin cierre) → OCO no está detectando ejecuciones
- Error en monitor_oco_execution → Revisar PositionTracker
- Error en fetch_order → Revisar conexión al exchange

---

### PASO 9: Verificar resultado final
```
📌 Obtiene estadísticas finales
✅ Valida que la posición se cerró

INFORMACIÓN ESPERADA:
- Posiciones abiertas: 0
- Total cerrados: 1
- Wins: 1 o 0 (depende si fue TP o SL)
- Losses: 0 o 1 (depende si fue TP o SL)
```

**Qué buscar si falla:**
- Posiciones abiertas > 0 → OCO no cerró la posición
- Total cerrados = 0 → Posición no se registró como cerrada

---

### PASO 10: Generar reporte de debug
```
📌 Genera archivo JSON con logs detallados
📁 Ubicación: logs/oco_debug_YYYYMMDD_HHMMSS.json

CONTENIDO:
- Timestamp de cada evento
- Paso ejecutado
- Mensaje descriptivo
- Datos asociados (órdenes, precios, IDs, etc.)
```

---

## 🔧 CÓMO DEBUGUEAR PROBLEMAS

### Problema: "Orden falló"
**Síntomas**: PASO 5 falla con error de Binance

**Causas posibles**:
1. Símbolo incorrecto → Revisar `self.symbol = "LTC/USD:USD"`
2. Balance insuficiente → Agregar fondos al testnet
3. Precio inválido → Revisar cálculo de TP/SL
4. Parámetros inválidos → Revisar BinanceConnector

**Solución**:
```python
# Revisar logs de BinanceConnector
# Buscar: "Error creating order"
# Verificar código de error de Binance
```

---

### Problema: "No se crearon órdenes TP/SL"
**Síntomas**: PASO 6 falla con `tp_order_id = None`

**Causas posibles**:
1. Error en _setup_oco_orders → Revisar Croupier
2. Error en CCXTAdapter → Revisar traducción de órdenes
3. Error en BinanceConnector → Revisar create_order

**Solución**:
```python
# Revisar logs de _setup_oco_orders
# Buscar: "Creating TP order" / "Creating SL order"
# Verificar que adapter.execute_order() retorna ID
```

---

### Problema: "OCO no cierra la posición (timeout)"
**Síntomas**: PASO 8 falla con timeout después de 60s

**Causas posibles**:
1. OCO manual no se ejecuta → Revisar monitor_oco_manual()
2. Precio no toca TP/SL → Esperar más tiempo o cambiar precios
3. Error en fetch_order → Revisar conexión al exchange
4. Error en cancelación → Revisar _cancel_sibling_order()

**Solución**:
```python
# Revisar logs de monitor_oco_execution
# Buscar: "Checking TP/SL execution"
# Verificar que fetch_order() retorna estado correcto
# Verificar que cancel_order() funciona
```

---

### Problema: "Error en fetch_order"
**Síntomas**: PASO 7 falla con error al obtener órdenes

**Causas posibles**:
1. Order ID inválido → Revisar que se registró correctamente
2. Símbolo incorrecto → Revisar normalización de símbolos
3. Conexión perdida → Revisar conexión al exchange

**Solución**:
```python
# Revisar logs de fetch_order
# Buscar: "Fetching order {order_id}"
# Verificar que order_id no es None
# Verificar que símbolo es correcto
```

---

## 📊 INTERPRETACIÓN DE RESULTADOS

### Resultado EXITOSO
```
✅ TEST COMPLETADO - OCO funcionando correctamente

Todos los pasos: PASS
- connect: PASS
- get_balance: PASS
- create_adapter_croupier: PASS
- get_current_price: PASS
- execute_order: PASS
- verify_open_position: PASS
- verify_tpsl_orders: PASS
- monitor_oco: PASS
- verify_final_result: PASS
```

**Significa**: OCO funciona correctamente, el bot puede operar en producción

---

### Resultado PARCIAL (Timeout)
```
⏱️ Timeout: OCO no se cerró en 60 segundos

Pasos exitosos: 1-7
Paso fallido: 8 (monitor_oco: TIMEOUT)

Significa: OCO se está monitoreando pero el precio no toca TP/SL
Solución: Esperar más tiempo o cambiar precios de TP/SL
```

---

### Resultado FALLIDO
```
❌ TEST FALLIDO - Revisar debug log

Pasos exitosos: 1-5
Paso fallido: 6 (verify_open_position: FAIL)

Significa: Error en creación de TP/SL
Solución: Revisar logs detallados en oco_debug_*.json
```

---

## 📁 ARCHIVOS GENERADOS

### Debug Log
```
logs/oco_debug_YYYYMMDD_HHMMSS.json

Contiene:
- Timestamp de cada evento
- Paso ejecutado
- Mensaje descriptivo
- Datos asociados (órdenes, precios, IDs, etc.)

Usar para análisis detallado de qué falló
```

---

## 🎯 PRÓXIMOS PASOS

### Si el test PASA ✅
1. Ejecutar Ronda 1 con el bot real
2. Validar que OCO funciona en producción
3. Monitorear logs para detectar problemas

### Si el test FALLA ❌
1. Revisar debug log en `logs/oco_debug_*.json`
2. Identificar en qué paso falla
3. Revisar código del paso fallido
4. Hacer fix y re-ejecutar test

---

## 🔗 REFERENCIAS

- **Croupier**: `croupier/croupier.py`
- **PositionTracker**: `core/portfolio/position_tracker.py`
- **BinanceConnector**: `exchanges/connectors/binance/binance_connector.py`
- **CCXTAdapter**: `exchanges/adapters/ccxt_adapter.py`

---

**Fin de la Guía de Debug**
