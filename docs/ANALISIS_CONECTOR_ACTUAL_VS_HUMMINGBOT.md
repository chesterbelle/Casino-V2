# 🔍 Análisis: Conector Actual vs Hummingbot

## 📊 Comparación Directa

### 1. fetch_balance() - Obtención de Balance

#### ❌ Casino V2 (Actual)
```python
# kraken_connector.py línea 251-298
async def fetch_balance(self) -> Dict[str, Any]:
    if not self._connected:
        raise RuntimeError("Not connected")

    try:
        balance = await self.exchange.fetch_balance()  # ← Llamada directa a CCXT

        # Normalización básica
        normalized = {
            "total": balance.get("total", {}),
            "free": balance.get("free", {}),
            "used": balance.get("used", {}),
        }

        # Marca como actualizado
        self._balance_updated = True
        self._last_balance_update = time.time()

        return normalized

    except Exception as e:
        # ¿Qué pasa aquí? ¿Re-raise? ¿Fallback?
        ...
```

**Problemas:**
1. ❌ No hay retry logic
2. ❌ No hay cache/fallback si falla
3. ❌ Depende 100% de CCXT (capa extra)
4. ❌ Si falla, probablemente crashea
5. ❌ No valida que los datos sean correctos

---

#### ✅ Hummingbot (Referencia)
```python
# Hummingbot usa múltiples fuentes
class ExchangePyBase:
    async def _update_balances(self):
        """Update from REST API (fallback)"""
        try:
            result = await self._api_request("Balance")
            self._account_balances = self._parse_balance(result)
        except Exception as e:
            # NO crashea, mantiene balance anterior
            self.logger().warning(f"Balance update failed: {e}")

    async def _user_stream_event_listener(self):
        """Update from WebSocket (preferido)"""
        async for event in self._iter_user_event_queue():
            if event["type"] == "balanceUpdate":
                self._account_balances[event["asset"]] = event["balance"]

    def _process_trade_message(self, trade):
        """Update calculado después de trade (inmediato)"""
        self._account_balances[base] -= trade["amount"]
        self._account_balances[quote] += trade["cost"]
```

**Ventajas:**
1. ✅ 3 fuentes de balance (REST, WebSocket, calculado)
2. ✅ Si una falla, usa otra
3. ✅ No crashea nunca
4. ✅ Balance siempre disponible
5. ✅ Actualización en tiempo real vía WebSocket

---

### 2. create_order() - Creación de Órdenes

#### ❌ Casino V2 (Actual)
```python
# Buscar en kraken_connector.py
async def create_order(...):
    # Probablemente algo así:
    order = await self.exchange.create_order(...)
    return order
```

**Problemas:**
1. ❌ No hay tracking ANTES de enviar
2. ❌ Si falla, perdemos la orden
3. ❌ No sabemos si se colocó o no
4. ❌ No hay retry inteligente

---

#### ✅ Hummingbot (Referencia)
```python
class KrakenExchange:
    async def _place_order(self, order: InFlightOrder):
        # 1. START TRACKING ANTES de enviar
        self._order_tracker.start_tracking_order(order)

        # 2. Enviar al exchange
        try:
            api_params = self._build_order_params(order)
            result = await self._api_request_with_retry(
                method="POST",
                path_url="/AddOrder",
                data=api_params,
                is_auth_required=True
            )

            # 3. Actualizar tracking con resultado
            exchange_order_id = result["txid"][0]
            order.update_exchange_order_id(exchange_order_id)

        except Exception as e:
            # Orden sigue trackeada
            # Verificar estado después
            self.logger().warning(f"Order placement uncertain: {e}")
            # NO re-raise, verificar estado en próximo tick
```

**Ventajas:**
1. ✅ Tracking ANTES de enviar
2. ✅ Si falla, orden sigue trackeada
3. ✅ Verificación de estado después
4. ✅ Retry con exponential backoff
5. ✅ No pierde órdenes

---

### 3. Retry Logic

#### ❌ Casino V2 (ResilientConnector)
```python
# resilient_connector.py
async def _execute_with_retry(self, func, *args, **kwargs):
    for attempt in range(self.max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay)  # ← Delay FIJO
            else:
                raise
```

