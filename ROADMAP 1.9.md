# 🗺️ ROADMAP v1.9 - Tres Modos + Conectores Híbridos

> **Objetivo**: Clarificar arquitectura de modos (backtest/testing/live) y establecer conectores híbridos con placeholders para futuros exchanges

---

## 🎯 **Visión General**

### **Problema Actual (v1.8)**
- `MODE="live"` se usa tanto para testing (Kraken Demo) como para live trading futuro
- `TESTNET=True` es confuso y no es semánticamente claro
- Comentarios en código explican lo que debería ser explícito
- Riesgo de confusión entre "probar con dinero ficticio" vs "operar con dinero real"

```python
# v1.8 - CONFUSO ❌
MODE: Literal["backtest", "live"] = "live"  # Para simulación usar 'live' + TESTNET=True
TESTNET = True  # ¿Testing o Live? No es claro
```

### **Solución Propuesta (v1.9)**
Arquitectura de **3 Modos Explícitos** con conectores híbridos:
- **`backtest`**: Simulación con datos históricos (CSV)
- **`testing`**: Pruebas con exchange real pero dinero ficticio (Kraken Demo)
- **`live`**: Trading real con dinero real (placeholder para v2.4+)

```python
# v1.9 - EXPLÍCITO ✅
MODE: Literal["backtest", "testing", "live"] = "testing"
# No más TESTNET, el modo lo define todo
```

### **Beneficios**
- ✅ **Claridad semántica**: `MODE="testing"` es auto-explicativo
- ✅ **Seguridad**: Imposible confundir testing con live
- ✅ **Escalabilidad**: Preparado para live trading futuro (v2.4+)
- ✅ **Conectores híbridos**: Un conector por exchange, no duplicación
- ✅ **Placeholders**: Binance y Hyperliquid listos para implementación futura
- ✅ **Mantenibilidad**: Menos código, más claro

---

## 📁 **Arquitectura Propuesta**

### **Estructura de Modos**

```
Casino V2 - Modos de Operación
│
├── MODE="backtest"
│   ├── Usa: TableBacktest
│   ├── Datos: CSV históricos (tables/data/raw/)
│   ├── Dinero: Simulado ($10,000 inicial)
│   └── Propósito: Validar estrategias con datos históricos
│
├── MODE="testing"  ← 🎯 FOCO DE v1.9
│   ├── Usa: TableCCXTPro + KrakenConnector(mode="testing")
│   ├── Datos: Kraken Demo (API real, dinero ficticio)
│   ├── Dinero: Ficticio (~$5,000 demo)
│   └── Propósito: Validar sistema con exchange real
│
└── MODE="live"  ← 🚧 PLACEHOLDER (v2.4+)
    ├── Usa: TableCCXTPro + KrakenConnector(mode="live")
    ├── Datos: Exchange real (API producción)
    ├── Dinero: REAL 💰
    └── Propósito: Trading en producción
```

### **Estructura de Conectores**

```
tables/connectors/
├── __init__.py                          # Exports
├── connector_base.py                    # Interface (sin cambios)
│
├── kraken/
│   ├── __init__.py
│   ├── kraken_connector.py              # ✅ HÍBRIDO (testing + live)
│   └── kraken_constants.py              # URLs, endpoints, config
│
├── binance/                             # 🆕 PLACEHOLDER v1.9
│   ├── __init__.py
│   ├── binance_connector.py             # Estructura básica, no funcional
│   └── binance_constants.py             # URLs testnet/mainnet
│
└── hyperliquid/                         # 🆕 PLACEHOLDER v1.9
    ├── __init__.py
    ├── hyperliquid_connector.py         # Estructura básica, no funcional
    └── hyperliquid_constants.py         # URLs y config
```

### **Estructura de Sessions**

```
core/
├── config.py                            # 🔄 MODIFICAR: 3 modos
├── version.py                           # 🔄 ACTUALIZAR: v1.9
├── backtest_session.py                  # ✅ Sin cambios
├── testing_session.py                   # 🔄 RENOMBRAR: live_session.py → testing_session.py
└── live_session.py                      # 🆕 PLACEHOLDER: Para v2.4+
```

---

## 📋 **Plan de Implementación**

### **Fase 1: Preparación y Limpieza**
- [ ] Crear `ROADMAP 1.9.md` (este archivo)
- [ ] Actualizar `docs/VISION.md` con sección de 3 modos
- [ ] Crear backup de archivos a modificar

**Criterios**: Documentación clara y backups creados

---

### **Fase 2: Refactorizar Config (3 Modos)**
- [ ] Modificar `core/config.py`:
  - Cambiar `MODE: Literal["backtest", "live"]` → `MODE: Literal["backtest", "testing", "live"]`
  - Eliminar variable `TESTNET`
  - Agregar `EXCHANGE: Literal["KRAKEN", "BINANCE", "HYPERLIQUID"]`
  - Agregar validaciones de seguridad para `MODE="live"`
- [ ] Crear tests: `tests/test_config_modes.py`

**Criterios**: Config con 3 modos, TESTNET eliminado, validaciones funcionando

---

