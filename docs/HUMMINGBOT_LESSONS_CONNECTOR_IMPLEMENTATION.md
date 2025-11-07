# 🎓 Lecciones de Hummingbot: Implementación de Conectores

## 📚 Fuente
- **Repositorio:** https://github.com/hummingbot/hummingbot
- **Conector analizado:** Kraken Exchange
- **Arquitectura:** https://hummingbot.org/developers/architecture/

---

## 🏗️ Arquitectura de Hummingbot

### 1. Clock-Driven Architecture

```python
# Hummingbot usa un "Clock" central que coordina TODO
Clock (tick cada 1 segundo)
    ↓
TimeIterator (base class para connectors y strategies)
    ↓ c_tick() llamado en orden
Connector.c_tick() → actualiza datos
    ↓
Strategy.c_tick() → toma decisiones
```

**Lección:** El orden importa. Connector SIEMPRE se actualiza ANTES que Strategy.

---

### 2. Order Tracking (Crítico)

```python
# Hummingbot TRACKEA órdenes activamente
class BinanceExchange:
    def create_order(self):
        # 1. START tracking ANTES de enviar al exchange
        self.c_start_tracking_order(order)

        # 2. Enviar al exchange
        result = await self.query_api(...)

        # 3. Si falla, la orden YA está trackeada
        # Esto evita perder órdenes si el API timeout pero la orden se colocó
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
async def create_order(...):
    order = await connector.create_order(...)  # Si falla aquí, perdemos la orden
    return order

# DEBERÍA SER ✅
async def create_order(...):
    # 1. Generar order_id ANTES
    order_id = self._generate_order_id()

    # 2. START tracking
    self._track_order(order_id, params)

    # 3. Enviar al exchange
    try:
        result = await connector.create_order(...)
        self._update_tracked_order(order_id, result)
    except Exception:
        # Orden sigue trackeada, verificar estado después
        pass
```

---

### 3. Graceful Degradation

**Principio:** El bot debe seguir funcionando aunque el exchange tenga problemas.

```python
# Hummingbot: Si fetch_balance() falla
async def _update_balances(self):
    try:
        balances = await self._api_request("Balance")
        self._account_balances = balances
    except Exception as e:
        # NO crashea, usa último balance conocido
        self.logger().warning(f"Failed to fetch balance: {e}")
        # self._account_balances sigue con valor anterior
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
balance = await connector.fetch_balance()  # Si falla → crash

# DEBERÍA SER ✅
try:
    balance = await connector.fetch_balance()
    self._last_known_balance = balance
    self._last_balance_update = time.time()
except Exception as e:
    logger.warning(f"Balance fetch failed, using cached: {e}")
    if time.time() - self._last_balance_update > 60:
        raise CriticalError("Balance too stale")
    balance = self._last_known_balance
```

---

### 4. Low Latency: WebSocket First

```python
# Hummingbot usa WebSocket para datos en tiempo real
class BinanceAPIOrderBookDataSource:
    async def listen_for_order_book_diffs(self):
        # WebSocket stream para order book updates
        async with websocket.connect(url) as ws:
            async for msg in ws:
                self._process_order_book_diff(msg)

    async def listen_for_trades(self):
        # WebSocket stream para trades
        async with websocket.connect(url) as ws:
            async for msg in ws:
                self._process_trade(msg)
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
# Polling cada 5 segundos para candles
await asyncio.sleep(5)
candles = await connector.fetch_ohlcv(...)

# DEBERÍA SER ✅
# WebSocket para trades en tiempo real
async def listen_trades(self):
    async with websocket.connect(kraken_ws_url) as ws:
        async for trade in ws:
            self._update_current_candle(trade)
```

---

### 5. Retry Logic con Exponential Backoff

```python
# Hummingbot: Retry inteligente
REQUEST_ATTEMPTS = 5

async def _api_request_with_retry(self, path_url, data=None):
    for retry_attempt in range(self.REQUEST_ATTEMPTS):
        try:
            response = await self._api_request(path_url, data)
            return response
        except IOError as e:
            if self.is_cloudflare_exception(e):
                # Exponential backoff
                retry_interval = 2  # base
                await asyncio.sleep(retry_interval ** retry_attempt)
                # 2^0=1s, 2^1=2s, 2^2=4s, 2^3=8s, 2^4=16s
                continue
            else:
                raise e
    raise IOError(f"Failed after {self.REQUEST_ATTEMPTS} attempts")
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
# ResilientConnector tiene retry, pero no exponential backoff
# Y no distingue tipos de errores

# DEBERÍA SER ✅
async def _execute_with_retry(self, func, *args, **kwargs):
    for attempt in range(self.max_retries):
        try:
            return await func(*args, **kwargs)
        except (NetworkError, TimeoutError) as e:
            # Retriable
            backoff = 2 ** attempt
            logger.warning(f"Retry {attempt+1}/{self.max_retries} after {backoff}s")
            await asyncio.sleep(backoff)
        except (AuthError, InvalidSymbolError) as e:
            # No retriable
            raise
```

---

### 6. User Stream (WebSocket para eventos de usuario)

