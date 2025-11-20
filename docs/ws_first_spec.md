# Especificación: WebSocket-first Architecture (WS por defecto) — Casino-V2 2.0

Fecha: 2025-11-20

Resumen
- Objetivo: Reestructurar las comunicaciones del bot para usar WebSocket (`ccxt.pro`) como canal primario de verdad (ordenes, fills, posiciones, balance, tickers), y usar REST como fallback. Mejorar latencia, robustez y consistencia entre demo/live y backtest.
- Alcance inicial: `ConnectionManager`, `BinanceConnector`, `exchanges/adapters/*`, y `croupier`.

Principios de diseño
- Adapter-agnosticidad: Los adaptadores (`exchanges/adapters/*`) deben permanecer agnósticos respecto al transporte (WS vs REST). El adaptador solicita operaciones (create_order, fetch_order, fetch_ticker) y el conector/ConnectionManager decide cómo ejecutar y confirmar dichas operaciones. Esto facilita soportar múltiples conectores (Binance, Gemini, etc.) sin cambiar adaptadores.
- WS-first: Por defecto, intentar confirmar acciones críticas vía WS (`watch_orders`, `watch_my_trades`, `watch_positions`, `watch_balance`, `watch_ticker`). REST solo como fallback cuando WS no esté disponible o no responda en timeout configurado.
Confirmación de órdenes: El flujo por defecto ahora espera confirmación de fill (`avgPrice`/`filled`) vía WebSocket antes de crear TP/SL. El flag `wait_for_fill_confirmation` y el modo legacy han sido eliminados.
- Feature-flag y migración: Mantener una feature-flag `ws_first` global que permita activar/desactivar el comportamiento durante migración y pruebas.

Componentes y responsabilidades
- ConnectionManager (`exchanges/resilience/connection_manager.py`)
  - Único responsable de crear/gestionar `ws_exchange` (instancia `ccxt.pro` o wrapper Testnet).
  - Exponer API async: `ensure_ws_connected()`, `watch_orders(filter)`, `watch_my_trades(symbol)`, `watch_positions()`, `watch_balance()`, `fetch_via_rest(method, ...)`, `is_ws_primary()`.
  - Manejar autenticación previa (`authenticate`), espejo de `markets` desde REST para evitar concurrencia de ccxt.pro, reintentos con backoff, circuit-breaker y telemetría.

- Connectors (ej. `BinanceConnector`)
  - Delegar en `ConnectionManager` para emitir y confirmar órdenes.
  - Implementar `create_order(order, confirm_with_ws=False, ws_timeout_ms=2000)`: enviar orden y, si `confirm_with_ws`, esperar evento WS correlacionado (por `orderId` o `clientOrderId`) o fallback REST.
  - Publicar eventos locales hacia `ExchangeStateSync` y/o `Croupier` cuando llegue confirmación WS.

- Adapters (`exchanges/adapters/*`)
  - Mantener API existente (agnóstica): `execute_order(order)` y `get_current_price(symbol)`.
  - Añadir parámetros opcionales en la firma (p.e. `confirm_with_ws: bool = False`, `ws_timeout_ms: int | None = None`) sin romper compatibilidad positional.

- Croupier
  - El método `execute_order` ahora siempre espera confirmación de fill antes de crear OCO/TP/SL. No existe más el flag `wait_for_fill_confirmation`.

Flujo de orden propuesto (WS-first)
1. `Croupier.execute_order(order)`
2. Adapter delega a Connector: `create_order(order, confirm_with_ws=True)`
3. Connector envía create_order (REST o WS create). Registra timestamp `create_ts`.
4. ConnectionManager subscribe a `watch_orders`/`watch_my_trades` y espera evento correlacionado con `orderId` o `clientOrderId`.
   - Si llega evento con `filled`/`avgPrice` dentro de `ws_timeout_ms`: confirmar y devolver `entry_price=avgPrice`.
   - Si no llega en timeout: intentar `fetch_order` por REST; si sigue sin avgPrice, decidir fallback (crear OCO con precio límite conservador o abortar según política configurable).

