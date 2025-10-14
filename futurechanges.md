## Mitigación ante Buckets Desconocidos (`UNKNOWN`)

### Contexto
Durante el backtest reciente se observó que, cuando los `features` consolidados no contienen los campos esperados por `BucketManager` (por ejemplo `bbw`, `range_score`, hora válida), el clasificador cae en el bucket `UNKNOWN`. En ese escenario Gemini sigue procesando la señal y podría generar apuestas con estimaciones mal condicionadas, degradando la credibilidad estadística del sistema.

### Cambio propuesto
Implementar un guard-rail en `Gemini.evaluate_signals` para abortar cualquier apuesta (retornar `GHOST`) cuando alguno de los participantes derive de un bucket `UNKNOWN`. La regla debe ser explícita:

1. Al extraer `Participant`s, si `participant.bucket == "UNKNOWN"`, descartar inmediatamente la señal.
2. Opcional: loggear un warning con `symbol`, `timeframe` y `contributors` para facilitar el diagnóstico.

Esto asegura que solo se ejecuten trades cuando el contexto fue correctamente clasificado, manteniendo la coherencia con la política de “apagar totalmente” ante falta de edge o soporte insuficiente.

---

## Integración ASTERDEx — Paper Trading

### Objetivo
Preparar el stack del casino para operar en **paper trading** con ASTERDEx (futuros perpetuos), reutilizando la arquitectura Gemini → Croupier → Mesas.

### Hallazgos clave de la documentación
- REST base URL: `https://fapi.asterdex.com`
- WebSocket base: `wss://fstream.asterdex.com`
- Autenticación: firma HMAC SHA256 idéntica a Binance Futures (`timestamp`, `recvWindow`, firma en query/body + header `X-MBX-APIKEY`)
- Fees: maker `0.005%` (`0.00005`), taker `0.04%` (`0.0004`)
- Funding: interés fijo `0.03%` diario (≈ `1.25e-5` por hora) + prima dinámica

### Cambios propuestos
1. **Perfiles de exchange**  
   - Añadir `tables/data/exchange_profiles/asterdex_paper.json` con fees, slippage y funding base.
   - Permitir elegirlo vía `config.EXCHANGE_PROFILE = "asterdex_paper"`.

2. **Cliente HTTP nativo**  
   - Crear `utils/asterdex_client.py` con helpers firmados (`get_server_time`, `get_klines`, `place_order`, `cancel_order`, `account_balance`).
   - Centralizar firma y headers, parametrizar `base_url` para alternar entre live/paper si publican endpoints separados.

3. **Loader de credenciales**  
   - `utils/aster_env_loader.py` que lea `ASTER_API_KEY`, `ASTER_API_SECRET`, `ASTER_BASE_URL`, `ASTER_WS_URL` desde `.env`/`config.py` y valide `GET /fapi/v1/time`.

4. **Mesa realtime especializada**  
   - Nuevo archivo `tables/table_aster_paper.py` derivado de `BaseTable`:
     - `next_candle()` con pooling WebSocket `kline` (fallback REST) y estado de `BalanceManager`.
     - `execute_order()` que envíe `POST /fapi/v1/order`, monitoree estado (`GET /fapi/v1/order`) y registre fees/funding reales.
     - Flag `paper_mode=True` para evitar traslados de fondos reales.

5. **Broker & Croupier**  
   - Extender `croupier/broker_interface.py` para despachar `TableAsterPaper` cuando `MODE="realtime"` y `config.EXCHANGE` contenga `ASTER`.
   - Añadir soporte a `TableRealtime` para seleccionar cliente externo a `python-binance`.

6. **Configuración**  
   - Nuevos campos en `config.py`: `ASTER_BASE_URL`, `ASTER_WS_URL`, `ASTER_DEFAULT_SYMBOL`, `ASTER_DEFAULT_INTERVAL`, `ASTER_RECV_WINDOW`.
   - Documentar variables `.env` y pasos de arranque en `README`.

7. **Pruebas**  
   - Script CLI `scripts/test_asterdex_connection.py` (opcional) que valide credenciales, descargue un kline y ejecute `order/test`.
   - Mocks unitarios para firma y parseo de respuestas.

### Riesgos / TODO abiertos
- Confirmar endpoint oficial de paper trading (si difiere de `fapi.asterdex.com`).
- Definir estrategia de reconexión para WebSocket (la sesión expira a las 24h).
- Mapear campos específicos de ASTER que difieran de Binance (p.ej. tipos de órdenes adicionales).
- Ajustar cálculo de funding real cuando la API devuelva eventos de `income`.

---

## Integración Kraken Futures — Demo Trading

### Objetivo
Permitir paper trading contra **Kraken Futures demo** reutilizando el flujo live.

### TODO
- Completar parsing de `sendorder`/`orderEvents` para obtener fills y PnL reales.
- Normalizar tamaños de contrato según `instrument.contractSize` y márgenes.
- Incorporar reconexión websocket cuando se integre streaming oficial.
- Soportar cuentas multi-collateral identificando correctamente `portfolioValue`.