```python
# Hummingbot: WebSocket separado para eventos de usuario
class KrakenAPIUserStreamDataSource:
    async def listen_for_user_stream(self):
        # 1. Obtener token de autenticación
        auth_token = await self.get_auth_token()

        # 2. Conectar WebSocket con token
        async with websocket.connect(url, auth=auth_token) as ws:
            # 3. Suscribirse a eventos
            await ws.send({"event": "subscribe", "subscription": {"name": "ownTrades"}})
            await ws.send({"event": "subscribe", "subscription": {"name": "openOrders"}})

            # 4. Procesar eventos en tiempo real
            async for msg in ws:
                if msg["channel"] == "ownTrades":
                    self._process_trade_update(msg)
                elif msg["channel"] == "openOrders":
                    self._process_order_update(msg)
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
# No hay WebSocket para eventos de usuario
# Polling manual de trades/orders

# DEBERÍA SER ✅
# Implementar UserStreamDataSource para Kraken
```

---

### 7. Balance Update Strategy

```python
# Hummingbot: Balance se actualiza de 3 formas
class ExchangePyBase:
    async def _update_balances(self):
        # 1. REST API (fallback)
        balances = await self._api_request("Balance")
        self._account_balances = balances

    async def _user_stream_event_listener(self):
        # 2. WebSocket (tiempo real) - PREFERIDO
        async for event in self._iter_user_event_queue():
            if event["type"] == "balanceUpdate":
                self._account_balances[event["asset"]] = event["balance"]

    def _process_trade_message(self, trade):
        # 3. Calculado después de trade (inmediato)
        self._account_balances[base] -= trade["amount"]
        self._account_balances[quote] += trade["cost"]
```

**Problema en Casino V2:**
```python
# ACTUAL ❌
# Solo REST API polling
balance = await connector.fetch_balance()

# DEBERÍA SER ✅
# 1. WebSocket para balance updates (si disponible)
# 2. Actualización local después de cada trade
# 3. REST API como verificación periódica
```

---

## 🎯 Problemas Identificados en Casino V2

### 1. No hay Order Tracking
- ❌ Si `create_order()` falla, perdemos la orden
- ❌ No sabemos si la orden se colocó o no
- ✅ **Solución:** Implementar tracking ANTES de enviar

### 2. No hay Fallback para datos críticos
- ❌ Si `fetch_balance()` falla → crash
- ❌ No hay cache de último valor conocido
- ✅ **Solución:** Cache + fallback + staleness check

### 3. Polling en lugar de WebSocket
- ❌ Latencia de 5 segundos
- ❌ Rate limits innecesarios
- ✅ **Solución:** WebSocket para trades, orders, balance

### 4. No hay Retry Inteligente
- ❌ Retry sin exponential backoff
- ❌ No distingue errores retriables vs no-retriables
- ✅ **Solución:** Exponential backoff + clasificación de errores

### 5. Balance desincronizado
- ❌ `get_stats()` lee balance interno viejo
- ❌ No se sincroniza después de trades
- ✅ **Solución:** Ya arreglado en commit anterior

---

## 📋 Plan de Acción Priorizado

### Prioridad 1: Order Tracking ⭐⭐⭐
```python
# Implementar en ResilientConnector
class OrderTracker:
    def __init__(self):
        self._tracked_orders = {}

    def start_tracking(self, order_id, params):
        self._tracked_orders[order_id] = {
            "status": "pending",
            "params": params,
            "created_at": time.time(),
        }

    def update_order(self, order_id, exchange_data):
        if order_id in self._tracked_orders:
            self._tracked_orders[order_id].update(exchange_data)
```

### Prioridad 2: Balance Fallback ⭐⭐⭐
```python
# Implementar en CCXTAdapter
class BalanceCache:
    def __init__(self, ttl=30):
        self._balance = None
        self._last_update = 0
        self._ttl = ttl

    def get(self):
        if self._balance and time.time() - self._last_update < self._ttl:
            return self._balance
        return None

    def set(self, balance):
        self._balance = balance
        self._last_update = time.time()
```

### Prioridad 3: WebSocket para Trades ⭐⭐
```python
# Implementar en KrakenConnector
async def listen_for_trades(self, symbol):
    url = "wss://ws.kraken.com/"
    async with websocket.connect(url) as ws:
        await ws.send({
            "event": "subscribe",
            "pair": [symbol],
            "subscription": {"name": "trade"}
        })
        async for msg in ws:
            yield self._parse_trade(msg)
```

### Prioridad 4: Exponential Backoff ⭐
```python
# Mejorar en ResilientConnector
async def _retry_with_backoff(self, func, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return await func()
        except RetriableError as e:
            backoff = min(2 ** attempt, 30)  # max 30s
            await asyncio.sleep(backoff)
    raise MaxRetriesExceeded()
```

---

## 💡 Conclusión

**Hummingbot es production-grade porque:**
1. ✅ Trackea órdenes ANTES de enviarlas
2. ✅ Usa WebSocket para baja latencia
3. ✅ Tiene fallbacks para todo
4. ✅ Retry inteligente con backoff
5. ✅ Graceful degradation

**Casino V2 necesita:**
1. ⚠️ Order tracking
2. ⚠️ Balance caching + fallback
3. ⚠️ WebSocket implementation
4. ⚠️ Mejor retry logic

**Próximo paso:** Implementar Order Tracking primero, es lo más crítico.