**Problemas:**
1. ❌ Delay fijo (no exponential backoff)
2. ❌ No distingue errores retriables vs no-retriables
3. ❌ Retry para TODO (incluso errores de auth)

---

#### ✅ Hummingbot (Referencia)
```python
class KrakenExchange:
    REQUEST_ATTEMPTS = 5

    async def _api_request_with_retry(self, path_url, data=None):
        for retry_attempt in range(self.REQUEST_ATTEMPTS):
            try:
                response = await self._api_request(path_url, data)
                return response

            except IOError as e:
                if self.is_cloudflare_exception(e):
                    # Retriable: Exponential backoff
                    retry_interval = 2
                    backoff = retry_interval ** retry_attempt
                    # 1s, 2s, 4s, 8s, 16s
                    await asyncio.sleep(backoff)
                    continue
                else:
                    # No retriable: Re-raise inmediatamente
                    raise e

        raise IOError(f"Failed after {self.REQUEST_ATTEMPTS} attempts")
```

**Ventajas:**
1. ✅ Exponential backoff (1s → 16s)
2. ✅ Distingue errores retriables
3. ✅ No retry para errores de auth
4. ✅ Límite razonable de intentos

---

### 4. WebSocket vs Polling

#### ❌ Casino V2 (Actual)
```python
# testing.py
async def next_candle(self):
    while True:
        await asyncio.sleep(self.poll_interval)  # ← 5 segundos
        candles = await self.adapter.connector.fetch_ohlcv(...)
        # Polling cada 5 segundos
```

**Problemas:**
1. ❌ Latencia de 5 segundos
2. ❌ Consume rate limits innecesariamente
3. ❌ No es tiempo real
4. ❌ Puede perder trades entre polls

---

#### ✅ Hummingbot (Referencia)
```python
class KrakenAPIOrderBookDataSource:
    async def listen_for_trades(self):
        """WebSocket para trades en tiempo real"""
        url = "wss://ws.kraken.com/"
        async with websocket.connect(url) as ws:
            await ws.send({
                "event": "subscribe",
                "pair": [self.trading_pair],
                "subscription": {"name": "trade"}
            })

            async for msg in ws:
                trade = self._parse_trade(msg)
                yield trade  # ← Tiempo real, sin delay

class KrakenAPIUserStreamDataSource:
    async def listen_for_user_stream(self):
        """WebSocket para eventos de usuario"""
        auth_token = await self.get_auth_token()
        url = "wss://ws-auth.kraken.com/"

        async with websocket.connect(url) as ws:
            # Suscribirse a eventos de usuario
            await ws.send({
                "event": "subscribe",
                "subscription": {"name": "ownTrades", "token": auth_token}
            })
            await ws.send({
                "event": "subscribe",
                "subscription": {"name": "openOrders", "token": auth_token}
            })

            async for msg in ws:
                yield msg  # ← Eventos en tiempo real
```

**Ventajas:**
1. ✅ Latencia < 100ms
2. ✅ No consume rate limits
3. ✅ Tiempo real
4. ✅ No pierde eventos

---

## 🎯 Resumen de Gaps

| Característica | Casino V2 | Hummingbot | Gap |
|----------------|-----------|------------|-----|
| **Order Tracking** | ❌ No | ✅ Sí | CRÍTICO |
| **Balance Fallback** | ❌ No | ✅ Sí | CRÍTICO |
| **WebSocket** | ❌ No | ✅ Sí | ALTO |
| **Exponential Backoff** | ❌ No | ✅ Sí | MEDIO |
| **Error Classification** | ❌ No | ✅ Sí | MEDIO |
| **User Stream** | ❌ No | ✅ Sí | ALTO |
| **Multi-source Balance** | ❌ No | ✅ Sí | ALTO |
| **Graceful Degradation** | ❌ No | ✅ Sí | CRÍTICO |

---

## 📋 Plan de Implementación

### Fase 1: Fixes Críticos (1-2 días)

