# Changelog

## [1.9.1] - 2025-11-04

### Added - Resiliencia 24/7 ACTIVADA ✅

**Capa de Resiliencia**:
- ✅ `ResilientConnector` - Wrapper agnóstico que agrega resiliencia a cualquier conector
- ✅ `StateRecovery` - Auto-guardado cada 60s y recuperación de sesión
- ✅ `ConnectionManager` - WebSocket + REST fallback (preparado para futuro)
- ✅ Properties de Hummingbot: `ready`, `status_dict`, `tracking_states`

**Integración Activa por Defecto**:
- ✅ `broker_interface.py` - Usa `ResilientConnector` automáticamente en modo testing
- ✅ `testing_session.py` - Resiliencia integrada directamente:
  - Setup automático de session ID
  - Recuperación de sesión al iniciar
  - Actualización de estado cada vela
  - Guardado de estado final
  - Auto-guardado cada 60s (en background)

**Sincronización de Estado Real**:
- ✅ `ExchangeStateSync` - Sincronización de balance, posiciones, fills
- ✅ `PositionTracker` modo híbrido - Detección + confirmación
- ✅ Velas enriquecidas con datos reales del exchange

### Changed

**BaseConnector**:
- Agregado `ready` property - Indica si conector está listo
- Agregado `status_dict` property - Estado de componentes
- Agregado `tracking_states` property - Estado para persistencia
- Agregado `restore_tracking_states()` - Recuperación de estado

**KrakenConnector**:
- Implementa `ready` property (conectado + mercados cargados)
- Implementa `status_dict` property (5 componentes)
- Implementa `tracking_states` property
- Implementa `restore_tracking_states()`
- Tracking de balance actualizado (`_balance_updated`)

**TableCCXTPro**:
- Wait for `connector.ready` antes de operar (timeout 10s)
- Logging de `connector.status_dict`
- Importa `asyncio` para wait logic

### Fixed

- Pre-commit: Todos los checks pasando ✅
- Flake8: Sin errores
- Black: Código formateado
- Isort: Imports ordenados

### Architecture

```
testing_session.py (MODIFICADO)
    ↓
broker_interface.py (MODIFICADO)
    ↓
ResilientConnector (NUEVO - wrapper transparente)
    ├─ StateRecovery (auto-guardado cada 60s)
    └─ ConnectionManager (futuro)
    ↓
BaseConnector (ACTUALIZADO - properties)
    ↓
KrakenConnector (ACTUALIZADO - implementa properties)
    ↓
Kraken Futures API
```

### Documentation

**live_session.py**:
- Actualizado docstring con arquitectura de resiliencia planeada
- Menciona que seguirá la misma arquitectura que testing_session.py
- Diferencias: auto-guardado cada 30s, validaciones más estrictas
- Estado: PLACEHOLDER (pendiente para v2.0)

### Removed

- ❌ `testing_session_resilient.py` - Ya no necesario (integrado directamente)

---

## [1.8] - 2025-11-03

### Added
- **Arquitectura Mesa + Conectores**: nueva `TableCCXTPro` inyecta cualquier `BaseConnector`.
- **Módulo de Conectores**: `tables/connectors/connector_base.py` y guías en `docs/connectors/`.
- **KrakenConnector**: soporte completo demo/mainnet, validado con balance real y OHLCV.
- **Tests y Validación**: `tests/test_kraken_connector.py` y `utils/validate_v18.py` para verificación end-to-end.

### Changed
- **BrokerInterface**: ahora crea mesas usando conectores modulares.
- **BalanceManager**: añade `get_balance()` y `update_balance()` para sincronizar con el exchange.
- **Documentación**: `docs/VISION.md`, `ROADMAP.md` y nuevas guías reflejan la arquitectura 1.8.

### Removed
- **Implementación Legacy**: se elimina `tables/table_ccxt_pro_legacy.py` y `docs/STATUS.md` obsoleto.