### **Fase 3: Refactorizar KrakenConnector (Híbrido)**
- [ ] Modificar `tables/connectors/kraken/kraken_connector.py`:
  - Agregar parámetro `mode: Literal["testing", "live"]`
  - Implementar lógica de URLs según modo
  - Agregar `_validate_live_credentials()`
  - Agregar warnings para live mode
- [ ] Actualizar `kraken_constants.py` con URLs separadas
- [ ] Crear tests: `tests/test_kraken_hybrid.py`

**Criterios**: KrakenConnector híbrido funcional, validaciones activas

---

### **Fase 4: Renombrar y Crear Sessions**
- [ ] Renombrar: `core/live_session.py` → `core/testing_session.py`
- [ ] Modificar `testing_session.py`: actualizar nombres y logging
- [ ] Crear `core/live_session.py` (placeholder con NotImplementedError)
- [ ] Actualizar `main.py` con lógica de 3 modos

**Criterios**: Sessions separadas, nombres semánticamente correctos

---

### **Fase 5: Crear Placeholders de Conectores**
- [ ] Crear estructura Binance:
  - `tables/connectors/binance/__init__.py`
  - `tables/connectors/binance/binance_connector.py`
  - `tables/connectors/binance/binance_constants.py`
- [ ] Crear estructura Hyperliquid:
  - `tables/connectors/hyperliquid/__init__.py`
  - `tables/connectors/hyperliquid/hyperliquid_connector.py`
  - `tables/connectors/hyperliquid/hyperliquid_constants.py`
- [ ] Implementar con NotImplementedError y documentación
- [ ] Actualizar `tables/connectors/__init__.py`

**Criterios**: Estructura creada, imports funcionan, errores claros

---

### **Fase 6: Actualizar BrokerInterface**
- [ ] Modificar `croupier/broker_interface.py` para 3 modos
- [ ] Agregar validaciones y mensajes claros
- [ ] Actualizar tests de broker_interface

**Criterios**: BrokerInterface crea mesas según modo, errores claros

---

### **Fase 7: Testing End-to-End**
- [ ] Test MODE="backtest" (funciona igual que v1.8)
- [ ] Test MODE="testing" con Kraken (funciona igual que v1.8 live)
- [ ] Test MODE="live" (lanza error apropiado)
- [ ] Test exchanges no disponibles (errores claros)
- [ ] Ejecutar suite completa: `pytest tests/ -v`
- [ ] Ejecutar pre-commit: `pre-commit run --all-files`

**Criterios**: Todos los tests pasan, pre-commit al 100%

---

### **Fase 8: Documentación y Cleanup**
- [ ] Actualizar `docs/VISION.md` con 3 modos
- [ ] Actualizar `docs/CHANGELOG.md` con entrada v1.9
- [ ] Actualizar `core/version.py` a 1.9
- [ ] Crear/actualizar guías de modos y conectores
- [ ] Eliminar backups si todo funciona

**Criterios**: Documentación completa y consistente

---

## 🎯 **Criterios de Éxito v1.9**

### **Funcional**
- ✅ 3 modos funcionan correctamente
- ✅ `MODE="testing"` funciona igual que v1.8 live
- ✅ `MODE="live"` lanza error claro
- ✅ KrakenConnector híbrido funciona
- ✅ Validaciones de seguridad activas

### **Arquitectura**
- ✅ Código más claro y semántico
- ✅ TESTNET eliminado
- ✅ Conectores híbridos (un conector por exchange)
- ✅ Estructura preparada para v2.0+
- ✅ Sin duplicación de código

### **Seguridad**
- ✅ Múltiples capas de validación para live
- ✅ Imposible activar live por error
- ✅ Mensajes y warnings claros

### **Testing**
- ✅ Tests de v1.8 siguen pasando
- ✅ Nuevos tests para 3 modos
- ✅ Pre-commit hooks al 100%

### **Documentación**
- ✅ VISION.md actualizado
- ✅ ROADMAP v1.9 completo
- ✅ CHANGELOG.md con v1.9
- ✅ Guías actualizadas

---

## 🚀 **Futuro (Post v1.9)**

### **v2.0 - Binance Connector**
- Implementar `BinanceConnector` completo
- Soporte testnet y mainnet

### **v2.1 - Hyperliquid Connector**
- Implementar `HyperliquidConnector` completo
- Solo live (no tiene testnet)

### **v2.4 - Live Trading Activado** 🎯
- Implementar `core/live_session.py`
- Activar live trading con 3 exchanges
- Risk management mejorado

---

## 📝 **Notas Importantes**

### **Por Qué Conectores Híbridos**
- Kraken testing y live usan la **misma API**, solo cambian URLs
- CCXT y Hummingbot usan este patrón
- Validaciones en múltiples capas garantizan seguridad
- Mantenimiento más simple

### **Por Qué Placeholders**
- Establece arquitectura correcta desde ahora
- Facilita implementación futura
- No rompe el sistema (no se usan en v1.9)

### **Seguridad en Live Mode**
4 capas de protección:
1. Variable de entorno: `CASINO_LIVE_TRADING_ENABLED=true`
2. Config flag: `LIVE_TRADING_ENABLED=True`
3. Confirmación interactiva: Usuario escribe "YES"
4. Validación de credenciales en conector

---

**Última actualización**: 2025-11-03
**Autor**: Pedro + Cascade
**Estado**: 📝 PLANIFICACIÓN (0/8 fases)