#### 1.1 Order Tracking
```python
# Crear OrderTracker en ResilientConnector
class OrderTracker:
    def __init__(self):
        self._in_flight_orders = {}

    def start_tracking(self, client_order_id, params):
        self._in_flight_orders[client_order_id] = {
            "status": "pending",
            "params": params,
            "created_at": time.time(),
            "exchange_order_id": None,
        }

    def update_order(self, client_order_id, exchange_order_id, status):
        if client_order_id in self._in_flight_orders:
            self._in_flight_orders[client_order_id].update({
                "exchange_order_id": exchange_order_id,
                "status": status,
                "updated_at": time.time(),
            })

    def get_order(self, client_order_id):
        return self._in_flight_orders.get(client_order_id)
```

#### 1.2 Balance Cache + Fallback
```python
# Mejorar CCXTAdapter
class CCXTAdapter:
    def __init__(self, ...):
        self._balance_cache = None
        self._balance_cache_time = 0
        self._balance_cache_ttl = 30  # 30 segundos

    async def get_balance_safe(self):
        """Get balance with fallback"""
        try:
            # Intento 1: Fetch fresco
            balance_data = await self.connector.fetch_balance()
            balance = self._validate_and_extract_balance(balance_data)

            # Actualizar cache
            self._balance_cache = balance
            self._balance_cache_time = time.time()

            return balance

        except Exception as e:
            logger.warning(f"Balance fetch failed: {e}")

            # Intento 2: Cache reciente
            if self._balance_cache and time.time() - self._balance_cache_time < self._balance_cache_ttl:
                logger.info("Using cached balance")
                return self._balance_cache

            # Intento 3: Balance interno (último conocido)
            if self.balance_manager.balance > 0:
                logger.warning("Using internal balance (stale)")
                return self.balance_manager.balance

            # Sin opciones
            raise CriticalDataError("Cannot obtain balance")
```

#### 1.3 Exponential Backoff
```python
# Mejorar ResilientConnector
async def _execute_with_retry(self, func, *args, **kwargs):
    for attempt in range(self.max_retries):
        try:
            return await func(*args, **kwargs)

        except (NetworkError, TimeoutError, RateLimitError) as e:
            # Retriable
            if attempt < self.max_retries - 1:
                backoff = min(2 ** attempt, 30)  # max 30s
                logger.warning(f"Retry {attempt+1}/{self.max_retries} after {backoff}s: {e}")
                await asyncio.sleep(backoff)
            else:
                raise

        except (AuthenticationError, InvalidSymbolError) as e:
            # No retriable
            logger.error(f"Non-retriable error: {e}")
            raise
```

---

### Fase 2: WebSocket (3-5 días)

#### 2.1 WebSocket para Trades
```python
# Agregar a KrakenConnector
async def listen_for_trades(self, symbol):
    """Stream de trades en tiempo real"""
    url = "wss://ws.kraken.com/"

    async with websocket.connect(url) as ws:
        await ws.send({
            "event": "subscribe",
            "pair": [symbol],
            "subscription": {"name": "trade"}
        })

        async for msg in ws:
            if msg.get("event") == "trade":
                yield self._parse_trade(msg)
```

#### 2.2 WebSocket para User Events
```python
# Agregar a KrakenConnector
async def listen_for_user_stream(self):
    """Stream de eventos de usuario (orders, trades, balance)"""
    # 1. Obtener token
    auth_token = await self._get_ws_auth_token()

    # 2. Conectar
    url = "wss://ws-auth.kraken.com/"
    async with websocket.connect(url) as ws:
        # 3. Suscribirse
        await ws.send({
            "event": "subscribe",
            "subscription": {"name": "ownTrades", "token": auth_token}
        })
        await ws.send({
            "event": "subscribe",
            "subscription": {"name": "openOrders", "token": auth_token}
        })

        # 4. Procesar eventos
        async for msg in ws:
            yield msg
```

---

## 🚀 Resultado Esperado

Después de implementar:

```python
# ANTES ❌
balance = await connector.fetch_balance()  # Falla → crash
order = await connector.create_order(...)  # Falla → orden perdida
await asyncio.sleep(5)  # Polling lento

# DESPUÉS ✅
balance = await adapter.get_balance_safe()  # Falla → usa cache/fallback
order_id = await connector.create_order_tracked(...)  # Falla → orden trackeada
async for trade in connector.listen_for_trades():  # Tiempo real
    process(trade)
```

---

**Próximo paso:** ¿Implementamos Order Tracking primero? Es lo más crítico.