Correlación y robustez
- Correlación por `clientOrderId`/`newClientOrderId` o `orderId`. Si CCXT/Exchange no retorna `clientOrderId`, usar un campo `user_tag` en `order.params` para permitir correlación desde el lado del cliente.
- Backoff y circuit-breaker: si WS falla N veces seguidas, marcar `ws_primary=False` por T minutos y cambiar a REST-first (incluir métricas para re-evaluación automática).

APIs y contratos (resumen)
- `ConnectionManager.ensure_ws_connected() -> None`
- `ConnectionManager.watch_orders(filter=None) -> AsyncIterator[list[Order]]` (o `await watch_orders(...)` que devuelve la lista de órdenes actuales y actualizaciones)
- `Connector.create_order(order, confirm_with_ws=False, ws_timeout_ms=2000) -> OrderResult`  (OrderResult contiene status, orderId, avgPrice opt.)
- `Adapter.execute_order(order, confirm_with_ws=False, ws_timeout_ms=None) -> OrderResult`

Configuración y feature flags
- `config/system.py`:
  - `WS_FIRST: bool = True`  # activar WS-first en la rama 2.0 por defecto
  - `WS_CONFIRM_TIMEOUT_MS: int = 2000`
  - `WS_RECONNECT_BACKOFF_SECONDS: int = 2`
  - `WS_CIRCUIT_BREAK_THRESHOLD: int = 5`

Telemetría y alertas
- Métricas a exponer:
  - `order_create_to_ws_confirm_ms`
  - `ws_fail_rate`
  - `rest_fallback_rate`
  - `ws_reconnect_count`
- Logs estructurados (JSON) con campos: `order_id`, `clientOrderId`, `symbol`, `create_ts`, `ws_confirm_ts`, `avgPrice`, `filled_qty`, `fallback_reason`.

Pruebas y validación
- Unit tests: mockear `ConnectionManager.watch_orders` y simular latencias/paquetes perdidos; validar que `create_order(..., confirm_with_ws=True)` devuelve avgPrice cuando WS entrega la notificación.
- Integration test: demo en testnet con `WS_FIRST=true` para medir latencia real entre crear orden y confirmación WS.
- Regression tests: asegurar que backtest y `SimulatedConnector` no rompan durante la migración (nota: per requirements actuales, el SimulatedConnector se deja fuera de emulación de 'immediately trigger').

Plan de despliegue incremental
1. Merge branch `2.0` con spec y feature-flag (esta rama).
2. Refactor `ConnectionManager` y exponer API (interno).
3. Implementar `create_order(..., confirm_with_ws=True)` en `BinanceConnector`.
4. Añadir `confirm_with_ws` support en `ccxt_adapter` y actualizar `Croupier` para `wait_for_fill_confirmation`.
5. Ejecutar demo testnet, recolectar métricas, ajustar timeouts.
6. Gradual rollout en demo/live (feature-flag toggles).

Aceptación (Criterios de éxito)
- Las órdenes con `confirm_with_ws=True` deben recibir avgPrice via WS en >90% de casos dentro de `WS_CONFIRM_TIMEOUT_MS` en testnet demo.
- La tasa de fallback REST debe ser baja (configurable, p.e. <5% en condiciones normales).
- No degradación en throughput de órdenes; si ccxt.pro se muestra inestable, circuit-breaker debe activar fallback automáticamente.

Notas finales
- Mantener la agnosticidad del adaptador es crítico: los adaptadores no deben realizar suposiciones sobre `watch_*` o transporte; todo el comportamiento WS-first se implementa en `ConnectionManager` y en los conectores.
- Se recomienda instrumentar con métricas desde la fase inicial del refactor para medir real impacto.

Autor: Equipo técnico — implementación en rama `2.0`
